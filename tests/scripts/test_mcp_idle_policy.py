"""Tests de `scripts/mcp_idle_policy.py` (política de reciclado por inactividad).

Cubren la precedencia top-level del núcleo (``tools/mcp_tool_common.py:_get_lifecycle_seconds``),
la exclusión de servidores HTTP, la idempotencia byte a byte y los códigos de salida.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
SCRIPT = SCRIPTS_DIR / "mcp_idle_policy.py"
sys.path.insert(0, str(SCRIPTS_DIR))

import mcp_idle_policy as policy  # noqa: E402


def _load(text: str) -> Any:
    return YAML(typ="rt").load(text)


def test_apply_policy_creates_top_level_key() -> None:
    doc = _load("mcp_servers:\n  github:\n    command: npx\n    args: [github-mcp]\n")
    changes = policy.apply_policy(doc, 200)
    assert [(c.server, c.before, c.after) for c in changes] == [("github", None, 200.0)]
    assert doc["mcp_servers"]["github"]["idle_timeout_seconds"] == 200
    assert "lifecycle" not in doc["mcp_servers"]["github"]


def test_top_level_wins_over_lifecycle_like_the_core() -> None:
    doc = _load("mcp_servers:\n  a:\n    command: x\n    idle_timeout_seconds: 100\n"
                "    lifecycle:\n      idle_timeout_seconds: 200\n")
    assert policy.current_idle(doc["mcp_servers"]["a"]) == 100.0


def test_stale_top_level_is_updated_not_shadowed() -> None:
    """Regresión B1: con top-level 100, aplicar 200 debe dejar 200 EFECTIVO."""
    doc = _load("mcp_servers:\n  a:\n    command: x\n    idle_timeout_seconds: 100\n")
    changes = policy.apply_policy(doc, 200)
    assert [c.server for c in changes] == ["a"]
    cfg = doc["mcp_servers"]["a"]
    assert cfg["idle_timeout_seconds"] == 200
    assert policy.current_idle(cfg) == 200.0


def test_conflicting_lifecycle_copy_is_synchronised() -> None:
    doc = _load("mcp_servers:\n  a:\n    command: x\n    idle_timeout_seconds: 100\n"
                "    lifecycle:\n      idle_timeout_seconds: 150\n      max_lifetime_seconds: 3600\n")
    policy.apply_policy(doc, 200)
    cfg = doc["mcp_servers"]["a"]
    assert cfg["idle_timeout_seconds"] == 200
    assert cfg["lifecycle"]["idle_timeout_seconds"] == 200
    assert cfg["lifecycle"]["max_lifetime_seconds"] == 3600


def test_no_false_check_when_top_level_shadows() -> None:
    """Regresión B1: --check no debe dar OK si el valor efectivo difiere del pedido."""
    doc = _load("mcp_servers:\n  a:\n    command: x\n    idle_timeout_seconds: 100\n"
                "    lifecycle:\n      idle_timeout_seconds: 200\n")
    assert policy.apply_policy(doc, 200) != []


def test_apply_policy_preserves_existing_keys() -> None:
    doc = _load(
        "mcp_servers:\n"
        "  coolify:\n"
        "    command: npx\n"
        "    lazy: true\n"
        "    env:\n"
        "      TOKEN: abc\n"
        "    lifecycle:\n"
        "      max_lifetime_seconds: 3600\n"
    )
    policy.apply_policy(doc, 200)
    cfg = doc["mcp_servers"]["coolify"]
    assert cfg["lazy"] is True
    assert cfg["env"]["TOKEN"] == "abc"
    assert cfg["lifecycle"]["max_lifetime_seconds"] == 3600
    assert cfg["idle_timeout_seconds"] == 200
    assert "idle_timeout_seconds" not in cfg["lifecycle"]


def test_apply_policy_is_idempotent() -> None:
    doc = _load("mcp_servers:\n  a:\n    command: x\n")
    assert len(policy.apply_policy(doc, 200)) == 1
    assert policy.apply_policy(doc, 200) == []


def test_lifecycle_only_value_is_promoted_to_top_level() -> None:
    doc = _load("mcp_servers:\n  a:\n    command: x\n    lifecycle:\n      idle_timeout_seconds: 200\n")
    assert policy.current_idle(doc["mcp_servers"]["a"]) == 200.0
    assert [c.server for c in policy.apply_policy(doc, 200)] == ["a"]
    assert doc["mcp_servers"]["a"]["idle_timeout_seconds"] == 200
    assert policy.apply_policy(doc, 200) == []


def test_stale_lifecycle_copy_is_synced_when_top_level_is_correct() -> None:
    doc = _load("mcp_servers:\n  a:\n    command: x\n    idle_timeout_seconds: 200\n"
                "    lifecycle:\n      idle_timeout_seconds: 150\n")
    assert [c.server for c in policy.apply_policy(doc, 200)] == ["a"]
    assert doc["mcp_servers"]["a"]["lifecycle"]["idle_timeout_seconds"] == 200
    assert policy.apply_policy(doc, 200) == []


def test_http_wins_when_both_url_and_command() -> None:
    doc = _load("mcp_servers:\n  mix:\n    command: x\n    url: https://x/mcp\n")
    assert policy.collect_targets(doc) == []
    assert policy.http_servers(doc) == ["mix"]
    assert policy.apply_policy(doc, 200) == []
    assert "idle_timeout_seconds" not in doc["mcp_servers"]["mix"]


def test_invalid_values_are_ignored_like_the_core() -> None:
    doc = _load("mcp_servers:\n  a:\n    command: x\n    idle_timeout_seconds: abc\n"
                "  b:\n    command: y\n    idle_timeout_seconds: -5\n")
    assert policy.current_idle(doc["mcp_servers"]["a"]) is None
    assert policy.current_idle(doc["mcp_servers"]["b"]) is None
    assert len(policy.apply_policy(doc, 200)) == 2


def test_zero_disables_recycling() -> None:
    doc = _load("mcp_servers:\n  a:\n    command: x\n")
    policy.apply_policy(doc, 0)
    assert doc["mcp_servers"]["a"]["idle_timeout_seconds"] == 0


def test_http_servers_are_skipped() -> None:
    doc = _load("mcp_servers:\n  remote:\n    url: https://x/mcp\n  real:\n    command: y\n")
    assert policy.collect_targets(doc) == ["real"]
    assert policy.http_servers(doc) == ["remote"]
    assert [c.server for c in policy.apply_policy(doc, 200)] == ["real"]
    assert "idle_timeout_seconds" not in doc["mcp_servers"]["remote"]


def test_servers_filter_and_unknown_name() -> None:
    doc = _load("mcp_servers:\n  a:\n    command: x\n  b:\n    command: y\n")
    changes = policy.apply_policy(doc, 200, ["b"])
    assert [c.server for c in changes] == ["b"]
    assert "idle_timeout_seconds" not in doc["mcp_servers"]["a"]
    with pytest.raises(policy.PolicyError):
        policy.collect_targets(doc, ["nope"])
    with pytest.raises(policy.PolicyError):
        policy.collect_targets(doc, ["http-only"])


def test_servers_without_command_or_url_are_skipped() -> None:
    doc = _load("mcp_servers:\n  disabled:\n    enabled: false\n  real:\n    url: https://x/mcp\n")
    assert policy.collect_targets(doc) == []
    assert policy.http_servers(doc) == ["real"]


def test_missing_mcp_servers_raises() -> None:
    with pytest.raises(policy.PolicyError):
        policy.collect_targets(_load("skills:\n  on_demand: true\n"))


def _write_config(tmp_path: Path) -> Path:
    config = tmp_path / "config.yaml"
    config.write_text(
        "# comentario de cabecera que debe sobrevivir\n"
        "skills:\n"
        "  on_demand: true\n"
        "mcp_servers:\n"
        "  # servidor de prueba\n"
        "  github:\n"
        "    command: npx\n"
        "    lazy: true  # inline\n"
        "  paperless:\n"
        "    url: https://paperless/mcp\n",
        encoding="utf-8",
    )
    return config


def _run(args: list[str], env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(Path.home())}
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env)


def test_cli_writes_and_preserves_comments(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    result = _run(["--config", str(config), "--idle-seconds", "200"], {"HERMES_HOME": str(tmp_path)})
    assert result.returncode == 0, result.stderr
    text = config.read_text(encoding="utf-8")
    assert "# comentario de cabecera que debe sobrevivir" in text
    assert "# servidor de prueba" in text
    assert "lazy: true  # inline" in text
    doc = YAML(typ="rt").load(text)
    assert doc["mcp_servers"]["github"]["idle_timeout_seconds"] == 200
    assert "idle_timeout_seconds" not in doc["mcp_servers"]["paperless"]
    assert doc["skills"]["on_demand"] is True


def test_cli_second_run_is_byte_identical(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    first = _run(["--config", str(config)], {"HERMES_HOME": str(tmp_path)})
    assert first.returncode == 0, first.stderr
    before = config.read_bytes()
    mtime = config.stat().st_mtime_ns
    second = _run(["--config", str(config)], {"HERMES_HOME": str(tmp_path)})
    assert second.returncode == 0, second.stderr
    assert "sin cambios" in second.stdout
    assert config.read_bytes() == before
    assert config.stat().st_mtime_ns == mtime


def test_cli_check_exit_codes(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    pending = _run(["--config", str(config), "--check"])
    assert pending.returncode == 3
    assert config.read_text(encoding="utf-8").count("idle_timeout_seconds") == 0
    applied = _run(["--config", str(config), "--json"], {"HERMES_HOME": str(tmp_path)})
    assert applied.returncode == 0, applied.stderr
    payload = json.loads(applied.stdout)
    assert {c["server"] for c in payload["changed"]} == {"github"}
    assert payload["skipped_http"] == ["paperless"]
    assert _run(["--config", str(config), "--check"]).returncode == 0


def test_cli_dry_run_does_not_write(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    before = config.read_bytes()
    result = _run(["--config", str(config), "--dry-run"])
    assert result.returncode == 0, result.stderr
    assert config.read_bytes() == before


def test_cli_check_and_dry_run_are_mutually_exclusive(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    result = _run(["--config", str(config), "--check", "--dry-run"])
    assert result.returncode == 2
    assert "not allowed with argument" in result.stderr


def test_cli_invalid_config_exits_2(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("skills:\n  on_demand: true\n", encoding="utf-8")
    result = _run(["--config", str(config)])
    assert result.returncode == 2
    assert "mcp_servers" in result.stderr


def test_cli_unparseable_yaml_exits_2(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("mcp_servers:\n  a: [unclosed\n", encoding="utf-8")
    before = config.read_bytes()
    result = _run(["--config", str(config)])
    assert result.returncode == 2
    assert config.read_bytes() == before


def test_cli_negative_idle_exits_2(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    result = _run(["--config", str(config), "--idle-seconds", "-1"])
    assert result.returncode == 2


def test_cli_missing_file_exits_2(tmp_path: Path) -> None:
    result = _run(["--config", str(tmp_path / "nope.yaml")])
    assert result.returncode == 2


def test_write_failure_exits_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _write_config(tmp_path)
    monkeypatch.setattr(policy, "save_document", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    assert policy.main(["--config", str(config)]) == policy.EXIT_WRITE
