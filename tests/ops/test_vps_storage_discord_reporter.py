#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for VPS Storage Discord Morning Reporter
==============================================
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.ops.vps_storage_discord_reporter import (
    build_discord_embed,
    format_bytes_human,
    get_live_disk_metrics,
    load_hygiene_audit,
    main,
    post_to_discord_thread,
)


def test_format_bytes_human():
    assert format_bytes_human(500) == "500.00 B"
    assert format_bytes_human(1024) == "1.00 KB"
    assert format_bytes_human(1048576 * 2.5) == "2.50 MB"
    assert format_bytes_human(1073741824 * 10) == "10.00 GB"


def test_get_live_disk_metrics():
    metrics = get_live_disk_metrics("/")
    assert "total_gb" in metrics
    assert "used_gb" in metrics
    assert "free_gb" in metrics
    assert "used_pct" in metrics
    assert metrics["total_gb"] > 0
    assert 0 <= metrics["used_pct"] <= 100


def test_load_hygiene_audit_valid(tmp_path: Path):
    audit_file = tmp_path / "vps-hygiene.json"
    data = {
        "total_freed_bytes": 1048576,
        "active_install": "abc123hash",
        "tasks": {
            "scratch": {"scanned": 10, "pruned": 2},
            "installs": {"pruned": 1},
            "sqlite_backups": {"scanned": 5, "pruned": 1},
            "git_worktrees": {"repos_checked": 3},
        },
    }
    audit_file.write_text(json.dumps(data), encoding="utf-8")

    loaded = load_hygiene_audit(audit_file)
    assert loaded is not None
    assert loaded["total_freed_bytes"] == 1048576
    assert loaded["active_install"] == "abc123hash"


def test_load_hygiene_audit_missing_or_corrupt(tmp_path: Path):
    missing_file = tmp_path / "non_existent.json"
    assert load_hygiene_audit(missing_file) is None

    corrupted_file = tmp_path / "bad.json"
    corrupted_file.write_text("invalid json content")
    assert load_hygiene_audit(corrupted_file) is None


def test_build_discord_embed_threshold_colors():
    # Healthy: < 75%
    live_green = {"used_pct": 65.0, "used_gb": 65.0, "total_gb": 100.0, "free_gb": 35.0}
    embed_green = build_discord_embed(live_green, None)
    assert embed_green["color"] == 0x2ECC71
    assert "🟢 ÓPTIMO" in embed_green["fields"][1]["value"]

    # Warning: 75% - 80%
    live_orange = {"used_pct": 78.0, "used_gb": 78.0, "total_gb": 100.0, "free_gb": 22.0}
    embed_orange = build_discord_embed(live_orange, None)
    assert embed_orange["color"] == 0xF39C12
    assert "🟡 ALERTA" in embed_orange["fields"][1]["value"]

    # Critical: >= 80%
    live_red = {"used_pct": 85.0, "used_gb": 85.0, "total_gb": 100.0, "free_gb": 15.0}
    embed_red = build_discord_embed(live_red, None)
    assert embed_red["color"] == 0xE74C3C
    assert "🔴 CRÍTICO" in embed_red["fields"][1]["value"]


def test_post_to_discord_thread_dry_run():
    embed = {"title": "Test"}
    assert post_to_discord_thread("12345", embed, token="", dry_run=True) is True


def test_post_to_discord_thread_mocked(monkeypatch):
    embed = {"title": "Test"}
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout: mock_resp)

    res = post_to_discord_thread("1569546504442740881", embed, token="fake_token", dry_run=False)
    assert res is True


def test_main_dry_run_cli(tmp_path: Path):
    audit_file = tmp_path / "vps-hygiene.json"
    audit_file.write_text(json.dumps({"total_freed_bytes": 0, "tasks": {}}), encoding="utf-8")

    exit_code = main(["--dry-run", "--audit-log", str(audit_file)])
    assert exit_code == 0
