#!/usr/bin/env python3
"""Idempotent re-point of broken skill symlinks in a Hermes profile's skills dir.

The profile's `<home>/skills/` is frequently provisioned with symlinks pointing at
`/opt/data/skills/<name>` — a path that does NOT exist on this host. The canonical
catalog lives at `/root/hermes-agent-legacy-docker/data/skills/` and
`/root/hermes-agent-legacy-docker/data/skills-especialistas/`. This script repoints only the broken
links to the real catalog (with a nested-category fallback) and reports what remains.

Usage:
  repuntar-skills.py [--home /root/hermes-agent-legacy-docker/data/profiles/<name>/skills]

Dry-run first with `--dry-run`; run without it to apply. Idempotent — re-running
after a partial fix is safe.

Verified in prod 2026-08-26: repunted 356/356 broken links, 0 remaining.
"""
import argparse
import os
import sys
from pathlib import Path

BASE_DIRS = [
    Path("/root/hermes-agent-legacy-docker/data/skills"),
    Path("/root/hermes-agent-legacy-docker/data/skills-especialistas"),
]


def find_target(name: str):
    """Resolve a skill name against the canonical catalog, including nested cat dirs."""
    for base in BASE_DIRS:
        p = base / name
        if p.is_dir():
            return p
    for base in BASE_DIRS:
        for child in base.iterdir():
            if child.is_dir() and (child / name).is_dir():
                return child / name
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default=None,
                    help="Profile skills dir (default: ./skills relative to cwd)")
    ap.add_argument("--dry-run", action="store_true", help="Report without applying")
    args = ap.parse_args()

    skills_dir = Path(args.home) if args.home else Path("skills")
    if not skills_dir.is_dir():
        print(f"ERROR: no skills dir at {skills_dir}", file=sys.stderr)
        return 2

    fixed, skipped, not_found = 0, 0, []
    for link in skills_dir.iterdir():
        if not link.is_symlink():
            continue
        target = os.readlink(link)
        if not target.startswith("/opt/data/skills"):
            continue  # not in our scope; leave alone
        if not (link.is_file() or link.is_dir()):  # is_symlink and target missing == broken
            dest = find_target(link.name)
            if dest:
                if not args.dry_run:
                    link.unlink()
                    os.symlink(str(dest), link)
                fixed += 1
            else:
                not_found.append(link.name)
                skipped += 1

    action = "Repuntaria" if args.dry_run else "Repuntados"
    print(f"{action}: {fixed} | Sin destino (quedan): {skipped}")
    if not_found:
        print("Sin destino en catalogo:", ", ".join(sorted(not_found)[:30]), ...)
    return 0


if __name__ == "__main__":
    sys.exit(main())