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

import asyncio
from typing import List, Optional, cast
from venv import logger

import aiohttp
import feedparser
from feedparser.util import FeedParserDict

from euphierr.exceptions import ArcNCielFeedInvalid, ArcNCielFeedMissing
from euphierr.models import ArcNCielTorrent, SeriesSeason

__all__ = (
    "process_series",
    "fetch_single_feed",
)
__UA__ = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0"  # noqa


async def fetch_single_feed(feed_url: str) -> FeedParserDict:
    loop = asyncio.get_event_loop()
    async with aiohttp.ClientSession() as session:
        async with session.get(feed_url, headers={"User-Agent": __UA__}) as resp:
            if resp.status != 200:
                raise ArcNCielFeedMissing(feed_url)
            rss_text = await resp.text()
            try:
                rss_feed = await loop.run_in_executor(None, feedparser.parse, rss_text)
                return cast(FeedParserDict, rss_feed)
            except Exception as e:
                raise ArcNCielFeedInvalid(feed_url, str(e)) from e


async def process_series(series: SeriesSeason):
    feed_info = await fetch_single_feed(series.rss)

    match_series: List[ArcNCielTorrent] = []
    for entry in feed_info.entries:
        entry_title = cast(str, entry.title)
        entry_link = cast(str, entry.link)
        entry_infohash = cast(Optional[str], entry["nyaa_infohash"])

        if (title_match := series.episode_regex.search(entry_title)) is None:
            logger.warning("Entry %s does not match %s", entry_title, series.episode_regex.pattern)
            continue

        matchers = series.matches
        matching_fail = False
        for idx, match in enumerate(matchers):
            if match.lower() not in entry_title.lower():
                logger.warning("Entry %s does not match (%d) %s", entry_title, idx, match)
                matching_fail = True
                continue
        if matching_fail:
            continue

        episode = int(title_match.group("episode"))
        season = title_match.group("season")
        if season is not None:
            season = str(series.season)

        tor_info = ArcNCielTorrent(
            name=entry_title,
            url=entry_link,
            hash=entry_infohash,
            series=series,
            episode=episode,
            season=int(season),
        )
        match_series.append(tor_info)
    logger.info("Found %d matches for %s", len(match_series), series.id)
    return match_series
