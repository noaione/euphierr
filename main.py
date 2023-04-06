import asyncio
from datetime import date, datetime
from pathlib import Path
from typing import Any, List, Optional, Tuple

import pendulum
from aiopath import AsyncPath

from euphierr.config import read_config
from euphierr.exceptions import ArcNCielInvalidTorrentError, ArcNCielNoConfigFile
from euphierr.feeds import process_series
from euphierr.management import get_arcnciel_data, get_downloaded_series, save_arcnciel_data
from euphierr.models import ArcNCielTorrent, SeriesSeason
from euphierr.qbt import EuphieClient
from euphierr.tooling import setup_logger

ROOT_DIR = Path(__file__).absolute().parent
LOCK_FILE = ROOT_DIR / "arcnciel.lock"
logger = setup_logger(ROOT_DIR / "logs" / "arcnciel.log")
_GLOBAL_TASKS: List[asyncio.Task[Any]] = []


def _get_config_file() -> Path:
    config_file = ROOT_DIR / "config.yml"
    if not config_file.exists():
        config_file = ROOT_DIR / "config.yaml"
        if not config_file.exists():
            raise ArcNCielNoConfigFile("No config file found")
    return config_file


async def _wrapped_downloader_and_move(torrent: ArcNCielTorrent, qbt: EuphieClient):
    try:
        torrent, save_dir = await qbt.add_and_wait(torrent)
        source_save = AsyncPath(save_dir)
        target_save = AsyncPath(torrent.to_data_content(source_save.suffix).path)
        await target_save.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Moving %s to %s", torrent.name, target_save)
        await source_save.rename(target_save)
        logger.info("Successfully processed %s", torrent.name)
        return torrent, source_save, True
    except ArcNCielInvalidTorrentError as te:
        logger.error("Failed to download %s", str(te))
        return torrent, None, False
    except Exception as e:
        logger.exception("An unknown error has occured!", exc_info=e)
        return torrent, None, False


async def _run_feed(series: SeriesSeason, qbt: EuphieClient):
    global _GLOBAL_TASKS

    logger.info("Processing %s", series.id)
    current_time = int(datetime.utcnow().timestamp())
    series_feeds = await process_series(series)
    downloaded_episodes = await get_downloaded_series(series)
    to_be_downloaded: List[ArcNCielTorrent] = []
    for feed in series_feeds:
        if feed.episode not in downloaded_episodes.get(str(feed.season or series.season), []):
            to_be_downloaded.append(feed)
            continue
        logger.warning(f"Episode S{feed.actual_season:02d}E{feed.episode:02d} already downloaded, skipping...")

    if not to_be_downloaded:
        logger.info("No new episodes for %s", series.id)
        return

    logger.info("Found %d new episodes for %s, creating tasks...", len(to_be_downloaded), series.id)
    tasks: List[asyncio.Task[Tuple[ArcNCielTorrent, Optional[AsyncPath], bool]]] = []
    for feed in to_be_downloaded:
        task_name = f"FEED_{series.id}_{feed.hash}_{current_time}"
        task = asyncio.create_task(_wrapped_downloader_and_move(feed, qbt), name=task_name)
        tasks.append(task)
        _GLOBAL_TASKS.append(task)
    logger.info("Running %d feed tasks for series %s...", len(tasks), series.id)
    results: List[Tuple[ArcNCielTorrent, Optional[AsyncPath], bool]] = await asyncio.gather(*tasks)

    arcnseries = await get_arcnciel_data(series)
    for tor, svpath, res in results:
        if res and svpath is not None:
            arcnseries.contents.append(tor.to_data_content(svpath.suffix))
    logger.info("Saving data for %s", series.id)
    await save_arcnciel_data(arcnseries)


def get_day_difference(week_air: int, week_ctime: int) -> int:
    return (week_air - week_ctime + 7) % 7


def should_check(series: SeriesSeason) -> bool:
    current_time = pendulum.now(tz="Asia/Tokyo")
    if isinstance(series.airtime, (datetime, date)):
        timezone = "Asia/Tokyo"
        if isinstance(series.airtime, datetime):
            timezone = series.airtime.tzinfo or current_time.tzinfo or "Asia/Tokyo"
            current_time = pendulum.now(tz=timezone)  # type: ignore
        time_diff = get_day_difference(series.airtime.weekday(), current_time.weekday())
        if time_diff > 0:
            current_time = current_time.add(days=time_diff)
        elif time_diff < 0:
            current_time = current_time.subtract(days=time_diff)
        hours = 0
        minutes = 0
        seconds = 0
        if isinstance(series.airtime, datetime):
            hours = series.airtime.hour
            minutes = series.airtime.minute
            seconds = series.airtime.second
        airtime = pendulum.datetime(
            year=series.airtime.year,
            month=current_time.month,
            day=current_time.day,
            hour=hours,
            minute=minutes,
            second=seconds,
            tz=timezone,  # type: ignore
        )
        if isinstance(series.airtime, datetime):
            current_time = pendulum.now(tz=timezone)  # type: ignore
        else:
            current_time = pendulum.now(tz="Asia/Tokyo")
        logger.info(
            "Next airtime for %s: %s (%s)",
            series.id,
            airtime.to_day_datetime_string(),
            current_time.to_day_datetime_string(),
        )
        diff_back = airtime.subtract(minutes=series.grace_period)
        diff_future = airtime.add(minutes=series.grace_period)
        return diff_back <= current_time <= diff_future
    return True


async def run_once():
    global _GLOBAL_TASKS

    logger.info("Starting run...")
    config = read_config(_get_config_file())
    current_time = int(datetime.utcnow().timestamp())
    euphie_qbt = EuphieClient(config.qbt)

    logger.info("Current time: %s", pendulum.now(tz="Asia/Tokyo").to_day_datetime_string())
    configure_series: List[SeriesSeason] = []
    for series in config.series:
        if not should_check(series):
            logger.info("Skipping %s, not the right time", series.id)
            continue
        configure_series.append(series)
    if not configure_series:
        logger.info("No series to check, exiting...")
        return

    # Chunk series, so we don't overload Nyaa RSS and got banned.
    chunk_size = 3
    chunk_series = [configure_series[i : i + chunk_size] for i in range(0, len(configure_series), chunk_size)]

    for idx, chunk in enumerate(chunk_series, 1):
        logger.info(
            "Processing chunk %d/%d (%d series out of %d)", idx, len(chunk_series), len(chunk), len(chunk_series)
        )
        tasks: List[asyncio.Task[None]] = []
        for series in chunk:
            task_name = f"SERIES_CHUNK_{idx}_{series.id}_{current_time}"
            task = asyncio.create_task(_run_feed(series, euphie_qbt), name=task_name)
            tasks.append(task)
            _GLOBAL_TASKS.append(task)
        logger.info("Executing series chunk %d/%d tasks...", idx, len(chunk_series))
        await asyncio.gather(*tasks)
    logger.info("Run complete")


if __name__ == "__main__":
    logger.info("Starting ArcNCiel/EuphieRR v0.3.9...")
    if LOCK_FILE.exists():
        logger.warning("Lock file exists, exiting")

    LOCK_FILE.touch()
    try:
        asyncio.run(run_once())
    except (KeyboardInterrupt, SystemExit):
        logger.warning("Interrupted, exiting...")
        for task in _GLOBAL_TASKS:
            task.cancel("Process got interrupted")
    except Exception as e:
        logger.exception("Unhandled exception: %s", str(e))
        for task in _GLOBAL_TASKS:
            task.cancel("Unhandled exception")
    finally:
        LOCK_FILE.unlink(missing_ok=True)
