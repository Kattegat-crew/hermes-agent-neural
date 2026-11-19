"""Tests for SDD governance discovery in the core repo and SubdirectoryHintTracker behavior."""

from pathlib import Path

from agent.prompt_builder import build_context_files_prompt
from agent.subdirectory_hints import SubdirectoryHintTracker

# Derived from this file's location so the test runs from any checkout (CI included):
# <repo>/tests/agent/test_sdd_governance_discovery.py -> <repo>.
CORE_ROOT = Path(__file__).resolve().parents[2]

GOVERNANCE_FILES = (
    "PROJECT_MEMORY.md",
    "ARCHITECTURE.md",
    ".agents/rules/01-sdd-workflow.md",
    ".agents/rules/02-vps-guardrails.md",
    ".agents/rules/03-code-standards.md",
    ".agents/rules/04-memory-and-reuse.md",
    ".atl/skill-registry.md",
)


def test_core_agents_md_includes_sdd_header_and_respects_size_cap() -> None:
    agents_md = (CORE_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert len(agents_md) <= 12_000

    rendered = build_context_files_prompt(
        cwd=str(CORE_ROOT),
        allow_install_tree_fallback=True,
        skip_soul=True,
    )
    assert "PROJECT_MEMORY.md" in rendered
    assert "ARCHITECTURE.md" in rendered
    assert ".agents/rules/01-sdd-workflow.md" in rendered
    assert ".specs/" in rendered
    assert "## What Hermes Is" in rendered
    assert "## Contribution rubric" in rendered

    for rel in GOVERNANCE_FILES:
        assert (CORE_ROOT / rel).is_file(), f"Missing core governance file: {CORE_ROOT / rel}"


def test_subdirectory_hints_activate_when_cwd_is_not_home(tmp_path: Path, monkeypatch) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    data_root = tmp_path / "hermes-agent-data"
    plugin_dir = data_root / "plugins" / "typesafe-skill-router"
    plugin_dir.mkdir(parents=True)
    (data_root / "AGENTS.md").write_text("# Root Data AGENTS\n", encoding="utf-8")
    (plugin_dir / "AGENTS.md").write_text("# Pre-Lector Cognitivo\n", encoding="utf-8")
    (plugin_dir / "__init__.py").write_text("# plugin\n", encoding="utf-8")

    # Observable behavior: a home-like cwd suppresses hint discovery entirely.
    home_tracker = SubdirectoryHintTracker(str(fake_home))
    assert home_tracker.check_tool_call("read_file", {"path": str(plugin_dir / "__init__.py")}) is None

    # A real project workspace injects the subdirectory's AGENTS.md once.
    root_tracker = SubdirectoryHintTracker(str(data_root))
    hint = root_tracker.check_tool_call("read_file", {"path": str(plugin_dir / "__init__.py")})
    assert hint is not None
    assert "Pre-Lector Cognitivo" in hint
