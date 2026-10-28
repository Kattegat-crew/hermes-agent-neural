"""Bounded, anonymous GitHub release discovery and tag verification."""

from __future__ import annotations

import json
import re
import time
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urljoin, urlparse, urlunparse
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

from .model import (
    API_ROOT,
    FULL_SHA_PATTERN,
    MAX_CANDIDATES,
    MAX_RELEASE_PAGES,
    MAX_RESOLVED_IDENTITIES,
    MAX_TAG_OBJECT_HOPS,
    RELEASES_PATH,
    TAG_OBJECT_PATH,
    TAG_REF_PATH,
    DiscoveryResult,
    DiscoveryState,
    ReleaseIdentity,
    ReleaseMetadata,
    parse_stable_tag,
)

MAX_REQUESTS = 29
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_RESPONSE_BYTES = 14 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 10.0
RUN_DEADLINE_SECONDS = 90.0
PAGE_SIZE = 100
_READ_CHUNK_SIZE = 64 * 1024
_NEXT_LINK = re.compile(r"<([^>]+)>\s*;\s*rel=\"?next\"?", re.IGNORECASE)
_HEX_SHA = re.compile(FULL_SHA_PATTERN)


class ReleaseError(Exception):
    """A sanitized, stable release-source failure with no upstream text."""

    def __init__(self, reason_code: str, status: str = "blocked") -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.status = status


class Response(Protocol):
    """Minimal response interface used by urllib and deterministic tests."""

    headers: Any
    status: int

    def read(self, size: int = -1) -> bytes: ...
    def geturl(self) -> str: ...
    def close(self) -> None: ...


class Opener(Protocol):
    """Minimal standard-library opener seam."""

    def open(self, request: Request, timeout: float) -> Response: ...


class _RejectRedirectHandler(HTTPRedirectHandler):
    """Reject redirects before urllib can issue a second physical request."""

    def redirect_request(
        self,
        request: Request,
        fp: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> Request:
        raise ReleaseError("redirect_rejected")


def _validate_api_url(url: str, *, allow_tag_object: bool) -> str:
    """Validate fixed-host API URL and reject ambiguous URL components."""
    try:
        parsed = urlparse(url)
        port = parsed.port
        query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    except (TypeError, ValueError):
        raise ReleaseError("invalid_api_url") from None
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.github.com"
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.fragment
    ):
        raise ReleaseError("invalid_api_url")
    if parsed.path == RELEASES_PATH:
        allowed_query = {"page", "per_page"}
    elif parsed.path.startswith(TAG_REF_PATH):
        allowed_query = set()
    elif allow_tag_object and parsed.path.startswith(TAG_OBJECT_PATH):
        allowed_query = set()
    else:
        raise ReleaseError("invalid_api_url")
    if set(query) != allowed_query:
        raise ReleaseError("invalid_api_url")
    if parsed.path == RELEASES_PATH:
        if (
            query.get("per_page") != [str(PAGE_SIZE)]
            or len(query.get("page", [])) != 1
            or not query["page"][0].isdigit()
            or int(query["page"][0]) < 1
        ):
            raise ReleaseError("invalid_api_url")
    return url


class GitHubReleaseReader:
    """Read public releases with fixed endpoints and per-run resource budgets."""

    def __init__(
        self,
        *,
        opener: Opener | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._opener = opener or build_opener(_RejectRedirectHandler())
        self._clock = clock
        self._started_at = clock()
        self._request_count = 0
        self._total_bytes = 0

    def list_releases(self) -> tuple[ReleaseMetadata, ...]:
        """Read at most five release pages and retain only stable release facts."""
        url = f"{API_ROOT}{RELEASES_PATH}?per_page={PAGE_SIZE}&page=1"
        releases: list[ReleaseMetadata] = []
        seen_pages: set[str] = set()

        for page_number in range(1, MAX_RELEASE_PAGES + 1):
            url = _validate_api_url(url, allow_tag_object=False)
            if url in seen_pages:
                raise ReleaseError("pagination_cycle", "partial")
            seen_pages.add(url)
            payload, headers = self._request_json(url)
            if not isinstance(payload, list):
                raise ReleaseError("invalid_release_response")
            for item in payload:
                parsed = _parse_release(item)
                if parsed is not None:
                    releases.append(parsed)

            next_url = _next_page_url(headers, url, page_number)
            if next_url is None:
                return tuple(
                    sorted(
                        releases,
                        key=lambda item: (item.published_at, item.release_id),
                    )
                )
            if page_number == MAX_RELEASE_PAGES:
                raise ReleaseError("incomplete_pagination", "partial")
            url = next_url

        raise ReleaseError("incomplete_pagination", "partial")

    def resolve_tag(self, tag: str) -> tuple[str, str]:
        """Resolve one stable tag to its tag-object SHA and peeled commit SHA."""
        if parse_stable_tag(tag) is None:
            raise ReleaseError("invalid_stable_tag")
        encoded_tag = quote(tag, safe="")
        ref_url = f"{API_ROOT}{TAG_REF_PATH}{encoded_tag}"
        payload, _ = self._request_json(ref_url)
        if not isinstance(payload, dict) or payload.get("ref") != f"refs/tags/{tag}":
            raise ReleaseError("tag_ref_mismatch")
        obj = payload.get("object") if isinstance(payload, dict) else None
        if not isinstance(obj, dict):
            raise ReleaseError("invalid_tag_ref")
        tag_sha = _require_sha(obj.get("sha"))
        kind = obj.get("type")
        if kind == "commit":
            return tag_sha, tag_sha
        if kind != "tag":
            raise ReleaseError("unsupported_tag_object")

        current_sha = tag_sha
        visited: set[str] = set()
        for _ in range(MAX_TAG_OBJECT_HOPS):
            if current_sha in visited:
                raise ReleaseError("tag_cycle")
            visited.add(current_sha)
            tag_url = f"{API_ROOT}{TAG_OBJECT_PATH}{current_sha}"
            tag_payload, _ = self._request_json(tag_url)
            if not isinstance(tag_payload, dict):
                raise ReleaseError("invalid_tag_object")
            response_sha = _require_sha(tag_payload.get("sha"))
            if response_sha != current_sha:
                raise ReleaseError("tag_object_mismatch")
            target = tag_payload.get("object")
            if not isinstance(target, dict):
                raise ReleaseError("invalid_tag_object")
            target_sha = _require_sha(target.get("sha"))
            target_kind = target.get("type")
            if target_kind == "commit":
                return tag_sha, target_sha
            if target_kind != "tag":
                raise ReleaseError("unsupported_tag_object")
            current_sha = target_sha
        raise ReleaseError("tag_depth_exceeded")

    def _request_json(self, url: str) -> tuple[Any, Any]:
        """Fetch one bounded JSON response without exposing response content."""
        _validate_api_url(url, allow_tag_object=True)
        if self._request_count >= MAX_REQUESTS:
            raise ReleaseError("request_budget_exceeded", "partial")
        remaining = RUN_DEADLINE_SECONDS - (self._clock() - self._started_at)
        if remaining <= 0:
            raise ReleaseError("run_deadline_exceeded", "partial")
        self._request_count += 1
        request = Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "Hermes-Update-Watch/1",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="GET",
        )
        try:
            response = self._opener.open(
                request, timeout=min(REQUEST_TIMEOUT_SECONDS, remaining)
            )
        except HTTPError as error:
            if error.code in (403, 429):
                raise ReleaseError("upstream_rate_limited") from None
            raise ReleaseError("upstream_unavailable") from None
        except (URLError, TimeoutError, OSError):
            raise ReleaseError("upstream_unavailable") from None

        with closing(response):
            final_url = response.geturl()
            _validate_api_url(final_url, allow_tag_object=True)
            requested = urlparse(url)
            returned = urlparse(final_url)
            if (returned.path, returned.query) != (requested.path, requested.query):
                raise ReleaseError("unexpected_redirect")
            status = getattr(response, "status", 200)
            if not isinstance(status, int) or isinstance(status, bool):
                raise ReleaseError("invalid_http_status")
            if status in (403, 429):
                raise ReleaseError("upstream_rate_limited")
            if not 200 <= status < 300:
                raise ReleaseError("upstream_unavailable")
            try:
                body = self._read_bounded(response)
            except ReleaseError:
                raise
            except (OSError, TimeoutError, URLError):
                raise ReleaseError("upstream_unavailable") from None
            try:
                return json.loads(body), response.headers
            except (UnicodeDecodeError, ValueError, RecursionError):
                raise ReleaseError("invalid_json_response") from None

    def _read_bounded(self, response: Response) -> bytes:
        chunks: list[bytes] = []
        response_bytes = 0
        while True:
            remaining_time = RUN_DEADLINE_SECONDS - (
                self._clock() - self._started_at
            )
            if remaining_time <= 0:
                raise ReleaseError("run_deadline_exceeded", "partial")
            remaining_response = MAX_RESPONSE_BYTES + 1 - response_bytes
            if remaining_response <= 0:
                raise ReleaseError("response_too_large", "partial")
            chunk = response.read(min(_READ_CHUNK_SIZE, remaining_response))
            if not isinstance(chunk, bytes):
                raise ReleaseError("invalid_response_body")
            if not chunk:
                break
            response_bytes += len(chunk)
            self._total_bytes += len(chunk)
            chunks.append(chunk)
            if response_bytes > MAX_RESPONSE_BYTES:
                raise ReleaseError("response_too_large", "partial")
            if self._total_bytes > MAX_TOTAL_RESPONSE_BYTES:
                raise ReleaseError("response_budget_exceeded", "partial")
        return b"".join(chunks)


def _parse_release(item: Any) -> ReleaseMetadata | None:
    """Validate required release metadata and discard all unapproved fields."""
    if not isinstance(item, dict):
        raise ReleaseError("invalid_release_metadata")
    release_id = item.get("id")
    tag = item.get("tag_name")
    draft = item.get("draft")
    prerelease = item.get("prerelease")
    if (
        not isinstance(release_id, int)
        or isinstance(release_id, bool)
        or release_id <= 0
        or not isinstance(tag, str)
        or not isinstance(draft, bool)
        or not isinstance(prerelease, bool)
    ):
        raise ReleaseError("invalid_release_metadata")
    if draft or prerelease or parse_stable_tag(tag) is None:
        return None
    published_at = _parse_timestamp(item.get("published_at"))
    return ReleaseMetadata(release_id, tag, published_at)


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ReleaseError("invalid_release_metadata")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ReleaseError("invalid_release_metadata")
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ReleaseError("invalid_release_metadata") from None


def _require_sha(value: Any) -> str:
    if not isinstance(value, str) or _HEX_SHA.fullmatch(value) is None:
        raise ReleaseError("invalid_git_sha")
    return value.lower()


def _next_page_url(headers: Any, current_url: str, page_number: int) -> str | None:
    """Read a single, sequential, same-endpoint GitHub pagination link."""
    links = headers.get("Link", "") if headers is not None else ""
    if not isinstance(links, str):
        raise ReleaseError("invalid_pagination", "partial")
    matches = _NEXT_LINK.findall(links)
    if not matches:
        return None
    if len(matches) != 1:
        raise ReleaseError("invalid_pagination", "partial")
    next_url = urljoin(current_url, matches[0])
    try:
        validated_url = _validate_api_url(next_url, allow_tag_object=False)
    except ReleaseError:
        raise ReleaseError("invalid_pagination", "partial") from None
    parsed = urlparse(validated_url)
    query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    if query.get("page") != [str(page_number + 1)]:
        raise ReleaseError("invalid_pagination", "partial")
    return urlunparse(parsed)


def _identity(
    release: ReleaseMetadata, tag_sha: str, commit_sha: str
) -> ReleaseIdentity:
    return ReleaseIdentity(
        release_id=release.release_id,
        tag=release.tag,
        published_at=release.published_at,
        tag_sha=tag_sha,
        commit_sha=commit_sha,
    )


def discover_releases(
    reader: GitHubReleaseReader,
    previous: DiscoveryState = DiscoveryState(),
) -> DiscoveryResult:
    """Produce a complete, bounded discovery snapshot or preserve prior state."""
    try:
        releases = reader.list_releases()
        if not releases:
            raise ReleaseError("no_verified_stable_release")
        return _discover_complete(reader, releases, previous)
    except ReleaseError as error:
        return DiscoveryResult(
            status=error.status,  # type: ignore[arg-type]
            reason_code=error.reason_code,
            candidates=(),
            latest_identity=None,
            seen_not_notified=(),
            pending_release_ids=previous.pending_release_ids,
            republished_release_ids=(),
            state=previous,
        )


def _discover_complete(
    reader: GitHubReleaseReader,
    releases: tuple[ReleaseMetadata, ...],
    previous: DiscoveryState,
) -> DiscoveryResult:
    by_id = {release.release_id: release for release in releases}
    if len(by_id) != len(releases):
        raise ReleaseError("duplicate_release_id")
    latest = releases[-1]
    old_identities = previous.identity_map
    old_tags = previous.tag_sha_map
    old_seen = set(previous.seen_not_notified)

    for release in releases:
        existing = old_identities.get(release.release_id)
        if existing is not None and existing[0] != release.tag:
            raise ReleaseError("identity_changed")

    if not previous.has_completed_scan:
        candidate_ids = [latest.release_id]
        seen_not_notified = tuple(
            sorted(old_seen | {release.release_id for release in releases[:-1]})
        )
        pending = ()
    else:
        seen_not_notified = tuple(sorted(old_seen))
        pending_set = set(previous.pending_release_ids)
        if any(release_id not in by_id for release_id in pending_set):
            raise ReleaseError("pending_release_missing", "partial")
        new_ids = [
            release.release_id
            for release in releases
            if release.release_id not in old_identities
            and release.release_id not in pending_set
            and release.release_id not in old_seen
        ]
        queue = sorted(
            pending_set | set(new_ids),
            key=lambda release_id: (
                by_id[release_id].published_at,
                release_id,
            ),
        )
        candidate_ids = queue[:MAX_CANDIDATES]
        pending = tuple(queue[MAX_CANDIDATES:])

    ids_to_resolve = list(candidate_ids)
    if latest.release_id not in ids_to_resolve:
        if len(ids_to_resolve) >= MAX_RESOLVED_IDENTITIES:
            raise ReleaseError("identity_budget_exceeded", "partial")
        ids_to_resolve.append(latest.release_id)

    resolved: dict[int, ReleaseIdentity] = {}
    for release_id in ids_to_resolve:
        metadata = by_id[release_id]
        existing = old_identities.get(release_id)
        if existing is not None and existing[0] != metadata.tag:
            raise ReleaseError("identity_changed")
        tag_sha, commit_sha = reader.resolve_tag(metadata.tag)
        bound_commit = old_tags.get(metadata.tag)
        if bound_commit is not None and bound_commit != commit_sha:
            raise ReleaseError("tag_moved")
        if existing is not None and existing[1] != commit_sha:
            raise ReleaseError("identity_changed")
        resolved[release_id] = _identity(metadata, tag_sha, commit_sha)

    republished: list[int] = []
    candidates: list[ReleaseIdentity] = []
    tag_seen = dict(old_tags)
    identity_seen = dict(old_identities)
    for release_id in ids_to_resolve:
        identity = resolved[release_id]
        prior_identity_for_tag = tag_seen.get(identity.tag)
        if prior_identity_for_tag is not None and release_id not in old_identities:
            republished.append(release_id)
        else:
            tag_seen[identity.tag] = identity.commit_sha
        previous_for_id = identity_seen.get(release_id)
        if previous_for_id is None:
            identity_seen[release_id] = (identity.tag, identity.commit_sha)
        if release_id in candidate_ids:
            is_republication = (
                release_id not in old_identities and prior_identity_for_tag is not None
            )
            if not is_republication:
                candidates.append(identity)

    republished_set = set(republished)
    pending = tuple(
        release_id for release_id in pending if release_id not in republished_set
    )

    if previous.has_completed_scan:
        candidates.sort(key=lambda item: (item.published_at, item.release_id))
    state = DiscoveryState(
        has_completed_scan=True,
        identities_by_release_id=tuple(
            sorted(
                (
                    release_id,
                    tag,
                    commit_sha,
                )
                for release_id, (tag, commit_sha) in identity_seen.items()
            )
        ),
        tag_commit_shas=tuple(sorted(tag_seen.items())),
        seen_not_notified=seen_not_notified,
        pending_release_ids=tuple(pending),
    )
    return DiscoveryResult(
        status="available" if candidates else "no_change",
        reason_code=None,
        candidates=tuple(candidates),
        latest_identity=resolved[latest.release_id],
        seen_not_notified=seen_not_notified,
        pending_release_ids=tuple(pending),
        republished_release_ids=tuple(sorted(republished)),
        state=state,
    )
