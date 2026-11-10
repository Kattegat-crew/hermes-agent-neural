"""Regression: equal-specificity profile routes that name ONE profile are not a conflict.

The WhatsApp bridge keeps bidirectional ``lid-mapping-*.json`` files, so a route
declared for ``<lid>@lid``, ``<number>@s.whatsapp.net`` and the bare number all match
the same DM with ``specificity == 4``. ``_runtime_profile`` used to require a single
best match and raised ``admission_conflict`` even when every tied route named the same
profile — dropping every DM on that chat before admission ever ran.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from gateway.config import Platform
from gateway.profile_routing import ProfileRoute, parse_profile_routes
from gateway.session_ingress_context import _runtime_profile
from hermes_state_runtime import RuntimeStoreError

LID = "43001262956766"
NUMBER = "573166910728"
JID = f"{NUMBER}@s.whatsapp.net"

THREE_ALIAS_ROUTES = [
    {"name": "wa-lid", "platform": "whatsapp", "chat_id": f"{LID}@lid", "profile": "default"},
    {"name": "wa-jid", "platform": "whatsapp", "chat_id": JID, "profile": "default"},
    {"name": "wa-num", "platform": "whatsapp", "chat_id": NUMBER, "profile": "default"},
]


@pytest.fixture
def whatsapp_aliases():
    """Bidirectional LID mapping in the isolated HERMES_HOME, as the live bridge writes it."""
    from hermes_constants import get_hermes_home

    session_dir = get_hermes_home() / "whatsapp" / "session"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / f"lid-mapping-{LID}_reverse.json").write_text(json.dumps(NUMBER), encoding="utf-8")
    (session_dir / f"lid-mapping-{NUMBER}.json").write_text(json.dumps(LID), encoding="utf-8")
    return session_dir


def _runner(routes):
    return SimpleNamespace(config=SimpleNamespace(profile_routes=parse_profile_routes(routes)))


def _source(chat_id):
    return SimpleNamespace(
        platform=Platform.WHATSAPP, chat_id=chat_id, scope_id=None, thread_id=None,
        parent_chat_id=None, user_id=None, profile=None)


def test_three_alias_routes_for_one_profile_resolve(whatsapp_aliases):
    """The reported failure: three alias rows, one destination, no ambiguity."""
    runner = _runner(THREE_ALIAS_ROUTES)
    assert _runtime_profile(runner, _source(f"{LID}@lid"), None, "default", {}, False) == "default"
    assert _runtime_profile(runner, _source(JID), None, "default", {}, False) == "default"
    assert _runtime_profile(runner, _source(NUMBER), None, "default", {}, False) == "default"


def test_tied_routes_naming_different_profiles_still_conflict():
    """A genuine destination ambiguity must keep failing closed."""
    routes = [
        {"name": "a", "platform": "whatsapp", "chat_id": NUMBER, "profile": "default"},
        {"name": "b", "platform": "whatsapp", "chat_id": NUMBER, "profile": "other"},
    ]
    with pytest.raises(RuntimeStoreError) as excinfo:
        _runtime_profile(_runner(routes), _source(NUMBER), None, "default", {}, False)
    assert "admission_conflict" in str(excinfo.value)


def test_no_route_still_falls_back_to_the_owner():
    runner = _runner([{"name": "elsewhere", "platform": "telegram", "chat_id": "9", "profile": "x"}])
    assert _runtime_profile(runner, _source(NUMBER), None, "default", {}, False) == "default"


class TestUnambiguousRouteTarget:
    def test_tie_naming_one_profile_resolves(self):
        from gateway.profile_routing import unambiguous_route_target

        matches = [
            ProfileRoute(name="a", platform="whatsapp", profile="default", chat_id=NUMBER),
            ProfileRoute(name="b", platform="whatsapp", profile="default", chat_id=JID),
        ]
        assert unambiguous_route_target(matches) == "default"

    def test_tie_naming_two_profiles_is_ambiguous(self):
        from gateway.profile_routing import unambiguous_route_target

        matches = [
            ProfileRoute(name="a", platform="whatsapp", profile="default", chat_id=NUMBER),
            ProfileRoute(name="b", platform="whatsapp", profile="other", chat_id=NUMBER),
        ]
        assert unambiguous_route_target(matches) is None

    def test_most_specific_tier_wins_over_a_broader_tie(self):
        from gateway.profile_routing import unambiguous_route_target

        matches = [
            ProfileRoute(name="chat", platform="whatsapp", profile="routed", chat_id=NUMBER),
            ProfileRoute(name="g1", platform="whatsapp", profile="a"),
            ProfileRoute(name="g2", platform="whatsapp", profile="b"),
        ]
        assert unambiguous_route_target(matches) == "routed"

    def test_no_matches_resolves_to_nothing(self):
        from gateway.profile_routing import unambiguous_route_target

        assert unambiguous_route_target([]) is None
