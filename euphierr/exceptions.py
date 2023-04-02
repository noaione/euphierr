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

# Exceptions class and more.


class ArcNCielException(Exception):
    pass


class ArcNCielNoConfigFile(ArcNCielException):
    pass


class ArcNCielConfigError(ArcNCielException):
    def __init__(self, path: str, message: str) -> None:
        self.message = message
        self.path = path
        super().__init__(f"Error in config file key `{path}`: {message}")


class ArcNCielInvalidTorrentError(ArcNCielException):
    pass


class ArcNCielInvalidTorrentURL(ArcNCielInvalidTorrentError):
    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__(f"Invalid torrent url: {url}")


class ArcNCielInvalidTorrentTooManyFiles(ArcNCielInvalidTorrentError):
    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__("Too many files in torrent, please use a torrent with only one file")


class ArcNCielFeedError(ArcNCielException):
    pass


class ArcNCielFeedMissing(ArcNCielFeedError):
    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__(f"Invalid feed url: {url}")


class ArcNCielFeedInvalid(ArcNCielFeedError):
    def __init__(self, url: str, message: str) -> None:
        self.url = url
        self.message = message
        super().__init__(f"Provided feed url is invalid: {url} ({message})")
