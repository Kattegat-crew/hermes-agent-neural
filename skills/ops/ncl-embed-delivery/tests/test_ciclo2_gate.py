#!/usr/bin/env python3
"""Ciclo 2 del gate adversarial — un test por hallazgo del veredicto `8411c95cb88bbed1`."""
import sys
import types
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ncl_cron_embed as ce  # noqa: E402
import ncl_embed as ne  # noqa: E402


# ── ALTO · el sufijo benigno no puede eximir una línea entera ─────────────────
@pytest.mark.parametrize(
    "linea",
    [
        "db_password=ruta_file",
        "api_key=abc123",
        "export GITHUB_TOKEN=ghp_abcdef123456",
        "config: token=abc123",
    ],
)
def test_h1b_asignacion_con_sufijo_benigno_sigue_redactando(linea):
    assert ce._linea_es_sensible(linea) is True


@pytest.mark.parametrize(
    "prosa",
    [
        "[OK] webhook-gateway",
        "[OK] db-password-rotation",
        "el servicio de tokens responde",
    ],
)
def test_h1b_prosa_sin_asignacion_no_se_redacta(prosa):
    # sobre-redactar un informe entero es un fallo de producto, no una precaución
    assert ce._linea_es_sensible(prosa) is False


def test_h1b_identificador_con_sufijo_benigno_sigue_exento():
    # `token_url` describe: no es una fuga, y no debe empezar a redactarse
    assert ce._linea_es_sensible("token_url") is False
    assert ce._linea_es_sensible("password_field") is False


# ── ALTO · la redacción no puede depender de security.redact_secrets ─────────
def test_h2b_el_canonico_se_invoca_con_force(monkeypatch):
    visto: dict = {}

    def falso(text, **kw):
        visto.update(kw)
        return text

    monkeypatch.setattr(ce, "_CANONICAL_REDACT", falso)
    ce.scrub("Authorization: Basic dXN1YXJpbzpTdXAzclMzY3JldFB3ZA==")
    assert visto.get("force") is True, "sin force=True el canónico es un no-op cuando la opción está apagada"


def test_h2b_con_redactor_apagado_por_config_igual_redacta(monkeypatch):
    def canonico(text, force=False):
        return "<secret>" if force else text  # simula security.redact_secrets: false

    monkeypatch.setattr(ce, "_CANONICAL_REDACT", canonico)
    assert "<secret>" in ce.scrub("Authorization: Basic abcdefghij1234")


def test_h2b_firma_antigua_sin_force_no_revienta(monkeypatch):
    monkeypatch.setattr(ce, "_CANONICAL_REDACT", lambda text: text.replace("abc", "<x>"))
    assert "<x>" in ce.scrub("abc")


# ── MEDIO · HERMES_HOME se resuelve en cada llamada ─────────────────────────
def _sin_fuente_de_secretos(monkeypatch):
    fake = types.ModuleType("hermes_cli.env_loader")
    fake.hydrate_profile_secret_sources = lambda *a, **k: {}
    pkg = types.ModuleType("hermes_cli")
    pkg.env_loader = fake
    monkeypatch.setitem(sys.modules, "hermes_cli", pkg)
    monkeypatch.setitem(sys.modules, "hermes_cli.env_loader", fake)


def test_m3b_hermes_home_se_lee_en_cada_llamada(tmp_path, monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    _sin_fuente_de_secretos(monkeypatch)
    (tmp_path / ".env").write_text("DISCORD_BOT_TOKEN=token-de-prueba-123456\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # si el módulo conservara el valor del import, leería el .env real y este token no existiría
    assert ne.resolve_token() == "token-de-prueba-123456"
