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

from io import BytesIO
from pathlib import Path
from typing import Tuple

import aiohttp
from torf import Torrent as TorfTorrent

from euphierr.exceptions import (
    ArcNCielInvalidTorrentError,
    ArcNCielInvalidTorrentTooManyFiles,
    ArcNCielInvalidTorrentURL,
)
from euphierr.models import ArcNCielTorrent, ClienteleConfig

__all__ = ("EuphieClient",)
__UA__ = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0"


class EuphieClient:
    def __init__(self, config: ClienteleConfig) -> None:
        self._config = config

    async def add_and_wait(self, torrent: ArcNCielTorrent) -> Tuple[ArcNCielTorrent, Path]:
        raise NotImplementedError

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

    async def login(self):
        raise NotImplementedError
