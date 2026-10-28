"""Standalone Hermes update watcher package."""

from .model import DiscoveryResult, DiscoveryState, ReleaseIdentity, ReleaseMetadata
from .releases import GitHubReleaseReader, ReleaseError, discover_releases

__all__ = [
    "DiscoveryResult",
    "DiscoveryState",
    "GitHubReleaseReader",
    "ReleaseError",
    "ReleaseIdentity",
    "ReleaseMetadata",
    "discover_releases",
]
