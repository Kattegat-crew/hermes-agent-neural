#!/usr/bin/env python3
"""Pre-tool-call hook (Config Shield) that blocks chat-driven mutations of model.default in config.yaml.

Prevents operators or agents in WhatsApp/Discord/Telegram/CLI from overwriting the canonical
fleet model assignment (`model.default`, `model.provider`, `fallback_model`, `fallback_providers`)
via `terminal`, `execute_code`, `write_file`, or `patch`.
"""

from __future__ import annotations

import json
import re
import sys

_BLOCKED_CLI_RE = re.compile(
    r"\bhermes\s+config\s+set\s+(?:model(?:\.[a-zA-Z0-9_]+)?|fallback_model|fallback_providers)\b",
    re.IGNORECASE,
)
_CONFIG_YAML_PATH_RE = re.compile(r"(?:^|/)config\.ya?ml\b", re.IGNORECASE)
_MODEL_MUTATION_RE = re.compile(
    r"(?:model\s*:|default\s*:|fallback_model\s*:|fallback_providers\s*:)",
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

    if tool_name in {"terminal", "execute_code"}:
        cmd = str(args.get("command") or args.get("code") or "")
        if _BLOCKED_CLI_RE.search(cmd) or (
            _CONFIG_YAML_PATH_RE.search(cmd) and _MODEL_MUTATION_RE.search(cmd)
        ):
            print(
                json.dumps(
                    {
                        "decision": "block",
                        "reason": (
                            "Config Shield active (model.lock_default_in_config=true): "
                            "Mutating model.default or fallback_providers in config.yaml from chat tools is blocked. "
                            "Use `/model <nombre>` for session-scoped overrides."
                        ),
                    }
                )
            )
            return 2

    if tool_name in {"write_file", "patch", "edit_file"}:
        path = str(args.get("path") or args.get("file_path") or "")
        body = str(args.get("content") or args.get("patch") or args.get("replacement") or "")
        if _CONFIG_YAML_PATH_RE.search(path) and _MODEL_MUTATION_RE.search(body):
            print(
                json.dumps(
                    {
                        "decision": "block",
                        "reason": (
                            "Config Shield active (model.lock_default_in_config=true): "
                            "Direct edits to model/fallback sections in config.yaml are blocked."
                        ),
                    }
                )
            )
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
