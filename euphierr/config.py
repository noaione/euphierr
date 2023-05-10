"""
MIT License

Copyright (c) 2023-present noaione

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

# The config parser
# Also the ArcNCiel data parser

import logging
import re
import uuid
from datetime import date, datetime
from math import inf as Infinity
from pathlib import Path
from string import Formatter
from typing import List, Optional, Union, cast
from urllib.parse import urlparse

import yaml

from euphierr.exceptions import ArcNCielConfigError
from euphierr.models import ArcNCielConfig, QBittorrentConfig, SeriesSeason

__all__ = (
    "read_config",
    "write_config",
)


def _check_format_string_key(to_parse: str, key: str):
    # Check if the string has the key in it
    # note, some key might have a modifier like {key:0>2}
    key_fmt = [tup[1] for tup in Formatter().parse(to_parse) if tup[1] is not None]
    return key in key_fmt


def _parse_airtime(airtime: Union[datetime, date]) -> Union[datetime, date, None]:
    if not isinstance(airtime, (datetime, date)):
        return None
    if isinstance(airtime, datetime):
        # Check if the airtime has timezone info
        # If it's, assume it's the local timezone
        if airtime.tzinfo is None:
            airtime = airtime.replace(tzinfo=datetime.utcnow().astimezone().tzinfo)
    return airtime


def _safe_clean_id(orig_id: str) -> str:
    # Replace space with underscore
    # Replace symbols (except underscore and dash) with underscore
    orig_id = re.sub(r"[^a-zA-Z0-9_-]", "_", orig_id)
    return orig_id


def read_config(config_path: Path) -> ArcNCielConfig:
    logger = logging.getLogger("euphierr.config")
    logger.info("Reading config from %s", config_path)
    with config_path.open("r") as f:
        data = yaml.safe_load(f)

    qbit_conf = data.get("qbt")
    if not qbit_conf:
        raise ArcNCielConfigError("qbt", "Missing key")
    qbit_url = qbit_conf.get("url", qbit_conf.get("uri"))
    qbit_user = qbit_conf.get("username", qbit_conf.get("user", qbit_conf.get("email")))
    qbit_pass = qbit_conf.get("password", qbit_conf.get("pass"))
    if not qbit_url:
        raise ArcNCielConfigError("qbt.url", "Missing key")

    # Validate URL
    parsed_qbt_host = urlparse(qbit_url)
    if not parsed_qbt_host.netloc:
        raise ArcNCielConfigError("qbt.url", "Invalid URL, missing domain/host")
    hostport = parsed_qbt_host.netloc.split(":", 1)
    host = hostport[0]
    if len(hostport) > 1:
        port = hostport[1]
    else:
        if parsed_qbt_host.scheme.startswith("http"):
            port = None
        else:
            raise ArcNCielConfigError(
                "qbt.url", "Invalid URL, unknown por! You must use a HTTP scheme or provide port!"
            )
    if parsed_qbt_host.path:
        host += parsed_qbt_host.path
    qbt_category = qbit_conf.get("category")
    parsed_qbt_conf = QBittorrentConfig(
        host=host,
        _raw_input=qbit_url,
        port=port,
        username=qbit_user,
        password=qbit_pass,
        category=qbt_category,
    )
    logger.info("Using qbittorrent host: %s", parsed_qbt_conf.host)

    series_feeds = data.get("series", [])
    parsed_series_feeds: List[SeriesSeason] = []
    resave_config = False
    for idx, feed in enumerate(series_feeds):
        if not isinstance(feed, dict):
            raise ArcNCielConfigError(f"series.{idx}", "Invalid feed data (not a dictionary)")
        feed_rss_url = feed.get("rss", feed.get("url", feed.get("uri")))
        feed_id = feed.get("id")
        if feed_id is None:
            feed_id = str(uuid.uuid4())
            logger.warning("No ID provided for feed %s, using gen ID %s", feed_rss_url, feed_id)
            resave_config = True
        _feed_id_safe = _safe_clean_id(feed_id)
        if _feed_id_safe != feed_id:
            logger.warning('Provided ID is "unsafe" for feed %s, using cleaned ID %s', feed_rss_url, _feed_id_safe)
            feed_id = _feed_id_safe
            resave_config = True
        if feed_rss_url is None:
            logger.error("No RSS URL provided for feed %s", feed_id)
            raise ArcNCielConfigError(f"series.{idx}.rss", "Missing key")
        feed_rss_test = urlparse(feed_rss_url)
        if "nyaa.si" not in feed_rss_test.netloc:
            logger.error("Invalid RSS URL provided for feed %s, not a Nyaa.si link!", feed_id)
            raise ArcNCielConfigError(f"series.{idx}.rss", "Invalid URL, not a Nyaa.si link")
        if "page=rss" not in feed_rss_test.query:
            logger.error("Invalid RSS URL provided for feed %s, not a Nyaa RSS link!", feed_id)
            raise ArcNCielConfigError(f"series.{idx}.rss", "Invalid URL, not a Nyaa RSS link")
        feed_regex = cast(Optional[str], feed.get("episodeRegex", feed.get("episode_regex")))
        if feed_regex is None:
            logger.error("No episode regex provided for feed %s, skipping", feed_id)
            raise ArcNCielConfigError(f"series.{idx}.episode_regex", "Missing key")
        feed_target_dir_temp = feed.get("targetDir", feed.get("target_dir"))
        if feed_target_dir_temp is None:
            logger.error("No target directory provided for feed %s, skipping", feed_id)
            raise ArcNCielConfigError(f"series.{idx}.target_dir", "Missing key")
        feed_target_dir = Path(feed_target_dir_temp)
        if not feed_target_dir.exists():
            logger.warning("Target directory %s for feed %s does not exist!", feed_target_dir, feed_id)
        # TODO: change this whenever I want to make it dynamic (i probably wont lmao)
        target_name = "Episode S{season:02d}E{episode:02d}"
        if feed_regex.startswith("/") and feed_regex.endswith("/"):
            feed_regex = feed_regex[1:-1]
        try:
            feed_regex_re = re.compile(feed_regex)
        except re.error as e:
            logger.error("Invalid regex for feed %s: %s", feed_id, e)
            raise ArcNCielConfigError(f"series.{idx}.episode_regex", "Invalid regex") from e
        feed_regex_keys = list(feed_regex_re.groupindex.keys())
        if "episode" not in feed_regex_keys:
            logger.error("Invalid regex for feed %s, must have `episode` group match!", feed_id)
            raise ArcNCielConfigError(
                f"series.{idx}.episode_regex",
                "Invalid regex, need `episode` group match",
            )
        if not _check_format_string_key(target_name, "episode"):
            logger.error(
                "Invalid target name for feed %s, must have `episode` key in the formatter!",
                feed_id,
            )
            raise ArcNCielConfigError(f"series.{idx}.target_name", "Invalid format, need `episode` key")
        feed_season = feed.get("season", 1)
        if not isinstance(feed_season, int):
            try:
                feed_season = int(feed_season)
            except ValueError:
                logger.error("Invalid season number for feed %s, must be an integer!", feed_id)
                raise ArcNCielConfigError(
                    f"series.{idx}.season",
                    "Invalid season number, must be an integer",
                ) from None
        feed_matches = feed.get("matches", [])
        if not isinstance(feed_matches, list):
            logger.error("Invalid matches for feed %s, must be a list!", feed_id)
            raise ArcNCielConfigError(f"series.{idx}.matches", "Invalid matches, must be a list") from None
        feed_ignore_matches = feed.get("ignore_matches", [])
        if not isinstance(feed_ignore_matches, list):
            logger.error("Invalid ignore matches for feed %s, must be a list!", feed_id)
            raise ArcNCielConfigError(
                f"series.{idx}.ignore_matches",
                "Invalid ignore matches, must be a list",
            ) from None
        feed_airtime = cast(Optional[Union[datetime, date]], feed.get("airtime"))
        if feed_airtime is not None:
            feed_airtime = _parse_airtime(feed_airtime)
        feed_grace_period = feed.get("gracePeriod", feed.get("grace_period", 120))
        try:
            feed_grace_period = int(feed_grace_period)
        except ValueError:
            logger.error("Invalid grace period for feed %s, must be an integer!", feed_id)
            raise ArcNCielConfigError(
                f"series.{idx}.grace_period",
                "Invalid grace period, must be an integer",
            ) from None
        feed_matches = list(map(str, feed_matches))
        feed_ignore_matches = list(map(str, feed_ignore_matches))
        parsed_feed = SeriesSeason(
            id=feed_id,
            rss=feed_rss_url,
            episode_regex=feed_regex_re,
            target_dir=feed_target_dir,
            target_name=target_name,
            season=feed_season,
            matches=feed_matches,
            ignore_matches=feed_ignore_matches,
            airtime=feed_airtime,
            grace_period=feed_grace_period,
        )
        parsed_series_feeds.append(parsed_feed)

    arcn_config = ArcNCielConfig(qbt=parsed_qbt_conf, series=parsed_series_feeds)
    if resave_config:
        logger.info("Resaving config because of changes to %s", config_path)
        write_config(config_path, arcn_config)

    return arcn_config


def write_config(config_path: Path, config: ArcNCielConfig):
    data = {
        "qbt": {
            "url": config.qbt._raw_input,
            "username": config.qbt.username,
            "password": config.qbt.password,
            "category": config.qbt.category,
        },
        "series": [
            {
                "id": feed.id,
                "rss": feed.rss,
                "episode_regex": feed.episode_regex.pattern,
                "target_dir": str(feed.target_dir),
                "season": feed.season,
                "matches": feed.matches,
                "ignore_matches": feed.ignore_matches,
                "airtime": feed.airtime,
                "grace_period": feed.grace_period,
            }
            for feed in config.series
        ],
    }
    with config_path.open("w") as f:
        yaml.safe_dump(
            data,
            f,
            indent=2,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=Infinity,
        )
