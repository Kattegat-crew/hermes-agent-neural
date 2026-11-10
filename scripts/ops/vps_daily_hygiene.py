#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VPS Daily Storage Hygiene Janitor
=================================

Automated storage maintenance script for Hermes VPS environments.
Cleans up scratch directories, rotates old installs and SQLite backups,
prunes disconnected git worktrees, vacuums systemd journal logs,
and enforces storage safety constraints.

Security Constraints:
- Strict path containment: all deletions verified within base_dir.
- Symlink resolution: never deletes external files through symlinks.
- Absolute protection: state.db, state.db-wal, state.db-shm, and active install folder.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("vps_daily_hygiene")

# Canonical SQLite databases and journal files that must NEVER be deleted
PROTECTED_DB_NAMES: Set[str] = frozenset({
    "state.db",
    "state.db-wal",
    "state.db-shm",
})

# Database files that are canonical active databases if directly under base_dir
CANONICAL_ACTIVE_DBS: Set[str] = frozenset({
    "shared-state.db",
    "shared-state.db-wal",
    "shared-state.db-shm",
    "response_store.db",
    "response_store.db-wal",
    "response_store.db-shm",
    "runs_idempotency.db",
    "runs_idempotency.db-wal",
    "runs_idempotency.db-shm",
    "verification_evidence.db",
    "verification_evidence.db-wal",
    "verification_evidence.db-shm",
})


def is_path_contained(target: Path, base_dir: Path) -> bool:
    """Verify that target resides strictly inside base_dir without escaping."""
    try:
        resolved_target = target.resolve()
        resolved_base = base_dir.resolve()
        return resolved_target.is_relative_to(resolved_base)
    except (ValueError, OSError):
        return False


def get_dir_size_bytes(directory: Path) -> int:
    """Calculate the total size of all files in a directory in bytes."""
    total = 0
    if not directory.is_dir() or directory.is_symlink():
        return total
    for root, _, files in os.walk(directory):
        for f in files:
            fp = Path(root) / f
            try:
                if not fp.is_symlink():
                    total += fp.stat().st_size
                else:
                    total += fp.lstat().st_size
            except OSError:
                pass
    return total


def resolve_active_install(base_dir: Path) -> Optional[str]:
    """
    Resolve the active Hermes install hash/identifier.
    
    Resolution order:
    1. Pointer file/symlink: base_dir / "current" or base_dir / "installs" / "current"
    2. Explicit record: base_dir / "active_install" or base_dir / ".active_install"
    3. Active leases: base_dir / "installs" / <hash> with newest generation lease
    4. Most recently modified install directory under base_dir / "installs"
    """
    base_dir = Path(base_dir)

    # 1. Symlink or pointer file 'current'
    for candidate in (base_dir / "current", base_dir / "installs" / "current"):
        if candidate.is_symlink():
            try:
                target = candidate.resolve()
                if target.is_dir() and target.name:
                    return target.name
            except OSError:
                pass
        elif candidate.is_file():
            try:
                text = candidate.read_text(encoding="utf-8").strip()
                if text:
                    return text
            except OSError:
                pass

    # 2. Pointer file 'active_install' or '.active_install' or 'active_hash'
    for name in ("active_install", ".active_install", "active_hash"):
        p = base_dir / name
        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8").strip()
                if text:
                    return text
            except OSError:
                pass

    # 3. Check installs directory for leases or newest mtime
    installs_dir = base_dir / "installs"
    if not installs_dir.is_dir():
        return None

    install_dirs = [d for d in installs_dir.iterdir() if d.is_dir() and not d.is_symlink() and d.name != "current"]
    if not install_dirs:
        return None

    # Check for active leases in environments or pm-runtime
    lease_candidates: List[tuple[float, str]] = []
    for d in install_dirs:
        newest_lease = 0.0
        lease_paths: List[Path] = []
        for gen_dir in (d / "environments", d / "pm-runtime" / "generations"):
            if gen_dir.is_dir():
                lease_paths.extend(gen_dir.glob("*/.leases/*"))
        for lp in lease_paths:
            try:
                mtime = lp.stat().st_mtime
                if mtime > newest_lease:
                    newest_lease = mtime
            except OSError:
                pass
        if newest_lease > 0.0:
            lease_candidates.append((newest_lease, d.name))

    if lease_candidates:
        lease_candidates.sort(key=lambda x: x[0], reverse=True)
        return lease_candidates[0][1]

    # Fallback: install directory with the latest mtime
    install_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return install_dirs[0].name


def prune_scratch_dirs(base_dir: Path, ttl_days: int = 3, dry_run: bool = False) -> Dict[str, Any]:
    """
    Prune temporary files older than ttl_days in scratch directories.
    
    Searches:
    - base_dir / "cache" / "scratch"
    - base_dir / "profiles" / * / "cache" / "scratch"
    
    Security:
    - Verifies path containment within base_dir.
    - If a symlink is encountered, deletes only the symlink itself without touching
      or deleting target files outside base_dir.
    - Protected canonical databases (state.db, etc.) are never deleted.
    """
    base_dir = Path(base_dir)
    ttl_seconds = ttl_days * 86400
    cutoff_time = time.time() - ttl_seconds

    scratch_roots: List[Path] = []
    c1 = base_dir / "cache" / "scratch"
    if c1.is_dir():
        scratch_roots.append(c1)

    profiles_dir = base_dir / "profiles"
    if profiles_dir.is_dir():
        for p in profiles_dir.iterdir():
            if p.is_dir():
                pc = p / "cache" / "scratch"
                if pc.is_dir():
                    scratch_roots.append(pc)

    scanned_count = 0
    pruned_count = 0
    bytes_freed = 0
    pruned_paths: List[str] = []
    errors: List[str] = []

    for root_dir in scratch_roots:
        # Traverse topdown=False to remove empty directories cleanly
        for current_root, dirs, files in os.walk(root_dir, topdown=False, followlinks=False):
            current_path = Path(current_root)

            # Process files and symlinks
            for fname in files:
                scanned_count += 1
                fpath = current_path / fname

                # Never delete canonical db files
                if fpath.name in PROTECTED_DB_NAMES:
                    continue

                try:
                    is_symlink = fpath.is_symlink()
                    lstat = fpath.lstat()
                    file_mtime = lstat.st_mtime
                    file_size = lstat.st_size

                    # Symlink target safety check
                    if is_symlink:
                        try:
                            resolved_target = fpath.resolve()
                            if resolved_target.name in PROTECTED_DB_NAMES:
                                # Points to protected database - do not touch
                                continue
                        except OSError:
                            pass

                    # TTL check
                    if file_mtime < cutoff_time:
                        if not dry_run:
                            # Strict containment check of the scratch path itself
                            if not is_path_contained(fpath, base_dir):
                                errors.append(f"Containment violation: {fpath}")
                                continue
                            fpath.unlink()

                        pruned_count += 1
                        bytes_freed += file_size
                        pruned_paths.append(str(fpath))

                except OSError as exc:
                    errors.append(f"Failed to process {fpath}: {exc}")

            # Clean up empty subdirectories (never remove the scratch root itself)
            if current_path != root_dir:
                try:
                    if not current_path.is_symlink() and not any(current_path.iterdir()):
                        if not dry_run:
                            current_path.rmdir()
                except OSError:
                    pass

    return {
        "scanned": scanned_count,
        "pruned": pruned_count,
        "bytes_freed": bytes_freed,
        "pruned_paths": pruned_paths,
        "dry_run": dry_run,
        "errors": errors,
    }


def rotate_hermes_installs(
    base_dir: Path,
    active_hash: str,
    keep_latest_n: int = 2,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Rotate older Hermes installs under base_dir / "installs", keeping active_hash and
    the latest keep_latest_n installs total.
    
    Security:
    - The active_hash install folder is ABSOLUTELY PROTECTED and never deleted.
    - Strict containment verification under base_dir / "installs".
    """
    base_dir = Path(base_dir)
    installs_dir = base_dir / "installs"

    if not installs_dir.is_dir():
        return {
            "scanned": 0,
            "pruned": 0,
            "bytes_freed": 0,
            "active_hash": active_hash,
            "pruned_installs": [],
            "dry_run": dry_run,
            "errors": [],
        }

    all_dirs = [d for d in installs_dir.iterdir() if d.is_dir() and not d.is_symlink() and d.name != "current"]
    
    # Active install directories matching active_hash (must never be pruned)
    active_dirs = [d for d in all_dirs if active_hash and (d.name == active_hash or d.name.startswith(active_hash))]
    
    # Candidates for rotation are non-active install directories
    candidates = [d for d in all_dirs if d not in active_dirs]
    candidates.sort(key=lambda d: d.stat().st_mtime, reverse=True)

    # Number of candidates to retain: keep_latest_n minus active installs kept
    to_keep_count = max(0, keep_latest_n - len(active_dirs))
    to_prune = candidates[to_keep_count:]

    pruned_installs: List[str] = []
    bytes_freed = 0
    errors: List[str] = []

    for d in to_prune:
        # Extra safety check: never prune active install
        if active_hash and (d.name == active_hash or d.name.startswith(active_hash)):
            continue

        if not is_path_contained(d, installs_dir):
            errors.append(f"Containment violation: {d}")
            continue

        size = get_dir_size_bytes(d)
        if not dry_run:
            try:
                shutil.rmtree(d)
            except OSError as exc:
                errors.append(f"Failed to remove install {d}: {exc}")
                continue

        bytes_freed += size
        pruned_installs.append(d.name)

    return {
        "scanned": len(all_dirs),
        "pruned": len(pruned_installs),
        "bytes_freed": bytes_freed,
        "active_hash": active_hash,
        "pruned_installs": pruned_installs,
        "dry_run": dry_run,
        "errors": errors,
    }


def rotate_sqlite_backups(base_dir: Path, ttl_days: int = 7, dry_run: bool = False) -> Dict[str, Any]:
    """
    Rotate SQLite backup files older than ttl_days.
    
    Searches:
    - base_dir / "backups" and subdirectories
    - base_dir / "state-snapshots"
    - Backup patterns in base_dir and profiles: *.bak, *.backup, *state.db*.bak*
    
    Security:
    - Absolute protection: state.db, state.db-wal, state.db-shm are NEVER deleted.
    - Canonical active databases (*.db) directly under base_dir are never deleted.
    """
    base_dir = Path(base_dir)
    ttl_seconds = ttl_days * 86400
    cutoff_time = time.time() - ttl_seconds

    candidate_files: Set[Path] = set()

    # 1. Backups and snapshots directories
    for sub in ("backups", "state-snapshots"):
        sdir = base_dir / sub
        if sdir.is_dir():
            for root, _, files in os.walk(sdir):
                for f in files:
                    candidate_files.add(Path(root) / f)

    # 2. Backup files in base_dir and profiles
    scan_roots = [base_dir]
    profiles_dir = base_dir / "profiles"
    if profiles_dir.is_dir():
        for p in profiles_dir.iterdir():
            if p.is_dir():
                scan_roots.append(p)

    backup_name_re = re.compile(r"(\.bak|\.backup|state\.db.*\.bak|backup)", re.IGNORECASE)

    for sroot in scan_roots:
        try:
            for item in sroot.iterdir():
                if item.is_file() and backup_name_re.search(item.name):
                    candidate_files.add(item)
        except OSError:
            pass

    scanned_count = 0
    pruned_count = 0
    bytes_freed = 0
    pruned_files: List[str] = []
    errors: List[str] = []

    for fpath in candidate_files:
        scanned_count += 1

        # CRITICAL SAFETY: Canonical databases must NEVER be deleted
        if fpath.name in PROTECTED_DB_NAMES:
            continue
        if re.fullmatch(r"state\.db(-wal|-shm)?", fpath.name):
            continue
        if fpath.name in CANONICAL_ACTIVE_DBS:
            continue

        try:
            lstat = fpath.lstat()
            if lstat.st_mtime < cutoff_time:
                file_size = lstat.st_size
                if not dry_run:
                    if not is_path_contained(fpath, base_dir):
                        errors.append(f"Containment violation: {fpath}")
                        continue
                    fpath.unlink()

                pruned_count += 1
                bytes_freed += file_size
                pruned_files.append(str(fpath))

        except OSError as exc:
            errors.append(f"Failed to process backup {fpath}: {exc}")

    return {
        "scanned": scanned_count,
        "pruned": pruned_count,
        "bytes_freed": bytes_freed,
        "pruned_files": pruned_files,
        "dry_run": dry_run,
        "errors": errors,
    }


def prune_git_worktrees(repos: List[Path], dry_run: bool = False) -> Dict[str, Any]:
    """
    Prune stale or disconnected git worktrees across given repository roots.
    Executes 'git worktree prune [-n] -v'.
    """
    results: List[Dict[str, Any]] = []

    for repo in repos:
        repo_path = Path(repo).resolve()
        if not repo_path.is_dir() or not (repo_path / ".git").exists():
            results.append({
                "repo": str(repo_path),
                "success": False,
                "error": "Not a git repository",
                "pruned_count": 0,
            })
            continue

        cmd = ["git", "-C", str(repo_path), "worktree", "prune", "-v"]
        if dry_run:
            cmd.insert(4, "-n")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            output = proc.stdout.strip() + "\n" + proc.stderr.strip()
            # Count lines reporting pruned worktrees
            pruned_count = len([line for line in output.splitlines() if "Removing" in line or "pruning" in line.lower()])
            results.append({
                "repo": str(repo_path),
                "success": proc.returncode == 0,
                "output": output.strip(),
                "pruned_count": pruned_count,
                "error": proc.stderr.strip() if proc.returncode != 0 else None,
            })
        except Exception as exc:
            results.append({
                "repo": str(repo_path),
                "success": False,
                "error": str(exc),
                "pruned_count": 0,
            })

    return {
        "repos_checked": len(repos),
        "dry_run": dry_run,
        "results": results,
    }


def vacuum_system_logs(max_size: str = "500M", dry_run: bool = False) -> Dict[str, Any]:
    """
    Vacuum systemd journal logs to max_size.
    In dry_run mode, reports current journal disk usage without altering logs.
    """
    journalctl_bin = shutil.which("journalctl")
    if not journalctl_bin:
        return {
            "available": False,
            "dry_run": dry_run,
            "max_size": max_size,
            "bytes_freed": 0,
            "message": "journalctl not found on system",
        }

    if dry_run:
        try:
            proc = subprocess.run(
                [journalctl_bin, "--disk-usage"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            return {
                "available": True,
                "dry_run": True,
                "max_size": max_size,
                "bytes_freed": 0,
                "disk_usage": proc.stdout.strip(),
                "success": proc.returncode == 0,
            }
        except Exception as exc:
            return {
                "available": True,
                "dry_run": True,
                "max_size": max_size,
                "bytes_freed": 0,
                "error": str(exc),
                "success": False,
            }

    try:
        proc = subprocess.run(
            [journalctl_bin, f"--vacuum-size={max_size}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        output = proc.stdout.strip()
        # Parse freed bytes if reported (e.g., "freed 12.3M of archived journals")
        bytes_freed = 0
        match = re.search(r"freed\s+([\d.]+)\s*([KMGTP]?)B?", output, re.IGNORECASE)
        if match:
            val = float(match.group(1))
            unit = match.group(2).upper()
            multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4, "P": 1024**5}
            bytes_freed = int(val * multipliers.get(unit, 1))

        return {
            "available": True,
            "dry_run": False,
            "max_size": max_size,
            "bytes_freed": bytes_freed,
            "output": output,
            "success": proc.returncode == 0,
            "error": proc.stderr.strip() if proc.returncode != 0 else None,
        }
    except Exception as exc:
        return {
            "available": True,
            "dry_run": False,
            "max_size": max_size,
            "bytes_freed": 0,
            "error": str(exc),
            "success": False,
        }


def check_disk_threshold(mount_point: str = "/", threshold_pct: float = 80.0) -> Dict[str, Any]:
    """
    Check if disk space usage on mount_point exceeds threshold_pct.
    """
    try:
        total, used, free = shutil.disk_usage(mount_point)
        used_pct = round((used / total) * 100.0, 2) if total > 0 else 0.0
        exceeded = used_pct >= threshold_pct
        return {
            "mount_point": mount_point,
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "used_pct": used_pct,
            "threshold_pct": threshold_pct,
            "exceeded": exceeded,
            "error": None,
        }
    except OSError as exc:
        return {
            "mount_point": mount_point,
            "total_bytes": 0,
            "used_bytes": 0,
            "free_bytes": 0,
            "used_pct": 0.0,
            "threshold_pct": threshold_pct,
            "exceeded": False,
            "error": str(exc),
        }


def run_daily_hygiene(
    base_dir: Optional[Path | str] = None,
    dry_run: bool = False,
    scratch_ttl_days: int = 3,
    backup_ttl_days: int = 7,
    keep_installs_n: int = 2,
    journal_max_size: str = "500M",
    disk_threshold_pct: float = 80.0,
    git_repos: Optional[List[Path | str]] = None,
    mount_point: str = "/",
    json_log_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """
    Coordinate all VPS daily storage hygiene tasks:
    1. Check initial disk threshold
    2. Resolve active install
    3. Prune scratch directories
    4. Rotate installs
    5. Rotate SQLite backups
    6. Prune git worktrees
    7. Vacuum system logs
    8. Check final disk threshold
    9. Compute total freed bytes and write JSON log
    """
    if base_dir is None:
        base_dir = Path(os.environ.get("HERMES_HOME", "/opt/hermes-agent-data"))
    base_dir = Path(base_dir).resolve()

    start_time = datetime.now(timezone.utc)
    initial_disk = check_disk_threshold(mount_point=mount_point, threshold_pct=disk_threshold_pct)

    active_hash = resolve_active_install(base_dir)

    # 1. Scratch dirs
    scratch_result = prune_scratch_dirs(base_dir=base_dir, ttl_days=scratch_ttl_days, dry_run=dry_run)

    # 2. Hermes installs
    installs_result = rotate_hermes_installs(
        base_dir=base_dir,
        active_hash=active_hash or "",
        keep_latest_n=keep_installs_n,
        dry_run=dry_run,
    )

    # 3. SQLite backups
    backups_result = rotate_sqlite_backups(base_dir=base_dir, ttl_days=backup_ttl_days, dry_run=dry_run)

    # 4. Git worktrees
    if git_repos is None:
        repos_to_check: List[Path] = []
        for candidate in (Path("/opt/hermes-agent"), base_dir):
            if (candidate / ".git").exists():
                repos_to_check.append(candidate)
        repos_dir = base_dir / "repos"
        if repos_dir.is_dir():
            for rd in repos_dir.iterdir():
                if rd.is_dir() and (rd / ".git").exists():
                    repos_to_check.append(rd)
    else:
        repos_to_check = [Path(r) for r in git_repos]

    worktrees_result = prune_git_worktrees(repos=repos_to_check, dry_run=dry_run)

    # 5. System logs
    logs_result = vacuum_system_logs(max_size=journal_max_size, dry_run=dry_run)

    final_disk = check_disk_threshold(mount_point=mount_point, threshold_pct=disk_threshold_pct)

    total_freed_bytes = (
        scratch_result.get("bytes_freed", 0)
        + installs_result.get("bytes_freed", 0)
        + backups_result.get("bytes_freed", 0)
        + logs_result.get("bytes_freed", 0)
    )

    end_time = datetime.now(timezone.utc)

    report: Dict[str, Any] = {
        "timestamp_start": start_time.isoformat(),
        "timestamp_end": end_time.isoformat(),
        "base_dir": str(base_dir),
        "dry_run": dry_run,
        "active_install": active_hash,
        "total_freed_bytes": total_freed_bytes,
        "initial_disk": initial_disk,
        "final_disk": final_disk,
        "tasks": {
            "scratch": scratch_result,
            "installs": installs_result,
            "sqlite_backups": backups_result,
            "git_worktrees": worktrees_result,
            "system_logs": logs_result,
        },
    }

    if json_log_path is not None:
        log_path = Path(json_log_path).resolve()
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.error("Failed to write JSON log to %s: %exc", log_path, exc)

    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="VPS Daily Storage Hygiene Janitor")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate cleanup without deleting any files",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path(os.environ.get("HERMES_HOME", "/opt/hermes-agent-data")),
        help="Base directory for Hermes data (default: $HERMES_HOME or /opt/hermes-agent-data)",
    )
    parser.add_argument(
        "--json-log",
        type=Path,
        default=None,
        help="Path to write JSON execution report",
    )
    parser.add_argument(
        "--scratch-ttl-days",
        type=int,
        default=3,
        help="TTL in days for scratch directories (default: 3)",
    )
    parser.add_argument(
        "--backup-ttl-days",
        type=int,
        default=7,
        help="TTL in days for SQLite backups (default: 7)",
    )
    parser.add_argument(
        "--keep-installs-n",
        type=int,
        default=2,
        help="Number of latest installs to keep (default: 2)",
    )
    parser.add_argument(
        "--journal-max-size",
        type=str,
        default="500M",
        help="Max size for journalctl vacuum (default: 500M)",
    )
    parser.add_argument(
        "--disk-threshold-pct",
        type=float,
        default=80.0,
        help="Disk usage alert threshold percentage (default: 80.0)",
    )

    args = parser.parse_args(argv)

    report = run_daily_hygiene(
        base_dir=args.base_dir,
        dry_run=args.dry_run,
        scratch_ttl_days=args.scratch_ttl_days,
        backup_ttl_days=args.backup_ttl_days,
        keep_installs_n=args.keep_installs_n,
        journal_max_size=args.journal_max_size,
        disk_threshold_pct=args.disk_threshold_pct,
        json_log_path=args.json_log,
    )

    mode = "DRY-RUN" if report["dry_run"] else "REAL"
    print(f"=== VPS Daily Hygiene ({mode}) ===")
    print(f"Base Directory:  {report['base_dir']}")
    print(f"Active Install:  {report['active_install']}")
    print(f"Total Freed:     {report['total_freed_bytes'] / (1024*1024):.2f} MB")
    print(f"Disk Usage:      {report['final_disk']['used_pct']}% (Threshold: {args.disk_threshold_pct}%)")

    tasks = report["tasks"]
    print(f"- Scratch:       {tasks['scratch']['pruned']} pruned ({tasks['scratch']['bytes_freed'] / (1024*1024):.2f} MB)")
    print(f"- Installs:      {tasks['installs']['pruned']} rotated ({tasks['installs']['bytes_freed'] / (1024*1024):.2f} MB)")
    print(f"- SQLite Baks:   {tasks['sqlite_backups']['pruned']} pruned ({tasks['sqlite_backups']['bytes_freed'] / (1024*1024):.2f} MB)")
    print(f"- Git Worktrees: {sum(r.get('pruned_count', 0) for r in tasks['git_worktrees']['results'])} pruned across {tasks['git_worktrees']['repos_checked']} repos")
    print(f"- Journal Logs:  Freed {tasks['system_logs'].get('bytes_freed', 0) / (1024*1024):.2f} MB")

    if report["final_disk"]["exceeded"]:
        print(f"[WARNING] Disk usage {report['final_disk']['used_pct']}% exceeds threshold {args.disk_threshold_pct}%!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
