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

from __future__ import annotations

import gzip
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

import coloredlogs

__all__ = (
    "RollingFileHandler",
    "setup_logger",
)


class RollingFileHandler(RotatingFileHandler):
    """
    A log file handler that follows the same format as RotatingFileHandler,
    but automatically roll over to the next numbering without needing to worry
    about maximum file count or something.

    At startup, we check the last file in the directory and start from there.
    """

    maxBytes: int
    gunzip: bool

    def __init__(
        self,
        filename: os.PathLike,
        mode: str = "a",
        maxBytes: int = 0,
        backupCount: int = 0,
        encoding: Optional[str] = None,
        delay: bool = False,
        gunzip: bool = True,
    ) -> None:
        self._last_backup_count = 0
        super().__init__(
            filename, mode=mode, maxBytes=maxBytes, backupCount=backupCount, encoding=encoding, delay=delay
        )
        self.maxBytes = maxBytes
        self.backupCount = backupCount
        self.gunzip = gunzip
        self._base_path = Path(filename).parent
        self._filename = Path(filename).name
        self._determine_start_count()

    def _determine_start_count(self):
        all_files = list(self._base_path.glob(f"{self._filename}*"))
        if all_files:
            all_files.sort(key=lambda x: x.stem)
            fn = all_files[-1]
            last_digit = fn.stem.split(".")[-1]
            if last_digit.isdigit():
                self._last_backup_count = int(last_digit)

    def doRollover(self) -> None:
        if self.stream and not self.stream.closed:
            self.stream.close()
        self._last_backup_count += 1
        next_name = "%s.%d" % (self.baseFilename, self._last_backup_count)
        self.rotate(self.baseFilename, next_name)
        if not self.delay:
            self.stream = self._open()

    def _safe_gunzip(self, source: str, dest: str):
        try:
            with Path(source).open("rb") as sf:
                with gzip.open(dest + ".gz", "wb") as df:
                    for line in sf:
                        df.write(line)
            return True
        except Exception:
            return False

    def _safe_rename(self, source: str, dest: str):
        try:
            Path(source).rename(dest)
            return True
        except Exception:
            return False

    def _safe_remove(self, source: str):
        try:
            Path(source).unlink(missing_ok=True)
            return True
        except Exception:
            return False

    def rotator(self, source: str, dest: str) -> None:
        # Override the rotator to gzip the file before moving it
        if not Path(source).exists():
            return  # silently fails
        if self.gunzip:
            # Try to gzip the file
            result = self._safe_gunzip(source, dest)
            if result:
                # If successful, delete the original file
                self._safe_remove(source)
            else:
                # If not successful, just rename the file
                self._safe_rename(source, dest)
        else:
            # Just rename the file
            self._safe_rename(source, dest)


def setup_logger(log_path: Path):
    log_path.parent.mkdir(exist_ok=True)

    file_handler = RollingFileHandler(log_path, maxBytes=5_242_880, backupCount=5, encoding="utf-8")
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[file_handler],
        format="[%(asctime)s] - (%(name)s)[%(levelname)s](%(funcName)s): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger()
    coloredlogs.install(
        fmt="[%(asctime)s %(hostname)s][%(levelname)s] (%(name)s[%(process)d]): %(funcName)s: %(message)s",
        level=logging.INFO,
        logger=logger,
        stream=sys.stdout,
    )

    # Set default logging for some modules
    logging.getLogger("qbittorrentapi").setLevel(logging.INFO)

    # Set back to the default of INFO even if asyncio's debug mode is enabled.
    logging.getLogger("asyncio").setLevel(logging.INFO)

    return logger
