import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, List, Tuple

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
        target_save = AsyncPath(torrent.to_data_content().path)
        await target_save.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Moving %s to %s", torrent.name, target_save)
        await source_save.rename(target_save)
        logger.info("Successfully processed %s", torrent.name)
        return torrent, True
    except ArcNCielInvalidTorrentError as te:
        logger.error("Failed to download %s", str(te))
        return torrent, False
    except Exception as e:
        logger.exception("An unknown error has occured!", exc_info=e)
        return torrent, False


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

    if not to_be_downloaded:
        logger.info("No new episodes for %s", series.id)
        return

    logger.info("Found %d new episodes for %s, creating tasks...", len(to_be_downloaded), series.id)
    tasks: List[asyncio.Task[Tuple[ArcNCielTorrent, bool]]] = []
    for feed in to_be_downloaded:
        task_name = f"FEED_{series.id}_{feed.hash}_{current_time}"
        task = asyncio.create_task(_wrapped_downloader_and_move(feed, qbt), name=task_name)
        tasks.append(task)
        _GLOBAL_TASKS.append(task)
    logger.info("Running %d feed tasks for series %s...", len(tasks), series.id)
    results: List[Tuple[ArcNCielTorrent, bool]] = await asyncio.gather(*tasks)

    arcnseries = await get_arcnciel_data(series)
    for tor, res in results:
        if res:
            arcnseries.contents.append(tor.to_data_content())
    logger.info("Saving data for %s", series.id)
    await save_arcnciel_data(arcnseries)


async def run_once():
    global _GLOBAL_TASKS

    logger.info("Starting run...")
    config = read_config(_get_config_file())
    current_time = int(datetime.utcnow().timestamp())
    euphie_qbt = EuphieClient(config.qbt)

    tasks: List[asyncio.Task[None]] = []
    logger.info("Processing %d series", len(config.series))
    for series in config.series:
        task_name = f"SERIES_{series.id}_{current_time}"
        task = asyncio.create_task(_run_feed(series, euphie_qbt), name=task_name)
        tasks.append(task)
        _GLOBAL_TASKS.append(task)
    logger.info("Running %d series tasks...", len(tasks))
    await asyncio.gather(*tasks)
    logger.info("Run complete")


if __name__ == "__main__":
    logger.info("Starting ArcNCiel/EuphieRR v0.1.0...")
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
