#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for VPS Daily Storage Hygiene Janitor
===========================================
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Ensure scripts/ops can be imported
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.ops.vps_daily_hygiene import (
    check_disk_threshold,
    is_path_contained,
    main,
    prune_git_worktrees,
    prune_scratch_dirs,
    resolve_active_install,
    rotate_hermes_installs,
    rotate_sqlite_backups,
    run_daily_hygiene,
    vacuum_system_logs,
)


def test_dry_run_leaves_filesystem_untouched(tmp_path: Path):
    """Verify dry_run=True computes freed bytes and reports without removing files."""
    # Setup scratch
    scratch = tmp_path / "cache" / "scratch"
    scratch.mkdir(parents=True)
    old_scratch = scratch / "old_scratch.tmp"
    old_scratch.write_text("old scratch content")
    os.utime(old_scratch, (time.time() - 10 * 86400, time.time() - 10 * 86400))

    # Setup installs
    installs = tmp_path / "installs"
    installs.mkdir()
    active_inst = installs / "active_hash_1"
    active_inst.mkdir()
    (active_inst / "facts.json").write_text("{}")

    old_inst = installs / "old_hash_2"
    old_inst.mkdir()
    (old_inst / "facts.json").write_text("{}")
    os.utime(old_inst, (time.time() - 20 * 86400, time.time() - 20 * 86400))

    (tmp_path / "active_install").write_text("active_hash_1")

    # Setup canonical db and old backup
    canonical_db = tmp_path / "state.db"
    canonical_db.write_text("canonical database content")
    canonical_wal = tmp_path / "state.db-wal"
    canonical_wal.write_text("canonical wal content")
    canonical_shm = tmp_path / "state.db-shm"
    canonical_shm.write_text("canonical shm content")

    old_bak = tmp_path / "state.db.bak-old"
    old_bak.write_text("backup content")
    os.utime(old_bak, (time.time() - 30 * 86400, time.time() - 30 * 86400))

    report = run_daily_hygiene(
        base_dir=tmp_path,
        dry_run=True,
        git_repos=[],
    )

    assert report["dry_run"] is True
    assert report["active_install"] == "active_hash_1"
    assert report["total_freed_bytes"] > 0

    # Every file and folder must still exist
    assert old_scratch.exists(), "Scratch file was deleted in dry-run!"
    assert old_inst.exists(), "Install was deleted in dry-run!"
    assert active_inst.exists(), "Active install was deleted in dry-run!"
    assert canonical_db.exists(), "Canonical db was deleted in dry-run!"
    assert canonical_wal.exists(), "Canonical wal was deleted in dry-run!"
    assert canonical_shm.exists(), "Canonical shm was deleted in dry-run!"
    assert old_bak.exists(), "Backup was deleted in dry-run!"


def test_active_install_never_deleted(tmp_path: Path):
    """Verify that active install is preserved regardless of keep_latest_n or timestamp."""
    installs = tmp_path / "installs"
    installs.mkdir()

    active_hash = "active_hash_alpha"
    active_dir = installs / active_hash
    active_dir.mkdir()
    (active_dir / "data.bin").write_bytes(b"active-content")
    # Make active install very old (60 days ago)
    os.utime(active_dir, (time.time() - 60 * 86400, time.time() - 60 * 86400))

    other_newer = installs / "other_newer"
    other_newer.mkdir()
    (other_newer / "data.bin").write_bytes(b"newer-content")
    os.utime(other_newer, (time.time() - 2 * 86400, time.time() - 2 * 86400))

    other_older = installs / "other_older"
    other_older.mkdir()
    (other_older / "data.bin").write_bytes(b"older-content")
    os.utime(other_older, (time.time() - 15 * 86400, time.time() - 15 * 86400))

    # Keep latest 1 total: active install must stay, others pruned
    res = rotate_hermes_installs(tmp_path, active_hash=active_hash, keep_latest_n=1, dry_run=False)

    assert active_dir.exists(), "Active install directory was deleted!"
    assert (active_dir / "data.bin").exists()
    assert not other_older.exists(), "Old install was not pruned!"
    assert not other_newer.exists(), "Newer install should have been pruned when keep_latest_n=1!"
    assert res["pruned"] == 2
    assert active_hash in res["active_hash"]

    # Even with keep_latest_n=0, active install must NEVER be pruned
    res_zero = rotate_hermes_installs(tmp_path, active_hash=active_hash, keep_latest_n=0, dry_run=False)
    assert active_dir.exists(), "Active install deleted when keep_latest_n=0!"


def test_scratch_ttl_pruning(tmp_path: Path):
    """Verify scratch directories prune files older than TTL while keeping younger files."""
    scratch_main = tmp_path / "cache" / "scratch"
    scratch_main.mkdir(parents=True)
    scratch_profile = tmp_path / "profiles" / "user_1" / "cache" / "scratch"
    scratch_profile.mkdir(parents=True)

    now = time.time()

    # In main scratch
    old_main = scratch_main / "old_main.txt"
    old_main.write_text("old main content")
    os.utime(old_main, (now - 5 * 86400, now - 5 * 86400))  # 5 days old (> 3)

    new_main = scratch_main / "new_main.txt"
    new_main.write_text("new main content")
    os.utime(new_main, (now - 1 * 86400, now - 1 * 86400))  # 1 day old (< 3)

    # In profile scratch
    old_prof = scratch_profile / "old_prof.txt"
    old_prof.write_text("old profile content")
    os.utime(old_prof, (now - 4 * 86400, now - 4 * 86400))  # 4 days old (> 3)

    new_prof = scratch_profile / "new_prof.txt"
    new_prof.write_text("new profile content")
    os.utime(new_prof, (now - 0.5 * 86400, now - 0.5 * 86400))  # 0.5 days old (< 3)

    res = prune_scratch_dirs(tmp_path, ttl_days=3, dry_run=False)

    assert res["scanned"] == 4
    assert res["pruned"] == 2
    assert res["bytes_freed"] > 0

    assert not old_main.exists(), "Old main scratch file was not pruned!"
    assert new_main.exists(), "New main scratch file was incorrectly pruned!"
    assert not old_prof.exists(), "Old profile scratch file was not pruned!"
    assert new_prof.exists(), "New profile scratch file was incorrectly pruned!"


def test_sqlite_bak_rotation_preserves_canonical_db(tmp_path: Path):
    """Verify that SQLite backup rotation cleans old backups but preserves state.db and journals."""
    # Canonical databases - must NEVER be pruned regardless of mtime
    canonical_db = tmp_path / "state.db"
    canonical_db.write_text("canonical database")
    canonical_wal = tmp_path / "state.db-wal"
    canonical_wal.write_text("canonical wal")
    canonical_shm = tmp_path / "state.db-shm"
    canonical_shm.write_text("canonical shm")

    # Set canonical mtime to 180 days ago (half a year old)
    ancient_time = time.time() - 180 * 86400
    os.utime(canonical_db, (ancient_time, ancient_time))
    os.utime(canonical_wal, (ancient_time, ancient_time))
    os.utime(canonical_shm, (ancient_time, ancient_time))

    # Old backup in base_dir
    bak_old = tmp_path / "state.db.bak-20261001"
    bak_old.write_text("backup old")
    os.utime(bak_old, (time.time() - 14 * 86400, time.time() - 14 * 86400))  # 14 days old

    # Operational non-db files that contain "backup" in the name must NEVER be pruned
    script_file = tmp_path / "backup.sh"
    script_file.write_text("#!/bin/bash\necho backup")
    os.utime(script_file, (time.time() - 30 * 86400, time.time() - 30 * 86400))

    manifest_file = tmp_path / "backup_manifest.json"
    manifest_file.write_text('{"type": "manifest"}')
    os.utime(manifest_file, (time.time() - 30 * 86400, time.time() - 30 * 86400))

    # New backup in base_dir
    bak_new = tmp_path / "state.db.bak-20261108"
    bak_new.write_text("backup new")
    os.utime(bak_new, (time.time() - 2 * 86400, time.time() - 2 * 86400))  # 2 days old

    # Backups subfolder
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()
    sub_old = backups_dir / "old_backup.sqlite"
    sub_old.write_text("sqlite copy")
    os.utime(sub_old, (time.time() - 20 * 86400, time.time() - 20 * 86400))

    sub_new = backups_dir / "recent_backup.sqlite"
    sub_new.write_text("sqlite copy")
    os.utime(sub_new, (time.time() - 3 * 86400, time.time() - 3 * 86400))

    res = rotate_sqlite_backups(tmp_path, ttl_days=7, dry_run=False)

    # Canonical files must remain intact
    assert canonical_db.exists(), "Canonical state.db was deleted!"
    assert canonical_wal.exists(), "Canonical state.db-wal was deleted!"
    assert canonical_shm.exists(), "Canonical state.db-shm was deleted!"

    # Operational non-db scripts/configs must remain intact
    assert script_file.exists(), "Operational script backup.sh was deleted!"
    assert manifest_file.exists(), "Operational config backup_manifest.json was deleted!"

    # Old backups pruned
    assert not bak_old.exists(), "Old state.db.bak was not pruned!"
    assert not sub_old.exists(), "Old subfolder backup was not pruned!"

    # New backups preserved
    assert bak_new.exists(), "New state.db.bak was incorrectly pruned!"
    assert sub_new.exists(), "New subfolder backup was incorrectly pruned!"

    assert res["pruned"] == 2
    assert res["bytes_freed"] > 0


def test_symlink_safety_and_containment(tmp_path: Path):
    """Verify symlink resolution does not delete external targets outside base_dir."""
    external_dir = tmp_path.parent / "external_safety_test"
    external_dir.mkdir(parents=True, exist_ok=True)
    external_file = external_dir / "secret_document.txt"
    external_file.write_text("critical external data")
    # Make external file old
    os.utime(external_file, (time.time() - 20 * 86400, time.time() - 20 * 86400))

    scratch = tmp_path / "cache" / "scratch"
    scratch.mkdir(parents=True)

    # Create symlink pointing outside base_dir
    symlink_to_external = scratch / "link_to_secret"
    symlink_to_external.symlink_to(external_file)
    os.utime(symlink_to_external, (time.time() - 10 * 86400, time.time() - 10 * 86400), follow_symlinks=False)

    # Create symlink pointing to canonical state.db
    canonical_db = tmp_path / "state.db"
    canonical_db.write_text("canonical db")
    symlink_to_db = scratch / "link_to_db"
    symlink_to_db.symlink_to(canonical_db)
    os.utime(symlink_to_db, (time.time() - 10 * 86400, time.time() - 10 * 86400), follow_symlinks=False)

    prune_scratch_dirs(tmp_path, ttl_days=3, dry_run=False)

    # External target MUST survive
    assert external_file.exists(), "External file outside base_dir was deleted via symlink!"
    assert external_dir.exists(), "External directory was deleted!"
    assert canonical_db.exists(), "Canonical state.db was deleted via symlink!"

    # The expired symlinks inside scratch themselves MUST be safely unlinked
    assert not symlink_to_external.exists(follow_symlinks=False), "Expired scratch symlink was not unlinked!"
    assert not symlink_to_db.exists(follow_symlinks=False), "Expired scratch symlink was not unlinked!"

    # Cleanup external test dir
    shutil.rmtree(external_dir, ignore_errors=True)


def test_disk_threshold_calculation(tmp_path: Path, monkeypatch):
    """Verify disk threshold reporting and exceeded calculation."""
    # Test mocked usage: 85% used
    monkeypatch.setattr(shutil, "disk_usage", lambda _: (1000, 850, 150))

    res_exceeded = check_disk_threshold(str(tmp_path), threshold_pct=80.0)
    assert res_exceeded["used_pct"] == 85.0
    assert res_exceeded["exceeded"] is True
    assert res_exceeded["threshold_pct"] == 80.0

    res_ok = check_disk_threshold(str(tmp_path), threshold_pct=90.0)
    assert res_ok["used_pct"] == 85.0
    assert res_ok["exceeded"] is False
    assert res_ok["threshold_pct"] == 90.0

    # Test real unmocked usage on tmp_path
    monkeypatch.undo()
    real_res = check_disk_threshold(str(tmp_path))
    assert "used_pct" in real_res
    assert "total_bytes" in real_res
    assert "free_bytes" in real_res
    assert "exceeded" in real_res
    assert real_res["total_bytes"] > 0


def test_full_run_cli(tmp_path: Path):
    """Verify full CLI execution writes JSON log and returns 0."""
    (tmp_path / "cache" / "scratch").mkdir(parents=True)
    (tmp_path / "installs").mkdir()
    (tmp_path / "state.db").write_text("db")

    log_path = tmp_path / "hygiene_log.json"
    script = REPO_ROOT / "scripts" / "ops" / "vps_daily_hygiene.py"

    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--base-dir",
            str(tmp_path),
            "--dry-run",
            "--json-log",
            str(log_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, f"CLI exited with {proc.returncode}:\n{proc.stdout}\n{proc.stderr}"
    assert log_path.exists(), "JSON log was not written!"

    data = json.loads(log_path.read_text(encoding="utf-8"))
    assert data["dry_run"] is True
    assert "tasks" in data
    assert "scratch" in data["tasks"]
    assert "installs" in data["tasks"]
    assert "sqlite_backups" in data["tasks"]
    assert "git_worktrees" in data["tasks"]
    assert "system_logs" in data["tasks"]
    assert "initial_disk" in data
    assert "final_disk" in data


def test_prune_git_worktrees_dry_run_and_execution(tmp_path: Path):
    """Verify git worktree prune succeeds in both dry_run and execution modes."""
    # Setup mock git repository
    repo_dir = tmp_path / "mock_repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_dir), check=True, capture_output=True)
    (repo_dir / "initial.txt").write_text("initial commit")
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo_dir), check=True, capture_output=True)

    # Test dry run (must not fail with error: unknown switch 'n')
    dry_res = prune_git_worktrees([repo_dir], dry_run=True)
    assert dry_res["repos_checked"] == 1
    assert dry_res["results"][0]["success"] is True

    # Test real run
    real_res = prune_git_worktrees([repo_dir], dry_run=False)
    assert real_res["repos_checked"] == 1
    assert real_res["results"][0]["success"] is True


def test_vacuum_system_logs_dry_run_and_execution():
    """Verify vacuum_system_logs dry run succeeds without errors."""
    dry_res = vacuum_system_logs(max_size="500M", dry_run=True)
    assert dry_res["dry_run"] is True
    assert dry_res["max_size"] == "500M"
    assert "success" in dry_res


def test_json_log_write_failure_handles_error(tmp_path: Path, monkeypatch):
    """Verify logger handles write errors without throwing TypeError."""
    invalid_log_path = tmp_path / "non_existent_sub_dir" / "readonly_file"

    def mock_write_text(*args, **kwargs):
        raise OSError("Permission denied simulation")

    monkeypatch.setattr(Path, "write_text", mock_write_text)

    # Should not crash with TypeError
    report = run_daily_hygiene(
        base_dir=tmp_path,
        dry_run=True,
        git_repos=[],
        json_log_path=invalid_log_path,
    )
    assert report["dry_run"] is True
