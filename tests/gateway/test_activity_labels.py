"""Tests for gateway.activity_labels -- localized heartbeat activity labels.

The long-running heartbeat bubble must show a short, human-friendly,
localized phrase.  Raw tool names ("terminal") and internal activity strings
("receiving stream response") must never reach the user.
"""

from __future__ import annotations

import pytest

from gateway.activity_labels import activity_label, wait_kind
from agent.i18n import t


@pytest.fixture(autouse=True)
def _force_default_language(monkeypatch):
    """Pin the baseline language to English unless a test overrides it."""
    monkeypatch.delenv("HERMES_LANGUAGE", raising=False)


def test_empty_activity_returns_empty():
    assert activity_label(None) == ""
    assert activity_label({}) == ""


def test_known_tools_map_to_friendly_phrases():
    assert activity_label({"current_tool": "terminal"}) == "running commands"
    assert activity_label({"current_tool": "read_file"}) == "reviewing files"
    assert activity_label({"current_tool": "write_file"}) == "writing changes"
    assert activity_label({"current_tool": "vision_analyze"}) == "analyzing images"
    assert activity_label({"current_tool": "delegate_task"}) == "coordinating subtasks"


def test_browser_tools_map_to_web_phrase():
    assert activity_label({"current_tool": "browser_navigate"}) == "checking the web"
    assert activity_label({"current_tool": "browser_click"}) == "checking the web"


def test_unknown_tool_never_echoes_raw_name():
    label = activity_label({"current_tool": "mcp__coolify__get_version"})
    assert label == "using tools"
    assert "mcp__" not in label


def test_tool_takes_precedence_over_description():
    label = activity_label(
        {
            "current_tool": "terminal",
            "last_activity_description": "receiving stream response",
        }
    )
    assert label == "running commands"


def test_model_activity_descriptions_are_mapped():
    assert (
        activity_label(
            {"last_activity_description": "waiting for provider response (streaming)"}
        )
        == "waiting for the model"
    )
    assert (
        activity_label({"last_activity_description": "receiving stream response"})
        == "receiving the model's response"
    )
    assert (
        activity_label({"last_activity_desc": "waiting for non-streaming API response"})
        == "waiting for the model"
    )


def test_unknown_description_returns_empty():
    assert activity_label({"last_activity_description": "something internal"}) == ""


def test_wait_kind_detects_user_waits():
    assert (
        wait_kind({"last_activity_description": "waiting for user clarify response"})
        == "clarify"
    )
    assert wait_kind({"last_activity_desc": "waiting for user approval"}) == "approval"


def test_wait_kind_ignores_other_activity():
    assert wait_kind(None) is None
    assert wait_kind({}) is None
    assert wait_kind({"current_tool": "terminal"}) is None
    assert (
        wait_kind({"last_activity_description": "waiting for provider response"})
        is None
    )


def test_wait_templates_render_without_leftover_placeholders(monkeypatch):
    for lang in ("en", "es"):
        monkeypatch.setenv("HERMES_LANGUAGE", lang)
        for key in ("long_running.waiting_answer", "long_running.waiting_approval"):
            text = t(key, minutes=12)
            assert "12 min" in text, (lang, key, text)
            assert "{" not in text, (lang, key, text)


def test_spanish_locale(monkeypatch):
    monkeypatch.setenv("HERMES_LANGUAGE", "es")
    assert activity_label({"current_tool": "terminal"}) == "ejecutando comandos"
    assert activity_label({"current_tool": "unknown_tool"}) == "usando herramientas"
    assert (
        activity_label({"last_activity_description": "receiving stream response"})
        == "recibiendo la respuesta del modelo"
    )
