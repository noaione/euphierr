"""
euphierr
~~~~~~~~
The internal code for the ArcNCiel or EuphieRR project.

:copyright: (c) 2023-present noaione
:license: MIT, see LICENSE for more details.
"""

from euphierr.models import ClienteleConfig

from .base import *
from .qbt import EuphieQbtClient, has_qbt_api


def get_client(config: ClienteleConfig) -> EuphieClient:
    if config.type.lower() == "qbt":
        if not has_qbt_api():
            raise ImportError("qBittorrent API is not installed")
        return EuphieQbtClient(config)
    raise ValueError(f"Unknown client type: {config.type}")


def available_clients():
    clients = []
    if has_qbt_api():
        clients.append("qbt")
    return clients
