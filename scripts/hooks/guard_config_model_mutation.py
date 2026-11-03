#!/usr/bin/env python3
"""Pre-tool-call hook (Config Shield) that blocks chat-driven mutations of config.yaml.

Prevents operators or agents in WhatsApp/Discord/Telegram/CLI from altering the canonical
configuration (`config.yaml`), especially model definitions, providers, and fallbacks via:
- `terminal` (hermes config set, sed, redirections, python write scripts)
- `execute_code` (pathlib.write_text, open('w'), yaml.dump)
- `write_file`, `patch`, `edit_file`
"""

from __future__ import annotations

import json
import re
import sys

_CONFIG_YAML_RE = re.compile(r"(?:^|[/\s'\"])config\.ya?ml\b", re.IGNORECASE)
_HERMES_CONFIG_SET_RE = re.compile(r"\bhermes\s+config\s+set\b", re.IGNORECASE)
_WRITE_PATTERNS_RE = re.compile(
    r"(?:"
    r"\bsed\s+-[a-zA-Z]*i\b|"
    r">\s*[^|;&\n]*config\.ya?ml\b|"
    r"\btee\s+[^|;&\n]*config\.ya?ml\b|"
    r"\.write_text\(|"
    r"open\([^)]*config\.ya?ml[^)]*['\"][wa\+]"
    r")",
    re.IGNORECASE,
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_name = str(payload.get("tool_name") or payload.get("name") or "").strip()
    args = payload.get("tool_args") or payload.get("arguments") or {}
    if not isinstance(args, dict):
        return 0

    # 1. Shell / Script execution tools
    if tool_name in {"terminal", "execute_code"}:
        cmd = str(args.get("command") or args.get("code") or "")
        is_config_target = bool(_CONFIG_YAML_RE.search(cmd))
        if _HERMES_CONFIG_SET_RE.search(cmd) or (
            is_config_target and _WRITE_PATTERNS_RE.search(cmd)
        ):
            print(
                json.dumps(
                    {
                        "decision": "block",
                        "reason": (
                            "Config Shield active (model.lock_default_in_config=true): "
                            "Direct mutations to config.yaml via terminal/scripts are strictly blocked. "
                            "Use `/model <nombre>` for session-scoped model overrides."
                        ),
                    }
                )
            )
            return 2

    # 2. File modification tools
    if tool_name in {"write_file", "patch", "edit_file"}:
        path = str(args.get("path") or args.get("file_path") or "")
        if _CONFIG_YAML_RE.search(path):
            print(
                json.dumps(
                    {
                        "decision": "block",
                        "reason": (
                            "Config Shield active (model.lock_default_in_config=true): "
                            "Direct file edits to config.yaml via chat tools are blocked."
                        ),
                    }
                )
            )
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
