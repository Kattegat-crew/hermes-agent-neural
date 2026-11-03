"""Tests for scripts/hooks/guard_config_model_mutation.py (Config Shield)."""

import json
import subprocess
import sys
from pathlib import Path


HOOK_PATH = Path(__file__).resolve().parents[2] / "scripts" / "hooks" / "guard_config_model_mutation.py"


def _run_hook(payload: dict) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
    )
    return proc.returncode, proc.stdout.strip()


def test_guard_blocks_sed_in_place_mutation():
    code, out = _run_hook(
        {
            "tool_name": "terminal",
            "tool_args": {
                "command": "sed -i 's/deepseek-v4-flash/x-flash/' /opt/hermes-agent-data/config.yaml"
            },
        }
    )
    assert code == 2
    assert "Config Shield active" in out


def test_guard_blocks_execute_code_write_text():
    code, out = _run_hook(
        {
            "tool_name": "execute_code",
            "tool_args": {
                "code": "from pathlib import Path\nPath('/opt/hermes-agent-data/config.yaml').write_text('bad')"
            },
        }
    )
    assert code == 2
    assert "Config Shield active" in out


def test_guard_blocks_redirection_write():
    code, out = _run_hook(
        {
            "tool_name": "terminal",
            "tool_args": {"command": "echo 'model: foo' > ~/.hermes/config.yaml"},
        }
    )
    assert code == 2
    assert "Config Shield active" in out


def test_guard_blocks_file_modification_tools():
    for tool in ("write_file", "patch", "edit_file"):
        code, out = _run_hook(
            {
                "tool_name": tool,
                "tool_args": {"path": "/opt/hermes-agent-data/profiles/roshi/config.yaml"},
            }
        )
        assert code == 2
        assert "Config Shield active" in out


def test_guard_allows_safe_commands():
    code, out = _run_hook(
        {
            "tool_name": "terminal",
            "tool_args": {"command": "cat /opt/hermes-agent-data/config.yaml"},
        }
    )
    assert code == 0
    assert out == ""
