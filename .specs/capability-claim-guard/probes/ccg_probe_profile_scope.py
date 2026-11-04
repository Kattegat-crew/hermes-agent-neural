"""Runtime probe: the capability claim guard answers for the OWNING profile only.

Review finding (round 1, blocking 1): with no resolvable owning home the gate fell back
to the ambient config, so a persistence-isolated fork (``agent/background_review.py:920``
sets ``_session_db = None`` and ``:1102`` still runs a turn) inherited the launch
profile's flag. This probe measures the fixed contract at runtime, not by reading code:

1. fork shape, ambient profile ENABLED       -> OFF  (fail closed, never ambient)
2. fork shape, ambient profile ENABLED       -> wire_turn captures no evidence
3. owning home DISABLED, ambient ENABLED     -> OFF  (owning profile wins)
4. owning home ENABLED, ambient DISABLED     -> ON   (activation still works)
5. owning home UNREADABLE                    -> OFF  (fail closed)

Usage (from the integrated worktree, or with PYTHONPATH pointing at the release):

    python .specs/capability-claim-guard/probes/ccg_probe_profile_scope.py [repo_root]

Exit code 0 only when every expectation holds. Throwaway homes only; the real profile
homes are never opened or written.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from agent.capability_claim_guard import is_enabled, wire_turn
from hermes_constants import (
    reset_hermes_home_override,
    set_hermes_home_override,
)


class _Agent:
    """Agent double carrying only its owning-profile identity (no tools, no prompt)."""

    def __init__(self, home: Path | None = None) -> None:
        if home is not None:
            self._session_db = type("_DB", (), {"db_path": str(home / "state.db")})()
        self.tools = []
        self.valid_tool_names = set()
        self._persist_disabled = False


def _home(root: Path, name: str, enabled: bool | None) -> Path:
    home = root / name
    home.mkdir(parents=True, exist_ok=True)
    if enabled is None:
        (home / "config.yaml").write_text("agent: [unclosed\n", encoding="utf-8")
    else:
        body = "    enabled: true\n" if enabled else "    enabled: false\n"
        (home / "config.yaml").write_text(
            "agent:\n  capability_claim_guard:\n" + body, encoding="utf-8"
        )
    return home


def main() -> int:
    results: list[tuple[str, object, object]] = []
    with tempfile.TemporaryDirectory(prefix="ccg-scope-") as tmp:
        root = Path(tmp)
        on = _home(root, "on", True)
        off = _home(root, "off", False)
        broken = _home(root, "broken", None)

        # 1-2: the fork shape of agent/background_review.py:920 under an ENABLED ambient home.
        token = set_hermes_home_override(str(on))
        try:
            fork = _Agent(home=None)
            fork._persist_disabled = True
            results.append(("fork under ambient ENABLED -> is_enabled", is_enabled(fork), False))
            wire_turn(fork, "probe-fork")
            results.append(
                ("fork under ambient ENABLED -> wire_turn evidence", fork._ccg_evidence, None)
            )
        finally:
            reset_hermes_home_override(token)

        # 3: owning profile OFF while the ambient one is ON.
        token = set_hermes_home_override(str(on))
        try:
            results.append(("owning OFF / ambient ON -> is_enabled", is_enabled(_Agent(off)), False))
        finally:
            reset_hermes_home_override(token)

        # 4: owning profile ON while the ambient one is OFF (the activation shape).
        token = set_hermes_home_override(str(off))
        try:
            results.append(("owning ON / ambient OFF -> is_enabled", is_enabled(_Agent(on)), True))
        finally:
            reset_hermes_home_override(token)

        # 5: unreadable owning config.
        results.append(("unreadable owning config -> is_enabled", is_enabled(_Agent(broken)), False))

        leaked = sorted(p.name for p in root.iterdir())
        results.append(("throwaway homes only (no real home touched)", leaked, ["broken", "off", "on"]))

    failed = 0
    for label, got, want in results:
        ok = got == want
        failed += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {label}: got={got!r} want={want!r}")
    print(f"\n{len(results) - failed}/{len(results)} expectations hold")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
