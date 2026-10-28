"""Behavior contracts for the standalone Hermes release watcher."""

from __future__ import annotations

import json
from email.message import Message
from io import BytesIO
from typing import Any
from urllib.response import addinfourl
from urllib.request import HTTPSHandler, build_opener

import pytest

from scripts.hermes_update_watch.model import DiscoveryState, parse_stable_tag
from scripts.hermes_update_watch.releases import (
    GitHubReleaseReader,
    ReleaseError,
    discover_releases,
)

API_RELEASES_URL = (
    "https://api.github.com/repos/NousResearch/hermes-agent/releases"
)


class FakeResponse:
    def __init__(
        self,
        body: dict[str, Any] | list[Any],
        *,
        headers: dict[str, str] | None = None,
        url: str = "https://api.github.com/",
    ) -> None:
        self._body = json.dumps(body).encode()
        self.headers = headers or {}
        self._url = url
        self.status = 200

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            raise AssertionError("response must be read with a bound")
        data, self._body = self._body[:size], self._body[size:]
        return data

    def geturl(self) -> str:
        return self._url

    def close(self) -> None:
        pass


class FakeOpener:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[tuple[str, float]] = []

    def open(self, request: Any, timeout: float) -> FakeResponse:
        self.requests.append((request.full_url, timeout))
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        return self.responses.pop(0)


def release(
    release_id: int,
    tag: str,
    published_at: str,
    *,
    draft: bool = False,
    prerelease: bool = False,
) -> dict[str, Any]:
    return {
        "id": release_id,
        "tag_name": tag,
        "published_at": published_at,
        "draft": draft,
        "prerelease": prerelease,
        "name": "UNTRUSTED title",
        "body": "UNTRUSTED body",
    }


def ref(
    tag_sha: str,
    kind: str = "commit",
    *,
    tag: str = "v1.2.3",
) -> dict[str, Any]:
    return {"ref": f"refs/tags/{tag}", "object": {"type": kind, "sha": tag_sha}}


def tag_object(
    tag_sha: str,
    target_sha: str,
    kind: str = "commit",
) -> dict[str, Any]:
    return {
        "sha": tag_sha,
        "object": {"type": kind, "sha": target_sha},
    }


class RawResponse(FakeResponse):
    def __init__(self, body: bytes, *, url: str) -> None:
        self._body = body
        self.headers = {}
        self._url = url
        self.status = 200


class FakeHTTPSHandler(HTTPSHandler):
    """Serve controlled status responses through urllib's real redirect flow."""

    def __init__(self, responses: list[tuple[int, dict[str, str], bytes]]) -> None:
        super().__init__()
        self.responses = list(responses)
        self.requests: list[str] = []

    def https_open(self, request: Any) -> Any:
        self.requests.append(request.full_url)
        if not self.responses:
            raise AssertionError("redirect attempted an additional HTTPS request")
        status, header_values, body = self.responses.pop(0)
        headers = Message()
        for name, value in header_values.items():
            headers[name] = value
        result = addinfourl(BytesIO(body), headers, request.full_url, status)
        result.msg = "controlled response"
        return result


def response(
    value: dict[str, Any] | list[Any],
    *,
    headers: dict[str, str] | None = None,
    url: str = "https://api.github.com/",
) -> FakeResponse:
    return FakeResponse(value, headers=headers, url=url)


def stable_listing(
    release_ids: list[tuple[int, str]],
) -> list[dict[str, Any]]:
    return [
        release(
            release_id,
            tag,
            f"2026-01-{release_id:02d}T00:00:00Z",
        )
        for release_id, tag in release_ids
    ]


def tag_ref_response(tag: str, sha: str) -> FakeResponse:
    return response(
        ref(sha, tag=tag),
        url=f"https://api.github.com/repos/NousResearch/hermes-agent/git/ref/tags/{tag}",
    )


def test_stable_tag_parser_rejects_prereleases_and_leading_zeroes() -> None:
    assert parse_stable_tag("v1.2.3") == (1, 2, 3)
    assert parse_stable_tag("v0.0.0") == (0, 0, 0)
    assert parse_stable_tag("v1.2.3-rc.1") is None
    assert parse_stable_tag("v01.2.3") is None
    assert parse_stable_tag("1.2.3") is None
    assert parse_stable_tag("v1.2.3+build.4") is None


def test_stable_tag_parser_rejects_unbounded_numeric_components() -> None:
    assert parse_stable_tag(f"v{'9' * 5000}.0.0") is None


def test_release_reader_filters_prereleases_and_discards_upstream_text() -> None:
    api = FakeOpener(
        [
            response(
                [
                    release(1, "v1.2.3-rc.1", "2026-01-01T00:00:00Z", prerelease=True),
                    release(2, "v1.2.3", "2026-01-02T00:00:00Z"),
                    release(3, "v2.0.0", "2026-01-03T00:00:00Z", draft=True),
                ],
                url="https://api.github.com/repos/NousResearch/hermes-agent/releases?per_page=100&page=1",
            )
        ]
    )
    reader = GitHubReleaseReader(opener=api)

    releases = reader.list_releases()

    assert [(item.release_id, item.tag) for item in releases] == [(2, "v1.2.3")]
    assert "UNTRUSTED" not in repr(releases)
    assert len(api.requests) == 1
    request_url, timeout = api.requests[0]
    assert request_url == (
        "https://api.github.com/repos/NousResearch/hermes-agent/releases"
        "?per_page=100&page=1"
    )
    assert timeout <= 10


def test_release_reader_rejects_external_pagination_before_requesting_it() -> None:
    api = FakeOpener(
        [
            response(
                [],
                headers={
                    "Link": (
                        '<https://example.com/steal?page=2&per_page=100>; rel="next"'
                    )
                },
                url="https://api.github.com/repos/NousResearch/hermes-agent/releases?per_page=100&page=1",
            )
        ]
    )
    reader = GitHubReleaseReader(opener=api)

    with pytest.raises(ReleaseError) as error:
        reader.list_releases()

    assert error.value.reason_code == "invalid_pagination"
    assert len(api.requests) == 1


def test_annotated_tag_is_peeled_to_commit_with_bounded_requests() -> None:
    tag_sha = "a" * 40
    commit_sha = "b" * 40
    api = FakeOpener(
        [
            response(
                ref(tag_sha, "tag"),
                url="https://api.github.com/repos/NousResearch/hermes-agent/git/ref/tags/v1.2.3",
            ),
            response(
                tag_object(tag_sha, commit_sha),
                url=f"https://api.github.com/repos/NousResearch/hermes-agent/git/tags/{tag_sha}",
            ),
        ]
    )
    reader = GitHubReleaseReader(opener=api)

    result = reader.resolve_tag("v1.2.3")

    assert result == (tag_sha, commit_sha)
    assert len(api.requests) == 2
    assert all(timeout <= 10 for _, timeout in api.requests)


def test_tag_resolution_rejects_cycles_and_non_commit_endpoints() -> None:
    tag_sha = "a" * 40
    api = FakeOpener(
        [
            response(
                ref(tag_sha, "tag"),
                url="https://api.github.com/repos/NousResearch/hermes-agent/git/ref/tags/v1.2.3",
            ),
            response(
                tag_object(tag_sha, tag_sha, "tag"),
                url=f"https://api.github.com/repos/NousResearch/hermes-agent/git/tags/{tag_sha}",
            ),
        ]
    )

    with pytest.raises(ReleaseError) as error:
        GitHubReleaseReader(opener=api).resolve_tag("v1.2.3")

    assert error.value.reason_code == "tag_cycle"


def test_cold_start_selects_only_latest_stable_and_marks_older_seen() -> None:
    listings = [
        release(1, "v1.0.0", "2026-01-01T00:00:00Z"),
        release(2, "v1.1.0", "2026-01-02T00:00:00Z"),
        release(3, "v1.2.0", "2026-01-03T00:00:00Z"),
    ]
    api = FakeOpener(
        [
            response(
                listings,
                url="https://api.github.com/repos/NousResearch/hermes-agent/releases?per_page=100&page=1",
            ),
            tag_ref_response("v1.2.0", "c" * 40),
        ]
    )

    result = discover_releases(GitHubReleaseReader(opener=api))

    assert result.status == "available"
    assert [identity.tag for identity in result.candidates] == ["v1.2.0"]
    assert result.seen_not_notified == (1, 2)
    assert [identity.commit_sha for identity in result.candidates] == ["c" * 40]
    assert len(api.requests) == 2


def test_catch_up_is_oldest_first_and_capped_at_five_plus_latest() -> None:
    releases = [
        release(i, f"v1.{i}.0", f"2026-02-{i:02d}T00:00:00Z")
        for i in range(1, 8)
    ]
    responses = [
        response(
            releases,
            url="https://api.github.com/repos/NousResearch/hermes-agent/releases?per_page=100&page=1",
        )
    ]
    # New candidate releases are 1..7; only the oldest five are resolved.
    responses.extend(
        tag_ref_response(f"v1.{i}.0", f"{i:040x}") for i in range(1, 6)
    )
    # Current latest is added as a separate identity check.
    responses.append(tag_ref_response("v1.7.0", f"{7:040x}"))
    state = DiscoveryState(has_completed_scan=True)
    result = discover_releases(
        GitHubReleaseReader(opener=FakeOpener(responses)),
        previous=state,
    )

    assert result.status == "available"
    assert [identity.release_id for identity in result.candidates] == [1, 2, 3, 4, 5]
    assert result.pending_release_ids == (6, 7)
    assert result.latest_identity is not None
    assert result.latest_identity.release_id == 7


def test_moved_tag_blocks_without_advancing_previous_discovery_state() -> None:
    previous = DiscoveryState(
        has_completed_scan=True,
        identities_by_release_id=((1, "v1.0.0", "a" * 40),),
        tag_commit_shas=(("v1.0.0", "a" * 40),),
    )
    api = FakeOpener(
        [
            response(
                [release(1, "v1.0.0", "2026-01-01T00:00:00Z")],
                url="https://api.github.com/repos/NousResearch/hermes-agent/releases?per_page=100&page=1",
            ),
            tag_ref_response("v1.0.0", "b" * 40),
        ]
    )

    result = discover_releases(GitHubReleaseReader(opener=api), previous)

    assert result.status == "blocked"
    assert result.reason_code == "tag_moved"
    assert result.state == previous


def test_republished_release_with_same_tag_and_commit_is_not_alerted_again() -> None:
    previous = DiscoveryState(
        has_completed_scan=True,
        identities_by_release_id=((1, "v1.0.0", "a" * 40),),
        tag_commit_shas=(("v1.0.0", "a" * 40),),
    )
    api = FakeOpener(
        [
            response(
                [
                    release(1, "v1.0.0", "2026-01-01T00:00:00Z"),
                    release(2, "v1.0.0", "2026-01-02T00:00:00Z"),
                ],
                url="https://api.github.com/repos/NousResearch/hermes-agent/releases?per_page=100&page=1",
            ),
            tag_ref_response("v1.0.0", "a" * 40),
            tag_ref_response("v1.0.0", "a" * 40),
        ]
    )

    result = discover_releases(GitHubReleaseReader(opener=api), previous)

    assert result.status == "no_change"
    assert result.candidates == ()
    assert result.republished_release_ids == (2,)


def test_release_schema_rejects_bool_release_id_and_bad_timestamp() -> None:
    for invalid in (
        release(True, "v1.2.3", "2026-01-01T00:00:00Z"),
        release(2, "v1.2.3", "not-a-date"),
    ):
        reader = GitHubReleaseReader(
            opener=FakeOpener(
                [
                    response(
                        [invalid],
                        url="https://api.github.com/repos/NousResearch/hermes-agent/releases?per_page=100&page=1",
                    )
                ]
            )
        )
        result = discover_releases(reader)
        assert result.status == "blocked"
        assert result.reason_code == "invalid_release_metadata"


def test_no_stable_release_is_blocked_not_no_change() -> None:
    api = FakeOpener(
        [
            response(
                [release(1, "v1.2.3-rc.1", "2026-01-01T00:00:00Z", prerelease=True)],
                url="https://api.github.com/repos/NousResearch/hermes-agent/releases?per_page=100&page=1",
            )
        ]
    )

    result = discover_releases(GitHubReleaseReader(opener=api))

    assert result.status == "blocked"
    assert result.reason_code == "no_verified_stable_release"
def test_seen_not_notified_cold_start_releases_stay_suppressed() -> None:
    listings = [
        release(1, "v1.0.0", "2026-01-01T00:00:00Z"),
        release(2, "v1.1.0", "2026-01-02T00:00:00Z"),
    ]
    cold_api = FakeOpener(
        [
            response(
                listings,
                url="https://api.github.com/repos/NousResearch/hermes-agent/releases?per_page=100&page=1",
            ),
            tag_ref_response("v1.1.0", "b" * 40),
        ]
    )
    first = discover_releases(GitHubReleaseReader(opener=cold_api))
    assert first.state.seen_not_notified == (1,)

    next_api = FakeOpener(
        [
            response(
                listings,
                url="https://api.github.com/repos/NousResearch/hermes-agent/releases?per_page=100&page=1",
            ),
            tag_ref_response("v1.1.0", "b" * 40),
        ]
    )
    second = discover_releases(
        GitHubReleaseReader(opener=next_api),
        first.state,
    )

    assert second.status == "no_change"
    assert second.candidates == ()
    assert second.state.seen_not_notified == (1,)


def test_pending_overflow_remains_alertable_after_latest_was_verified() -> None:
    releases = stable_listing([(i, f"v1.{i}.0") for i in range(1, 8)])
    first_responses = [
        response(
            releases,
            url="https://api.github.com/repos/NousResearch/hermes-agent/releases?per_page=100&page=1",
        )
    ]
    first_responses.extend(
        tag_ref_response(f"v1.{i}.0", f"{i:040x}") for i in range(1, 6)
    )
    first_responses.append(tag_ref_response("v1.7.0", f"{7:040x}"))
    first = discover_releases(
        GitHubReleaseReader(opener=FakeOpener(first_responses)),
        DiscoveryState(has_completed_scan=True),
    )
    assert first.pending_release_ids == (6, 7)

    next_responses = [
        response(
            releases,
            url="https://api.github.com/repos/NousResearch/hermes-agent/releases?per_page=100&page=1",
        ),
        tag_ref_response("v1.6.0", f"{6:040x}"),
        tag_ref_response("v1.7.0", f"{7:040x}"),
    ]
    second = discover_releases(
        GitHubReleaseReader(opener=FakeOpener(next_responses)),
        first.state,
    )

    assert [item.release_id for item in second.candidates] == [6, 7]
    assert second.pending_release_ids == ()


def test_release_reader_stops_at_five_pages_without_claiming_complete_scan() -> None:
    responses = []
    for page in range(1, 6):
        headers = (
            {"Link": f'<{API_RELEASES_URL}?per_page=100&page={page + 1}>; rel="next"'}
            if page < 5
            else {"Link": f'<{API_RELEASES_URL}?per_page=100&page=6>; rel="next"'}
        )
        responses.append(
            response(
                [],
                headers=headers,
                url=f"{API_RELEASES_URL}?per_page=100&page={page}",
            )
        )
    api = FakeOpener(responses)

    result = discover_releases(GitHubReleaseReader(opener=api))

    assert result.status == "partial"
    assert result.reason_code == "incomplete_pagination"
    assert len(api.requests) == 5


def test_release_reader_rejects_oversized_json_body() -> None:
    api = FakeOpener(
        [
            FakeResponse(
                [{"ignored": "x" * (2 * 1024 * 1024)}],
                url="https://api.github.com/repos/NousResearch/hermes-agent/releases?per_page=100&page=1",
            )
        ]
    )

    with pytest.raises(ReleaseError) as error:
        GitHubReleaseReader(opener=api).list_releases()

    assert error.value.reason_code == "response_too_large"


def test_same_host_redirect_to_another_api_route_is_rejected() -> None:
    api = FakeOpener(
        [
            response(
                [],
                url="https://api.github.com/repos/NousResearch/hermes-agent/git/ref/tags/v1.2.3",
            )
        ]
    )

    with pytest.raises(ReleaseError) as error:
        GitHubReleaseReader(opener=api).list_releases()

    assert error.value.reason_code == "unexpected_redirect"


def test_release_id_cannot_change_tag_even_when_not_selected() -> None:
    previous = DiscoveryState(
        has_completed_scan=True,
        identities_by_release_id=((1, "v1.0.0", "a" * 40),),
        tag_commit_shas=(("v1.0.0", "a" * 40),),
    )
    api = FakeOpener(
        [
            response(
                [
                    release(1, "v1.0.1", "2026-01-01T00:00:00Z"),
                    release(2, "v1.2.0", "2026-01-02T00:00:00Z"),
                ],
                url="https://api.github.com/repos/NousResearch/hermes-agent/releases?per_page=100&page=1",
            )
        ]
    )

    result = discover_releases(GitHubReleaseReader(opener=api), previous)

    assert result.status == "blocked"
    assert result.reason_code == "identity_changed"
    assert result.state == previous
def test_http_rate_limit_is_blocked_without_leaking_response_text() -> None:
    rate_limited = response(
        {"message": "do not expose upstream body"},
        url=f"{API_RELEASES_URL}?per_page=100&page=1",
    )
    rate_limited.status = 429
    api = FakeOpener([rate_limited])

    result = discover_releases(GitHubReleaseReader(opener=api))

    assert result.status == "blocked"
    assert result.reason_code == "upstream_rate_limited"
    assert "do not expose" not in repr(result)


def test_annotated_tag_resolution_stops_after_three_tag_objects() -> None:
    sha_values = [f"{index:040x}" for index in range(1, 5)]
    responses = [
        response(
            ref(sha_values[0], "tag"),
            url="https://api.github.com/repos/NousResearch/hermes-agent/git/ref/tags/v1.2.3",
        )
    ]
    responses.extend(
        response(
            tag_object(sha_values[index - 1], sha_values[index], "tag"),
            url=f"https://api.github.com/repos/NousResearch/hermes-agent/git/tags/{sha_values[index - 1]}",
        )
        for index in range(1, 4)
    )
    api = FakeOpener(responses)

    with pytest.raises(ReleaseError) as error:
        GitHubReleaseReader(opener=api).resolve_tag("v1.2.3")

    assert error.value.reason_code == "tag_depth_exceeded"
    assert len(api.requests) == 4


def test_release_reader_enforces_total_request_budget() -> None:
    api = FakeOpener(
        [
            response(
                ref("a" * 40),
                url="https://api.github.com/repos/NousResearch/hermes-agent/git/ref/tags/v1.2.3",
            )
            for _ in range(29)
        ]
    )
    reader = GitHubReleaseReader(opener=api)

    for _ in range(29):
        assert reader.resolve_tag("v1.2.3") == ("a" * 40, "a" * 40)
    with pytest.raises(ReleaseError) as error:
        reader.resolve_tag("v1.2.3")

    assert error.value.reason_code == "request_budget_exceeded"
    assert len(api.requests) == 29
def test_release_reader_sanitizes_malformed_final_url() -> None:
    api = FakeOpener(
        [
            response(
                [],
                url="https://api.github.com:not-a-port/repos/NousResearch/hermes-agent/releases?per_page=100&page=1",
            )
        ]
    )

    result = discover_releases(GitHubReleaseReader(opener=api))

    assert result.status == "blocked"
    assert result.reason_code == "invalid_api_url"


def test_release_reader_sanitizes_body_read_timeout() -> None:
    class TimedOutResponse(FakeResponse):
        def read(self, size: int = -1) -> bytes:
            raise TimeoutError("private network detail")

    api = FakeOpener(
        [
            TimedOutResponse(
                [],
                url=f"{API_RELEASES_URL}?per_page=100&page=1",
            )
        ]
    )

    result = discover_releases(GitHubReleaseReader(opener=api))

    assert result.status == "blocked"
    assert result.reason_code == "upstream_unavailable"
    assert "private network detail" not in repr(result)
def test_republished_release_in_overflow_stays_suppressed_across_scans() -> None:
    previous = DiscoveryState(
        has_completed_scan=True,
        identities_by_release_id=((1, "v1.1.0", "a" * 40),),
        tag_commit_shas=(("v1.1.0", "a" * 40),),
    )
    releases = [
        release(1, "v1.1.0", "2026-01-01T00:00:00Z"),
        *[
            release(i, f"v1.{i}.0", f"2026-01-0{i}T00:00:00Z")
            for i in range(2, 8)
        ],
        release(8, "v1.1.0", "2026-01-08T00:00:00Z"),
    ]
    first_responses = [
        response(
            releases,
            url=f"{API_RELEASES_URL}?per_page=100&page=1",
        ),
        *[
            tag_ref_response(f"v1.{i}.0", f"{i:040x}")
            for i in range(2, 7)
        ],
        tag_ref_response("v1.1.0", "a" * 40),
    ]
    first = discover_releases(
        GitHubReleaseReader(opener=FakeOpener(first_responses)),
        previous,
    )

    assert [identity.release_id for identity in first.candidates] == [2, 3, 4, 5, 6]
    assert first.republished_release_ids == (8,)
    assert first.pending_release_ids == (7,)

    next_responses = [
        response(releases, url=f"{API_RELEASES_URL}?per_page=100&page=1"),
        tag_ref_response("v1.7.0", f"{7:040x}"),
        tag_ref_response("v1.1.0", "a" * 40),
    ]
    second = discover_releases(
        GitHubReleaseReader(opener=FakeOpener(next_responses)),
        first.state,
    )

    assert [identity.release_id for identity in second.candidates] == [7]
    assert 8 not in second.pending_release_ids
    assert 8 not in second.republished_release_ids


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (
            b'[{"id":' + b"9" * 5000
            + b',"tag_name":"v1.2.3","draft":false,"prerelease":false,'
            + b'"published_at":"2026-01-01T00:00:00Z"}]',
            "invalid_json_response",
        ),
        (b"[" * 100_000 + b"0" + b"]" * 100_000, "invalid_json_response"),
    ],
    ids=["large_integer", "deep_nesting"],
)
def test_release_reader_sanitizes_json_integer_and_nesting_limits(
    body: bytes,
    reason: str,
) -> None:
    api = FakeOpener(
        [RawResponse(body, url=f"{API_RELEASES_URL}?per_page=100&page=1")]
    )

    result = discover_releases(GitHubReleaseReader(opener=api))

    assert result.status == "blocked"
    assert result.reason_code == reason
    assert "9" * 100 not in repr(result)


def test_release_reader_sanitizes_timestamp_timezone_underflow() -> None:
    api = FakeOpener(
        [
            response(
                [release(1, "v1.2.3", "0001-01-01T00:00:00+01:00")],
                url=f"{API_RELEASES_URL}?per_page=100&page=1",
            )
        ]
    )

    result = discover_releases(GitHubReleaseReader(opener=api))

    assert result.status == "blocked"
    assert result.reason_code == "invalid_release_metadata"


def test_tag_ref_must_match_the_requested_stable_tag() -> None:
    api = FakeOpener(
        [
            response(
                ref("a" * 40, tag="v99.99.99"),
                url="https://api.github.com/repos/NousResearch/hermes-agent/git/ref/tags/v1.2.3",
            )
        ]
    )

    with pytest.raises(ReleaseError) as error:
        GitHubReleaseReader(opener=api).resolve_tag("v1.2.3")

    assert error.value.reason_code == "tag_ref_mismatch"


def test_annotated_tag_response_sha_must_match_requested_object() -> None:
    requested_sha = "a" * 40
    api = FakeOpener(
        [
            response(
                ref(requested_sha, "tag"),
                url="https://api.github.com/repos/NousResearch/hermes-agent/git/ref/tags/v1.2.3",
            ),
            response(
                tag_object("b" * 40, "c" * 40),
                url=f"https://api.github.com/repos/NousResearch/hermes-agent/git/tags/{requested_sha}",
            ),
        ]
    )

    with pytest.raises(ReleaseError) as error:
        GitHubReleaseReader(opener=api).resolve_tag("v1.2.3")

    assert error.value.reason_code == "tag_object_mismatch"


@pytest.mark.parametrize(
    "target",
    [
        "https://attacker.example/collect",
        "https://api.github.com/repos/NousResearch/hermes-agent/git/tags/"
        + "a" * 40,
    ],
)
def test_redirects_are_rejected_before_a_second_https_request(
    target: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.hermes_update_watch import releases as releases_module

    fake_https = FakeHTTPSHandler(
        [
            (
                302,
                {"Location": target},
                b"",
            )
        ]
    )
    monkeypatch.setattr(
        releases_module,
        "build_opener",
        lambda handler: build_opener(fake_https, handler),
    )

    result = discover_releases(GitHubReleaseReader())

    assert result.status == "blocked"
    assert result.reason_code == "redirect_rejected"
    assert len(fake_https.requests) == 1
    assert fake_https.requests[0].startswith("https://api.github.com/")
def test_pending_republication_is_suppressed_when_not_latest() -> None:
    previous = DiscoveryState(
        has_completed_scan=True,
        identities_by_release_id=((1, "v1.1.0", "a" * 40),),
        tag_commit_shas=(("v1.1.0", "a" * 40),),
        pending_release_ids=(8,),
    )
    releases = [
        release(1, "v1.1.0", "2026-01-01T00:00:00Z"),
        release(8, "v1.1.0", "2026-01-08T00:00:00Z"),
        release(9, "v1.9.0", "2026-01-09T00:00:00Z"),
    ]
    api = FakeOpener(
        [
            response(releases, url=f"{API_RELEASES_URL}?per_page=100&page=1"),
            tag_ref_response("v1.1.0", "a" * 40),
            tag_ref_response("v1.9.0", "b" * 40),
        ]
    )

    result = discover_releases(
        GitHubReleaseReader(opener=api),
        previous,
    )

    assert [identity.release_id for identity in result.candidates] == [9]
    assert result.pending_release_ids == ()
    assert result.republished_release_ids == (8,)
