"""Contract tests for the native-video QA script of the video-reel-pipeline skill.

These tests pin behaviour, not prose: the mp4 must travel as a native ``video_url``
part, an unparseable verdict must never approve, and the pass budget is a hard cap.
No network: the transport is injected.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "core" / "video-reel-pipeline" / "scripts" / "video_native_qa.py"

SCRIPT_TEXT = "Linea uno: el agente entiende.\nLinea dos: el agente recuerda."


@pytest.fixture
def mod(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_QA_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("NAN_BUILDERS_API_KEY", "test-key")
    spec = importlib.util.spec_from_file_location("video_native_qa_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "probe_duration", lambda _p: 12.0)
    monkeypatch.setattr(module, "run_pre_gate", lambda _v: (0, "ok"))
    return module


@pytest.fixture
def video(tmp_path):
    p = tmp_path / "film.mp4"
    p.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"payload" * 32)
    return p


@pytest.fixture
def guion(tmp_path):
    p = tmp_path / "guion.txt"
    p.write_text(SCRIPT_TEXT, encoding="utf-8")
    return p


class FakeTransport:
    """Returns queued verdicts and records every payload sent."""

    def __init__(self, *texts):
        self.texts = list(texts)
        self.calls = []

    def __call__(self, payload, api_key, timeout):
        self.calls.append(payload)
        text = self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]
        return {
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 1200, "completion_tokens": 90},
        }


def verdict(**over):
    base = {
        "passed": True,
        "score": 8,
        "voids": [],
        "collisions": [],
        "narration_sync": {"ok": True, "mismatches": []},
        "legibility": {"ok": True, "issues": []},
        "pacing": {"ok": True, "why": "ok"},
        "blocking": [],
    }
    base.update(over)
    return json.dumps(base)


def blocking(sev, t=3.0, what="caption overlaps title"):
    return {"severity": sev, "t": t, "what": what}


def run(mod, video, guion, transport, *extra):
    return mod.main(
        [str(video), "--script", str(guion), "--json", *extra],
        transport=transport,
    )


# ── CA1: el video va nativo ────────────────────────────────────────────────────
def test_video_travels_as_native_video_url_part(mod, video, guion):
    t = FakeTransport(verdict())
    assert run(mod, video, guion, t) == 0
    parts = t.calls[0]["messages"][0]["content"]
    assert [p["type"] for p in parts] == ["text", "video_url"]
    url = parts[1]["video_url"]["url"]
    assert url.startswith("data:video/mp4;base64,")
    assert SCRIPT_TEXT.splitlines()[0] in parts[0]["text"]


# ── CA2: la evidencia manda sobre el flag ─────────────────────────────────────
def test_critical_blocks_even_when_model_says_passed(mod, video, guion):
    t = FakeTransport(verdict(passed=True, blocking=[blocking("critical")]))
    assert run(mod, video, guion, t) == 1


def test_high_blocks_on_first_pass(mod, video, guion):
    t = FakeTransport(verdict(passed=False, blocking=[blocking("high")]))
    assert run(mod, video, guion, t) == 1
    assert len(t.calls) == 1, "un hallazgo high no necesita segunda pasada"


# ── CA3: medium pide confirmación ─────────────────────────────────────────────
def test_single_pass_medium_is_warning(mod, video, guion):
    t = FakeTransport(
        verdict(passed=False, blocking=[blocking("medium", t=4.0)]),
        verdict(passed=True),
    )
    assert run(mod, video, guion, t) == 0
    assert len(t.calls) == 2


def test_medium_confirmed_in_two_passes_blocks(mod, video, guion):
    t = FakeTransport(
        verdict(passed=False, blocking=[blocking("medium", t=4.0)]),
        verdict(passed=False, blocking=[blocking("medium", t=4.4)]),
    )
    assert run(mod, video, guion, t) == 1


# ── CA4: presupuesto duro ─────────────────────────────────────────────────────
def test_pass_budget_is_a_hard_cap(mod, video, guion):
    t = FakeTransport(
        verdict(passed=False, blocking=[blocking("medium", t=1.0)]),
        verdict(passed=False, blocking=[blocking("medium", t=9.0)]),
        verdict(passed=False, blocking=[blocking("medium", t=9.0)]),
    )
    run(mod, video, guion, t, "--max-passes", "2")
    assert len(t.calls) == 2


def test_max_passes_one_never_calls_twice(mod, video, guion):
    t = FakeTransport(verdict(passed=False, blocking=[blocking("medium")]))
    run(mod, video, guion, t, "--max-passes", "1")
    assert len(t.calls) == 1


# ── CA5: el gate determinista ahorra la llamada ───────────────────────────────
def test_pre_gate_failure_costs_zero_model_calls(mod, video, guion, monkeypatch):
    monkeypatch.setattr(mod, "run_pre_gate", lambda _v: (1, "3 frames vacios"))
    t = FakeTransport(verdict())
    assert run(mod, video, guion, t, "--pre-gate") == 1
    assert t.calls == []


# ── CA6: cache por hash ───────────────────────────────────────────────────────
def test_second_identical_run_hits_cache(mod, video, guion):
    t1 = FakeTransport(verdict())
    assert run(mod, video, guion, t1) == 0
    t2 = FakeTransport(verdict())
    assert run(mod, video, guion, t2) == 0
    assert len(t1.calls) == 1
    assert t2.calls == []


def test_force_bypasses_cache(mod, video, guion):
    run(mod, video, guion, FakeTransport(verdict()))
    t2 = FakeTransport(verdict())
    assert run(mod, video, guion, t2, "--force") == 0
    assert len(t2.calls) == 1


# ── CA7: fail-closed ──────────────────────────────────────────────────────────
def test_unparseable_verdict_is_not_an_approval(mod, video, guion):
    t = FakeTransport("Se ve bien, aprobado. 8/10.")
    assert run(mod, video, guion, t) == 2


def test_passed_false_without_findings_blocks(mod, video, guion):
    t = FakeTransport(verdict(passed=False, score=3))
    assert run(mod, video, guion, t) == 1


def test_truncated_verdict_missing_keys_is_invalid(mod, video, guion):
    t = FakeTransport(json.dumps({"passed": True, "score": 9}))
    assert run(mod, video, guion, t) == 2


# ── CA8: guardas de entrada ───────────────────────────────────────────────────
def test_oversize_video_is_refused_without_network(mod, video, guion):
    t = FakeTransport(verdict())
    assert run(mod, video, guion, t, "--max-mb", "0.000001") == 2
    assert t.calls == []


def test_missing_api_key_fails_closed(mod, video, guion, monkeypatch):
    monkeypatch.delenv("NAN_BUILDERS_API_KEY", raising=False)
    t = FakeTransport(verdict())
    assert run(mod, video, guion, t) == 2
    assert t.calls == []


def test_missing_video_is_an_error(mod, tmp_path, guion):
    t = FakeTransport(verdict())
    assert run(mod, tmp_path / "nope.mp4", guion, t) == 2
    assert t.calls == []


# ── CA9: dry-run ─────────────────────────────────────────────────────────────
def test_dry_run_sends_nothing(mod, video, guion, capsys):
    t = FakeTransport(verdict())
    assert run(mod, video, guion, t, "--dry-run") == 0
    assert t.calls == []
    out = capsys.readouterr().out
    assert "video/mp4" in out


# ── Contrato de decisión como API ────────────────────────────────────────────
def test_decide_reports_unconfirmed_medium_as_warning(mod):
    d = mod.decide([
        {"passed": False, "blocking": [blocking("medium", t=2.0)]},
        {"passed": True, "blocking": []},
    ])
    assert d["passed"] is True
    assert d["blocking"] == []
    assert d["warnings"], "el medium no confirmado debe quedar visible"


def test_prompt_orders_json_only(mod):
    p = mod.build_prompt(SCRIPT_TEXT, None, 12.0)
    assert "ONLY" in p.upper()
    assert "narration_sync" in p
    assert SCRIPT_TEXT in p


def test_json_mode_rejected_falls_back_without_losing_the_pass(mod, video, guion):
    class PickyTransport:
        def __init__(self):
            self.calls = []

        def __call__(self, payload, api_key, timeout):
            self.calls.append(payload)
            if "response_format" in payload:
                raise mod.QAError("HTTP 400: response_format is not supported")
            return {"choices": [{"message": {"content": verdict()}}], "usage": {}}

    t = PickyTransport()
    assert run(mod, video, guion, t) == 0
    assert len(t.calls) == 2, "reintenta una vez sin response_format"
    assert "response_format" not in t.calls[1]


def test_unparseable_pass_keeps_the_raw_reply_as_evidence(mod, video, guion, capsys):
    t = FakeTransport("Parece correcto, pero el JSON se cortó: {\"passed\": true, \"sco")
    assert run(mod, video, guion, t) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["raw"] and "JSON se cortó" in payload["raw"][0]


def test_reasoning_only_reply_is_parsed(mod, video, guion):
    """GLM con thinking deja content vacío y el texto en reasoning_content."""

    class ReasoningTransport:
        def __call__(self, payload, api_key, timeout):
            return {"choices": [{"message": {"content": "", "reasoning_content": verdict()}}],
                    "usage": {}}

    assert run(mod, video, guion, ReasoningTransport()) == 0
