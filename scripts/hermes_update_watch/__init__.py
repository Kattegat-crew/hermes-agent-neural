"""Standalone Hermes update watcher package."""

from .cli import main, run_cli
from .model import DiscoveryResult, DiscoveryState, ReleaseIdentity, ReleaseMetadata
from .releases import GitHubReleaseReader, ReleaseError, discover_releases
from .transport import DiscordTransport, TransportError

__all__ = [
    "DiscoveryResult",
    "DiscoveryState",
    "DiscordTransport",
    "GitHubReleaseReader",
    "ReleaseError",
    "ReleaseIdentity",
    "ReleaseMetadata",
    "TransportError",
    "discover_releases",
    "main",
    "run_cli",
]
