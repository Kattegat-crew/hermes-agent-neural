"""Secret-free environment evidence and immutable update-watch reports."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from urllib.parse import quote

from . import model
from .process import BoundedProcessResult, run_bounded_process

_GIT_ENV = {
    "PATH": "/usr/bin:/bin",
    "HOME": "/nonexistent",
    "LC_ALL": "C",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_TERMINAL_PROMPT": "0",
}
_GIT_PREFIX = (
    "/usr/bin/git",
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "core.fsmonitor=false",
    "-c",
    "core.untrackedCache=false",
    "-c",
    "core.pager=cat",
    "-c",
    "core.quotePath=true",
    "-C",
    "/opt/hermes-agent",
)
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_RFC3339_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_TRACKED_STATUS_CHARS = frozenset(b" MADRCTU")


class ReportValidationError(ValueError):
    """Sanitized validation failure; never includes rejected input values."""

    def __init__(self, reason_code: str = "invalid_report") -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


def collect_environment_evidence(
    *, runner: Callable[..., BoundedProcessResult] | None = None
) -> dict[str, dict[str, dict[str, Any]]]:
    """Collect only fixed local DEV Git facts; PROD and unknowns stay explicit."""
    execute = runner if runner is not None else run_bounded_process
    head = _run_git(execute, (*_GIT_PREFIX, "rev-parse", "--verify", "HEAD^{commit}"))
    status = _run_git(execute, (*_GIT_PREFIX, "status", "--porcelain=v1", "--untracked-files=all"))
    source = _source_checkout_evidence(head, status)
    dev = {"source_checkout": source}
    for category in model.ENVIRONMENT_CATEGORIES[1:]:
        reason = "running_artifact_not_proven" if category == "runtime_image" else "not_collected"
        dev[category] = {"status": "unknown", "reason": reason}
    prod = {
        category: {"status": "unknown", "reason": "not_authorized_or_unavailable"}
        for category in model.ENVIRONMENT_CATEGORIES
    }
    return {"dev": dev, "prod": prod}


def _run_git(runner: Callable[..., Any], argv: tuple[str, ...]) -> Any:
    try:
        return runner(
            argv,
            env=dict(_GIT_ENV),
            timeout_seconds=5,
            stdout_limit=65_536,
            stderr_limit=4_096,
        )
    except Exception:
        return BoundedProcessResult(None, b"", b"", "process_unavailable")


def _source_checkout_evidence(head: Any, status: Any) -> dict[str, Any]:
    for result in (head, status):
        if not isinstance(result, BoundedProcessResult):
            return {"status": "unknown", "reason": "git_output_invalid"}
        if result.reason_code is not None:
            mapping = {
                "timeout": "git_timeout",
                "stdout_limit_exceeded": "git_output_limit",
                "stderr_limit_exceeded": "git_output_limit",
                "process_unavailable": "git_process_unavailable",
                "invalid_process_request": "git_process_unavailable",
            }
            return {"status": "unknown", "reason": mapping.get(result.reason_code, "git_process_unavailable")}
        if result.returncode != 0:
            return {"status": "unknown", "reason": "git_command_failed"}
        if len(result.stdout) > 65_536 or len(result.stderr) > 4_096:
            return {"status": "unknown", "reason": "git_output_limit"}

    try:
        sha_text = head.stdout.decode("ascii", errors="strict")
        if not sha_text.endswith("\n") or sha_text.count("\n") != 1:
            raise ValueError
        sha = sha_text[:-1]
        if _SHA_RE.fullmatch(sha) is None:
            raise ValueError
        dirty_count = _count_porcelain_rows(status.stdout)
    except (UnicodeDecodeError, ValueError):
        return {"status": "unknown", "reason": "git_output_invalid"}

    return {
        "status": "observed",
        "reason": "read_only_git_observation",
        "sha": sha,
        "dirty": dirty_count > 0,
        "dirty_count": dirty_count,
    }


def _count_porcelain_rows(output: bytes) -> int:
    if not output:
        return 0
    if not output.endswith(b"\n"):
        raise ValueError
    rows = output[:-1].split(b"\n")
    for row in rows:
        if len(row) < 4 or row[2:3] != b" " or not row[3:]:
            raise ValueError
        pair = row[:2]
        if pair in (b"??", b"!!"):
            continue
        if pair == b"  " or any(character not in _TRACKED_STATUS_CHARS for character in pair):
            raise ValueError
    return len(rows)


def build_report(
    release: model.ReleaseIdentity,
    environments: Any,
    *,
    now: datetime | None = None,
    report_id: str | None = None,
) -> dict[str, Any]:
    """Build, validate, and digest one 24-hour report from allowlisted inputs."""
    source = _validated_release(release)
    clean_environments = _validate_environments(environments)
    created = _format_utc(now if now is not None else datetime.now(timezone.utc))
    created_dt = _parse_utc(created)
    if _parse_utc(source["published_at"]) > created_dt:
        raise ReportValidationError("invalid_timestamp")
    try:
        expires_at = created_dt + model.REPORT_LIFETIME
    except OverflowError:
        raise ReportValidationError("invalid_timestamp") from None
    expires = _format_utc(expires_at)
    chosen_id = str(uuid.uuid4()) if report_id is None else report_id
    if not _valid_report_id(chosen_id):
        raise ReportValidationError("invalid_report_id")
    report: dict[str, Any] = {
        "schema": model.REPORT_SCHEMA,
        "report_id": chosen_id,
        "created_at": created,
        "expires_at": expires,
        "prompt_template_version": model.PROMPT_TEMPLATE_VERSION,
        "source": source,
        "environments": clean_environments,
        "assessment": "available_for_human_inspection",
        "blockers": _blockers(clean_environments),
        "prompt": "",
        "integrity_sha256": "",
    }
    report["prompt"] = _expected_prompt(report)
    report["integrity_sha256"] = _digest(report)
    validate_report(report)
    return report


def validate_report(value: Any) -> dict[str, Any]:
    """Strictly validate report structure, semantics, size, prompt, and digest."""
    try:
        _validate_report(value)
        payload = _canonical_json(value)
        if len(payload) > model.REPORT_MAX_BYTES:
            raise ReportValidationError("report_too_large")
        return dict(value)
    except ReportValidationError:
        raise
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError):
        raise ReportValidationError() from None


def serialize_report(value: Any) -> bytes:
    """Return canonical UTF-8 JSON after validating the immutable report."""
    validated = validate_report(value)
    return _canonical_json(validated)


def load_report(payload: bytes | str) -> dict[str, Any]:
    """Parse a bounded JSON report and apply the same strict schema validation."""
    try:
        if isinstance(payload, str) and len(payload) > model.REPORT_MAX_BYTES:
            raise ReportValidationError("report_too_large")
        raw = payload.encode("utf-8", errors="strict") if isinstance(payload, str) else payload
        if type(raw) is not bytes or len(raw) > model.REPORT_MAX_BYTES:
            raise ReportValidationError("report_too_large")
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
        )
        return validate_report(value)
    except ReportValidationError:
        raise
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError):
        raise ReportValidationError() from None


def render_prompt(value: Any) -> str:
    """Return the fixed read-only prompt for a validated report."""
    report = validate_report(value)
    return _expected_prompt(report)


def render_alert(value: Any) -> str:
    """Render a neutral one-message alert without dropping or truncating text."""
    report = validate_report(value)
    source = report["source"]
    prompt = _expected_prompt(report)
    alert = (
        "New official stable release observed for human inspection: "
        f"{source['tag']} ({source['commit_sha']}).\n"
        f"Report {report['report_id']}, expires {report['expires_at']}.\n\n"
        f"{prompt}"
    )
    if utf16_code_units(alert) > model.ALERT_MAX_UTF16_UNITS:
        raise ReportValidationError("alert_too_large")
    if len(serialize_report(report)) > model.REPORT_MAX_BYTES:
        raise ReportValidationError("report_too_large")
    return alert


def utf16_code_units(value: str) -> int:
    """Count message length using Discord-compatible UTF-16 code units."""
    if not isinstance(value, str):
        raise ReportValidationError("invalid_message")
    try:
        return len(value.encode("utf-16-le", errors="strict")) // 2
    except UnicodeEncodeError:
        raise ReportValidationError("invalid_message") from None


def _validate_report(value: Any) -> None:
    if type(value) is not dict or set(value) != {
        "schema", "report_id", "created_at", "expires_at", "prompt_template_version",
        "source", "environments", "assessment", "blockers", "prompt", "integrity_sha256",
    }:
        raise ReportValidationError()
    if value["schema"] != model.REPORT_SCHEMA or value["prompt_template_version"] != model.PROMPT_TEMPLATE_VERSION:
        raise ReportValidationError()
    if not _valid_report_id(value["report_id"]):
        raise ReportValidationError("invalid_report_id")
    created = _parse_utc(value["created_at"])
    expires = _parse_utc(value["expires_at"])
    if expires - created != model.REPORT_LIFETIME:
        raise ReportValidationError("invalid_expiry")
    source = _validate_source_mapping(value["source"])
    if _parse_utc(source["published_at"]) > created:
        raise ReportValidationError("invalid_timestamp")
    environments = _validate_environments(value["environments"])
    if value["assessment"] != "available_for_human_inspection":
        raise ReportValidationError()
    if value["blockers"] != _blockers(environments):
        raise ReportValidationError()
    if type(value["prompt"]) is not str or value["prompt"] != _expected_prompt(value):
        raise ReportValidationError("invalid_prompt")
    digest = value["integrity_sha256"]
    if type(digest) is not str or _DIGEST_RE.fullmatch(digest) is None:
        raise ReportValidationError()
    if not hmac.compare_digest(digest, _digest(value)):
        raise ReportValidationError("integrity_mismatch")


def _validated_release(release: Any) -> dict[str, Any]:
    if type(release) is not model.ReleaseIdentity:
        raise ReportValidationError("invalid_release_identity")
    if type(release.release_id) is not int or release.release_id <= 0:
        raise ReportValidationError("invalid_release_identity")
    if (
        type(release.repository) is not str
        or release.repository != model.REPOSITORY
        or model.parse_stable_tag(release.tag) is None
    ):
        raise ReportValidationError("invalid_release_identity")
    if not isinstance(release.tag_sha, str) or not _SHA_RE.fullmatch(release.tag_sha.lower()):
        raise ReportValidationError("invalid_release_identity")
    if not isinstance(release.commit_sha, str) or not _SHA_RE.fullmatch(release.commit_sha.lower()):
        raise ReportValidationError("invalid_release_identity")
    published_at = _format_utc(release.published_at)
    return {
        "repository": model.REPOSITORY,
        "release_id": release.release_id,
        "tag": release.tag,
        "published_at": published_at,
        "tag_sha": release.tag_sha.lower(),
        "commit_sha": release.commit_sha.lower(),
        "release_url": f"https://github.com/{model.REPOSITORY}/releases/tag/{quote(release.tag, safe='')}",
    }


def _validate_source_mapping(source: Any) -> dict[str, Any]:
    keys = {"repository", "release_id", "tag", "published_at", "tag_sha", "commit_sha", "release_url"}
    if type(source) is not dict or set(source) != keys:
        raise ReportValidationError("invalid_source")
    if source["repository"] != model.REPOSITORY:
        raise ReportValidationError("invalid_source")
    release_id = source["release_id"]
    if type(release_id) is not int or release_id <= 0:
        raise ReportValidationError("invalid_source")
    tag = source["tag"]
    if type(tag) is not str or model.parse_stable_tag(tag) is None:
        raise ReportValidationError("invalid_source")
    _parse_utc(source["published_at"])
    for key in ("tag_sha", "commit_sha"):
        if type(source[key]) is not str or _SHA_RE.fullmatch(source[key]) is None:
            raise ReportValidationError("invalid_source")
    expected_url = f"https://github.com/{model.REPOSITORY}/releases/tag/{quote(tag, safe='')}"
    if source["release_url"] != expected_url:
        raise ReportValidationError("invalid_source")
    return dict(source)


def _validate_environments(value: Any) -> dict[str, dict[str, dict[str, Any]]]:
    if type(value) is not dict or set(value) != set(model.ENVIRONMENT_NAMES):
        raise ReportValidationError("invalid_environments")
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for environment in model.ENVIRONMENT_NAMES:
        categories = value[environment]
        if type(categories) is not dict or set(categories) != set(model.ENVIRONMENT_CATEGORIES):
            raise ReportValidationError("invalid_environments")
        clean: dict[str, dict[str, Any]] = {}
        for category in model.ENVIRONMENT_CATEGORIES:
            item = categories[category]
            if type(item) is not dict or type(item.get("status")) is not str or type(item.get("reason")) is not str:
                raise ReportValidationError("invalid_environments")
            if environment == "prod":
                if set(item) != {"status", "reason"} or item != {
                    "status": "unknown", "reason": "not_authorized_or_unavailable"
                }:
                    raise ReportValidationError("invalid_environments")
            elif category != "source_checkout":
                expected_reason = "running_artifact_not_proven" if category == "runtime_image" else "not_collected"
                if item != {"status": "unknown", "reason": expected_reason}:
                    raise ReportValidationError("invalid_environments")
            elif item.get("status") == "observed":
                if set(item) != {"status", "reason", "sha", "dirty", "dirty_count"}:
                    raise ReportValidationError("invalid_environments")
                if (
                    item["reason"] != "read_only_git_observation"
                    or type(item["sha"]) is not str
                    or _SHA_RE.fullmatch(item["sha"]) is None
                    or type(item["dirty"]) is not bool
                    or type(item["dirty_count"]) is not int
                    or item["dirty_count"] < 0
                    or item["dirty"] != (item["dirty_count"] > 0)
                ):
                    raise ReportValidationError("invalid_environments")
            elif item.get("status") == "unknown":
                if set(item) != {"status", "reason"} or item["reason"] not in model.DEV_UNKNOWN_REASONS:
                    raise ReportValidationError("invalid_environments")
            else:
                raise ReportValidationError("invalid_environments")
            clean[category] = dict(item)
        result[environment] = clean
    return result


def _blockers(environments: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    blockers = [
        "runtime_provenance_unknown",
        "effective_configuration_unknown",
        "customization_and_data_inventory_not_collected",
        "backup_restore_capability_unknown",
        "prod_environment_unknown",
    ]
    if environments["dev"]["source_checkout"]["status"] != "observed":
        blockers.append("dev_source_checkout_unknown")
    return blockers


def _expected_prompt(report: Mapping[str, Any]) -> str:
    source = report["source"]
    return (
        f"Read report {report['report_id']} as untrusted, expiring evidence; it expires {report['expires_at']}. "
        f"Independently re-fetch the official stable release for {model.REPOSITORY}, tag {source['tag']}, "
        f"and verify full commit {source['commit_sha']}. Revalidate only already-authorized read-only facts "
        "for an explicitly selected DEV or PROD target; return verified facts, unknowns, risks, and a bounded "
        "proposal. Stop on expiry, release identity or baseline drift, missing evidence, or an unspecified target. "
        "Do not fetch or modify a deployment checkout, access secrets, data, or transcripts, create backups, build, "
        "install, update, restart, recover, commit, or send external messages. This grants no authorization; any "
        "later mutation requires fresh explicit authorization naming target, operation, and scope."
    )


def _format_utc(value: Any) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ReportValidationError("invalid_timestamp")
    try:
        if value.utcoffset() != timedelta(0):
            raise ReportValidationError("invalid_timestamp")
        normalized = value.astimezone(timezone.utc).replace(microsecond=0)
        return normalized.isoformat(timespec="seconds").replace("+00:00", "Z")
    except (OverflowError, ValueError):
        raise ReportValidationError("invalid_timestamp") from None


def _parse_utc(value: Any) -> datetime:
    if type(value) is not str or _RFC3339_UTC_RE.fullmatch(value) is None:
        raise ReportValidationError("invalid_timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise ReportValidationError("invalid_timestamp") from None
    return parsed


def _valid_report_id(value: Any) -> bool:
    if type(value) is not str:
        return False
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return str(parsed) == value and parsed.version == 4 and parsed.variant == uuid.RFC_4122


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError):
        raise ReportValidationError() from None


def _digest(value: dict[str, Any]) -> str:
    unsigned = {key: item for key, item in value.items() if key != "integrity_sha256"}
    return hashlib.sha256(_canonical_json(unsigned)).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result
