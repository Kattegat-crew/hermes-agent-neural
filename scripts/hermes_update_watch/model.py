"""Typed release-discovery values for the update watcher."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, TypedDict

REPOSITORY = "NousResearch/hermes-agent"
API_ROOT = "https://api.github.com"
RELEASES_PATH = f"/repos/{REPOSITORY}/releases"
TAG_REF_PATH = f"/repos/{REPOSITORY}/git/ref/tags/"
TAG_OBJECT_PATH = f"/repos/{REPOSITORY}/git/tags/"
STABLE_TAG_PATTERN = re.compile(
    r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
)
FULL_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
MAX_STABLE_TAG_LENGTH = 128
MAX_RELEASE_PAGES = 5
MAX_CANDIDATES = 5
MAX_RESOLVED_IDENTITIES = 6
MAX_TAG_OBJECT_HOPS = 3


def parse_stable_tag(tag: str) -> tuple[int, int, int] | None:
    """Return semantic version components only for strict stable release tags."""
    if not isinstance(tag, str) or len(tag) > MAX_STABLE_TAG_LENGTH:
        return None
    match = STABLE_TAG_PATTERN.fullmatch(tag)
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())


@dataclass(frozen=True, slots=True)
class ReleaseMetadata:
    """Allowlisted fields retained from an official published release."""

    release_id: int
    tag: str
    published_at: datetime


@dataclass(frozen=True, slots=True)
class ReleaseIdentity:
    """Immutable stable release identity with its tag object and peeled commit."""

    release_id: int
    tag: str
    published_at: datetime
    tag_sha: str
    commit_sha: str
    repository: str = REPOSITORY


@dataclass(frozen=True, slots=True)
class DiscoveryState:
    """Pure snapshot of discovery evidence consumed and produced by one scan."""

    has_completed_scan: bool = False
    identities_by_release_id: tuple[tuple[int, str, str], ...] = ()
    tag_commit_shas: tuple[tuple[str, str], ...] = ()
    seen_not_notified: tuple[int, ...] = ()
    pending_release_ids: tuple[int, ...] = ()

    @property
    def identity_map(self) -> dict[int, tuple[str, str]]:
        """Return release ID to its first observed (tag, peeled commit) binding."""
        return {
            release_id: (tag, commit_sha)
            for release_id, tag, commit_sha in self.identities_by_release_id
        }

    @property
    def tag_sha_map(self) -> dict[str, str]:
        """Return the first verified peeled commit for each stable tag."""
        return dict(self.tag_commit_shas)


DiscoveryStatus = Literal["available", "no_change", "blocked", "partial"]


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """One bounded discovery result; only complete results carry new state."""

    status: DiscoveryStatus
    reason_code: str | None
    candidates: tuple[ReleaseIdentity, ...]
    latest_identity: ReleaseIdentity | None
    seen_not_notified: tuple[int, ...]
    pending_release_ids: tuple[int, ...]
    republished_release_ids: tuple[int, ...]
    state: DiscoveryState

# T02 report/evidence schema constants. These allowlists are intentionally closed.
REPORT_SCHEMA = "hermes.update-watch-report/v1"
PROMPT_TEMPLATE_VERSION = "1"
REPORT_MAX_BYTES = 65_536
ALERT_MAX_UTF16_UNITS = 1_900
REPORT_LIFETIME = timedelta(hours=24)
ENVIRONMENT_NAMES = ("dev", "prod")
ENVIRONMENT_CATEGORIES = (
    "source_checkout",
    "runtime_image",
    "effective_config",
    "customizations_mounts_profiles_data_sessions_plugins_skills_integrations",
    "backup_restore",
)
DEV_UNKNOWN_REASONS = frozenset(
    {
        "git_timeout",
        "git_output_limit",
        "git_process_unavailable",
        "git_command_failed",
        "git_output_invalid",
    }
)


class EvidenceField(TypedDict, total=False):
    """One allowlisted category in an environment evidence record."""

    status: str
    reason: str
    sha: str
    dirty: bool
    dirty_count: int


class EnvironmentEvidence(TypedDict):
    """Closed set of target environment categories used in reports."""

    source_checkout: EvidenceField
    runtime_image: EvidenceField
    effective_config: EvidenceField
    customizations_mounts_profiles_data_sessions_plugins_skills_integrations: EvidenceField
    backup_restore: EvidenceField
