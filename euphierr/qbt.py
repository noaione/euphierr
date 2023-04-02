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

# qbittorrent client and stuff.

import asyncio
import logging
from functools import partial
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple, Union, cast, overload

import aiohttp
import qbittorrentapi as qbtapi
from qbittorrentapi.exceptions import UnsupportedMediaType415Error
from qbittorrentapi.torrents import TorrentDictionary, TorrentInfoList
from torf import Torrent as TorfTorrent

from euphierr.exceptions import (
    ArcNCielInvalidTorrentError,
    ArcNCielInvalidTorrentTooManyFiles,
    ArcNCielInvalidTorrentURL,
)
from euphierr.models import ArcNCielTorrent, QBittorrentConfig

__all__ = ("EuphieClient",)
__UA__ = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0"  # noqa


class EuphieClient:
    def __init__(self, qbt_conf: QBittorrentConfig) -> None:
        self._client = qbtapi.Client(
            host=qbt_conf.host,
            port=qbt_conf.port,
            username=qbt_conf.username,
            password=qbt_conf.password,
        )
        self.logger = logging.getLogger("euphierr.qbt")
        self._config = qbt_conf

    @property
    def client(self) -> qbtapi.Client:
        return self._client

    async def _add_torrent(self, torrent_url: str, torrent_bytes: bytes):
        category = self._config.category
        loop = asyncio.get_event_loop()
        torrent_add_wrap = partial(
            self._client.torrents_add,
            torrent_files=torrent_bytes,
            category=category,
            use_auto_torrent_management=category is not None,
        )
        try:
            executed = await loop.run_in_executor(None, torrent_add_wrap)
            return "ok" in executed.lower()
        except UnsupportedMediaType415Error:
            raise ArcNCielInvalidTorrentURL(torrent_url)

    @overload
    async def _list_torrents(self, torrent_hash: str) -> Optional[TorrentDictionary]:
        ...

    @overload
    async def _list_torrents(self, torrent_hash: None = None) -> TorrentInfoList:
        ...

    async def _list_torrents(
        self, torrent_hash: Optional[str] = None
    ) -> Union[Optional[TorrentDictionary], TorrentInfoList]:
        category = self._config.category
        if torrent_hash is not None:
            category = None
        torrent_list_wrap = partial(
            self._client.torrents_info,
            category=category,
            sort="added_on",
            limit=30,
            reverse=True,
            torrent_hashes=torrent_hash,
        )

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, torrent_list_wrap)
        if torrent_hash is not None:
            for torrent in results:
                if torrent["hash"] == torrent_hash:
                    return torrent
            return None
        return results

    async def download_torrent(self, torrent_url: str) -> tuple[bytes, str]:
        async with aiohttp.ClientSession(
            headers={
                "User-Agent": __UA__,
            }
        ) as session:
            async with session.get(torrent_url) as resp:
                if resp.status != 200:
                    raise ArcNCielInvalidTorrentURL(torrent_url)
                torrent_data = await resp.read()
                torrent_stream = BytesIO(torrent_data)
                torrent_stream.seek(0)
                try:
                    torrent = TorfTorrent.read_stream(torrent_stream)
                    if len(torrent.files) > 1:
                        raise ArcNCielInvalidTorrentTooManyFiles(torrent_url)
                    torrent_stream.close()
                    return torrent_data, torrent.infohash
                except Exception:
                    raise ArcNCielInvalidTorrentError(f"Failed to read torrent: {torrent_url}")

    async def add_and_wait(self, torrent: ArcNCielTorrent) -> Tuple[ArcNCielTorrent, Path]:
        self.logger.info(f"Adding torrent to client: {torrent.name}")
        tor_bytes, tor_hash = await self.download_torrent(torrent.url)
        result = await self._add_torrent(torrent.url, tor_bytes)
        if not result:
            raise ArcNCielInvalidTorrentError(f"Failed to add torrent: {torrent.name} ({torrent.url})")
        torrent.hash = tor_hash

        is_downloaded = False
        missing_failure = 0
        loop = asyncio.get_event_loop()
        temporary_dl_dir: Optional[Path] = None
        self.logger.info(f"Waiting for client to finish downloading: {torrent.name}")
        while not is_downloaded:
            await asyncio.sleep(5)  # refresh every 5s
            tor_info = await self._list_torrents(torrent.hash)
            if tor_info is None:
                missing_failure += 1
                if missing_failure > 5:
                    raise ArcNCielInvalidTorrentError(f"Torrent disappeared: {torrent.name} ({torrent.url})")
                continue
            missing_failure = 0

            if tor_info.state_enum.is_errored:
                raise ArcNCielInvalidTorrentError(f"Torrent errored: {torrent.name} ({torrent.url})")
            if tor_info.state_enum.is_complete:
                tor_files = await loop.run_in_executor(None, self._client.torrents_files, tor_hash)
                tor_file = tor_files[0]["name"]
                temporary_dl_dir = Path(tor_info["save_path"]) / tor_file  # type: ignore
                wrap_delete = partial(self._client.torrents_delete, torrent_hashes=tor_hash)
                await loop.run_in_executor(None, wrap_delete)
                break
        self.logger.info(f"Torrent downloaded: {torrent.name}")
        return torrent, cast(Path, temporary_dl_dir)
