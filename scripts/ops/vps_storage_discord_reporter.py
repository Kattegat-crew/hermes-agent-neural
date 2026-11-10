#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VPS Storage Discord Morning Reporter
====================================

Reads the daily hygiene execution audit (/var/log/vps-hygiene.json) and
current live filesystem metrics, then publishes a rich Discord embed to the
dedicated thread in the '#🖥️・sistema-servers' forum channel.

Target Discord Thread:
- Guild: 1493354289266167808 (NeuralCrew Labs)
- Forum: 1554961888771575899 (#🖥️・sistema-servers)
- Thread: 1569546504442740881 (🧹 Higiene y Almacenamiento VPS (.250))
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure scripts path can resolve _discord_token
DATA_SCRIPTS_PATH = Path("/opt/data/scripts")
if DATA_SCRIPTS_PATH.is_dir() and str(DATA_SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(DATA_SCRIPTS_PATH))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vps_storage_discord_reporter")

DEFAULT_AUDIT_LOG = Path("/var/log/vps-hygiene.json")
DEFAULT_FORUM_CHANNEL_ID = "1554961888771575899"
DEFAULT_THREAD_ID = "1569546504442740881"
DEFAULT_THREAD_NAME = "🧹 Higiene y Almacenamiento VPS (.250)"


def resolve_discord_token(base_dir: Optional[Path] = None) -> str:
    """Retrieve the Discord bot token via the canonical loader."""
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if token:
        return token

    try:
        from _discord_token import discord_token
        tok = discord_token()
        if tok:
            return tok
    except Exception as exc:
        logger.warning("Failed importing _discord_token: %s", exc)

    hermes_home = base_dir or Path(os.environ.get("HERMES_HOME", "/opt/hermes-agent-data"))
    candidates = [hermes_home / ".env"]
    data_dir = os.environ.get("DATA_DIR")
    if data_dir:
        candidates.append(Path(data_dir) / ".env")

    for candidate in candidates:
        try:
            if candidate.is_file():
                for line in candidate.read_text(encoding="utf-8").splitlines():
                    if line.startswith("DISCORD_BOT_TOKEN="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except (OSError, AssertionError):
            pass
    return ""


def get_live_disk_metrics(mount_point: str = "/") -> Dict[str, Any]:
    """Calculate current live disk metrics."""
    total, used, free = shutil.disk_usage(mount_point)
    used_pct = round((used / total) * 100, 2)
    return {
        "mount_point": mount_point,
        "total_gb": round(total / (1024**3), 1),
        "used_gb": round(used / (1024**3), 1),
        "free_gb": round(free / (1024**3), 1),
        "used_pct": used_pct,
    }


def load_hygiene_audit(audit_path: Path) -> Optional[Dict[str, Any]]:
    """Load and parse the JSON hygiene audit report."""
    if not audit_path.is_file():
        logger.warning("Audit file not found: %s", audit_path)
        return None
    try:
        data = json.loads(audit_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.error("Failed loading hygiene audit from %s: %s", audit_path, exc)
        return None


def format_bytes_human(num_bytes: int) -> str:
    """Format bytes into readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} PB"


def build_discord_embed(
    live_disk: Dict[str, Any],
    audit_data: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Construct a structured Discord embed for morning reporting."""
    used_pct = live_disk["used_pct"]

    if used_pct >= 80.0:
        status_color = 0xE74C3C  # Red
        status_icon = "🔴 CRÍTICO"
    elif used_pct >= 75.0:
        status_color = 0xF39C12  # Orange
        status_icon = "🟡 ALERTA"
    else:
        status_color = 0x2ECC71  # Green
        status_icon = "🟢 ÓPTIMO"

    fields = [
        {
            "name": "💾 Ocupación Actual del Disco (/)",
            "value": f"**{live_disk['used_pct']}%** usado\n({live_disk['used_gb']} GB de {live_disk['total_gb']} GB)\nLibres: **{live_disk['free_gb']} GB**",
            "inline": True,
        },
        {
            "name": "🛡️ Estado de Capacidad",
            "value": f"{status_icon}\nUmbral Alerta: **80.0%**\nHost: **147.93.3.250 (DEV)**",
            "inline": True,
        },
    ]

    if audit_data:
        freed_bytes = audit_data.get("total_freed_bytes", 0)
        tasks = audit_data.get("tasks", {})
        scratch = tasks.get("scratch", {})
        installs = tasks.get("installs", {})
        baks = tasks.get("sqlite_backups", {})
        worktrees = tasks.get("git_worktrees", {})
        active_hash = audit_data.get("active_install", "N/A")

        summary_lines = [
            f"• **Liberado esta madrugada:** `{format_bytes_human(freed_bytes)}`",
            f"• **Scratch / Venvs:** {scratch.get('scanned', 0)} inspeccionados, {scratch.get('pruned', 0)} podados",
            f"• **Hermes Installs:** Activo `{active_hash[:12]}` protegido, {installs.get('pruned', 0)} rotados",
            f"• **Backups SQLite:** {baks.get('scanned', 0)} escaneados, {baks.get('pruned', 0)} purgados (TTL 7d)",
            f"• **Git Worktrees:** {worktrees.get('repos_checked', 0)} repositorios saneados",
            f"• **Journald Logs:** Vacuum ejecutado a 500 MB",
        ]

        fields.append({
            "name": "🧹 Saneamiento de la Madrugada (04:00 AM)",
            "value": "\n".join(summary_lines),
            "inline": False,
        })
    else:
        fields.append({
            "name": "🧹 Saneamiento de la Madrugada",
            "value": "ℹ️ No se encontró el registro `/var/log/vps-hygiene.json` de la madrugada.",
            "inline": False,
        })

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    embed = {
        "title": "🧹 Reporte Matutino de Almacenamiento e Higiene VPS",
        "description": f"Auditoría diaria programada del servidor DEV al **{now_str}**",
        "color": status_color,
        "fields": fields,
        "footer": {
            "text": "VPS Storage Janitor • Kattegat Crew & Dev Fleet",
        },
    }

    return embed


def post_to_discord_thread(
    thread_id: str,
    embed: Dict[str, Any],
    token: str,
    dry_run: bool = False,
) -> bool:
    """Post the report embed to the specified Discord thread."""
    if dry_run:
        logger.info("[DRY-RUN] Embed to post to thread %s:\n%s", thread_id, json.dumps(embed, indent=2))
        return True

    if not token:
        logger.error("Cannot post to Discord: missing bot token.")
        return False

    url = f"https://discord.com/api/v10/channels/{thread_id}/messages"
    payload = {
        "embeds": [embed],
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bot {token}",
            "User-Agent": "DiscordBot (https://neuralcrew.labs, 1.0)",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            success = resp.status in (200, 201, 204)
            if success:
                logger.info("Successfully posted morning report to Discord thread %s", thread_id)
            else:
                logger.warning("Discord API returned status %s", resp.status)
            return success
    except urllib.error.HTTPError as exc:
        err_msg = exc.read().decode("utf-8", errors="replace")
        logger.error("HTTP error posting to Discord (%s): %s", exc.code, err_msg)
        return False
    except Exception as exc:
        logger.error("Failed sending message to Discord thread %s: %s", thread_id, exc)
        return False


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="VPS Storage Discord Morning Reporter")
    parser.add_argument(
        "--audit-log",
        type=Path,
        default=DEFAULT_AUDIT_LOG,
        help="Path to vps-hygiene.json audit log",
    )
    parser.add_argument(
        "--thread-id",
        type=str,
        default=DEFAULT_THREAD_ID,
        help="Target Discord thread ID",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print embed to stdout without posting to Discord",
    )

    args = parser.parse_args(argv)

    live_disk = get_live_disk_metrics("/")
    audit_data = load_hygiene_audit(args.audit_log)
    embed = build_discord_embed(live_disk, audit_data)
    token = "" if args.dry_run else resolve_discord_token()

    success = post_to_discord_thread(
        thread_id=args.thread_id,
        embed=embed,
        token=token,
        dry_run=args.dry_run,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
