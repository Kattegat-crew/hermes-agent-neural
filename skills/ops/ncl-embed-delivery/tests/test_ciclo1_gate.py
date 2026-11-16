#!/usr/bin/env python3
"""Ciclo 1 del gate adversarial (ronda 14) — un test por hallazgo bloqueante.

Cada test referencia el ID del hallazgo en el veredicto `bbea5aa9419b1139`.
Escriben primero en rojo: si alguno pasa sin el arreglo, no está probando nada.
"""
import json
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ncl_cron_embed as ce  # noqa: E402
import ncl_embed as ne  # noqa: E402

SECRETO = "s3cr3t0-op4co-1234567890"
SECRETO_LARGO = "valorfinal-9876543210"


# ── H1 · líneas sensibles consecutivas ────────────────────────────────────────
def test_h1_dos_claves_seguidas_no_filtran_el_valor_de_la_segunda():
    texto = f"DB_PASSWORD=\nAPI_KEY=\n  {SECRETO}\n"
    salida = ce.scrub(texto)
    assert SECRETO not in salida


def test_h1_cadena_de_tres_claves_tampoco():
    texto = f"A_PASSWORD=\nB_TOKEN=\nC_SECRET=\n  {SECRETO_LARGO}\n"
    assert SECRETO_LARGO not in ce.scrub(texto)


def test_h1_una_sola_clave_sigue_redactando_la_siguiente():
    texto = f"DB_PASSWORD=\n  {SECRETO}\n"
    assert SECRETO not in ce.scrub(texto)


# ── H2 · userinfo de URL con el redactor canónico apagado ─────────────────────
def test_h2_userinfo_se_redacta_sin_ayuda_del_canonico(monkeypatch):
    # aísla nuestra capa: con el canónico apagado, la fuga depende solo de scrub()
    monkeypatch.setattr(ce, "_CANONICAL_REDACT", False)
    salida = ce.scrub("GET https://admin:Sup3rS3cretPwd@db.interno.local/x")
    assert "Sup3rS3cretPwd" not in salida


def test_h2_userinfo_tambien_en_postgres_y_redis(monkeypatch):
    monkeypatch.setattr(ce, "_CANONICAL_REDACT", False)
    salida = ce.scrub(
        "postgresql://usuario:ClaveDeBase99@10.0.0.5:5432/db\n"
        "redis://default:ClaveRedis77@cache:6379"
    )
    assert "ClaveDeBase99" not in salida
    assert "ClaveRedis77" not in salida


# ── C1 · el runner no evalúa una cadena en un shell ───────────────────────────
def test_c1_rechaza_metacaracteres_de_shell():
    with pytest.raises(ValueError):
        ce.run_command("echo uno; echo dos", timeout=5)


def test_c1_rechaza_pipe_y_redireccion():
    for cmd in ("ls | head -1", "echo x > /tmp/x", "echo $(id)", "echo `id`"):
        with pytest.raises(ValueError):
            ce.run_command(cmd, timeout=5)


def test_c1_ejecuta_comando_simple_sin_shell(tmp_path):
    guion = tmp_path / "eco.py"
    guion.write_text("print('hola-sin-shell')", encoding="utf-8")
    out, err, code, _ = ce.run_command(f"{sys.executable} {guion}", timeout=30)
    assert code == 0
    assert "hola-sin-shell" in out


def test_c1_comando_vacio_es_error():
    with pytest.raises(ValueError):
        ce.run_command("   ", timeout=5)


# ── H4 · el drenaje del pipe tras el timeout está acotado ─────────────────────
def test_h4_acota_el_drenaje_del_pipe_tras_el_timeout(tmp_path, monkeypatch):
    # si el kill no funciona, el hijo sigue vivo con el pipe abierto: sin cota, cuelgue
    monkeypatch.setattr(ce, "_kill_tree", lambda proc: None)
    lento = tmp_path / "lento.py"
    lento.write_text("import time\nprint('vivo', flush=True)\ntime.sleep(120)\n", encoding="utf-8")
    t0 = time.monotonic()
    out, err, code, _ = ce.run_command(f"{sys.executable} {lento}", timeout=1)
    assert code == 124
    assert time.monotonic() - t0 < 30
    assert "timeout" in err.lower()


# ── M2 · un `warn` con stdout no pierde el stderr ────────────────────────────
def test_m2_warn_con_stdout_conserva_el_stderr():
    embed = ce.build_embed(
        job="prueba",
        stdout="Texto libre del día\n",
        stderr="warning: cola lenta",
        exit_code=0,
    )
    assert "cola lenta" in json.dumps(embed, ensure_ascii=False)


def test_m2_ok_sin_stderr_no_mete_bloque_vacio():
    embed = ce.build_embed(job="prueba", stdout="Reservas: 3\n", stderr="", exit_code=0)
    assert "```" not in (embed.get("description") or "")


# ── H3 · channel_id validado como snowflake ──────────────────────────────────
@pytest.mark.parametrize(
    "malo",
    ["1567587939783806996/../../x", "1567587939783806996?x=1", "abc", "", "123", "1" * 25],
)
def test_h3_channel_id_invalido_se_rechaza(malo):
    with pytest.raises(ValueError):
        ne.post_embed(malo, {"title": "t", "color": 1}, token="x")


def test_h3_channel_id_valido_pasa_en_dry_run():
    res = ne.post_embed("1567587939783806996", {"title": "t", "color": 1}, dry_run=True)
    assert res["dry_run"] is True


# ── M1 · límite de 6000 caracteres del conjunto del embed ────────────────────
def _total(embed: dict) -> int:
    total = len(embed.get("title") or "")
    total += len(embed.get("description") or "")
    total += sum(len(f.get("name") or "") + len(f.get("value") or "") for f in embed.get("fields") or [])
    total += len((embed.get("footer") or {}).get("text") or "")
    return total


def test_m1_embed_grande_se_recorta_por_debajo_de_6000():
    spec = {
        "title": "Informe enorme",
        "status": "ok",
        "description": "d" * 4000,
        "fields": [{"name": f"f{i}", "value": "v" * 1000} for i in range(6)],
        "footer": "NeuralCrew Labs · Prueba",
    }
    embed = ne.embed_from_spec(spec)
    assert _total(embed) <= 6000


def test_m1_embed_normal_no_se_toca():
    spec = {"title": "Corto", "status": "ok", "description": "texto", "fields": [{"name": "a", "value": "b"}]}
    assert _total(ne.embed_from_spec(spec)) == _total(ne.embed_from_spec(spec))
    assert ne.embed_from_spec(spec)["description"] == "texto"


# ── M3 · token vacío en .env no se devuelve como cadena vacía ────────────────
def _sin_fuente_de_secretos(monkeypatch):
    """Aísla resolve_token: el loader real de secretos del perfil encontraría el token vivo."""
    import types

    fake = types.ModuleType("hermes_cli.env_loader")
    fake.hydrate_profile_secret_sources = lambda *a, **k: {}
    pkg = types.ModuleType("hermes_cli")
    pkg.env_loader = fake
    monkeypatch.setitem(sys.modules, "hermes_cli", pkg)
    monkeypatch.setitem(sys.modules, "hermes_cli.env_loader", fake)


def test_m3_token_vacio_en_env_es_error_no_cadena_vacia(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    _sin_fuente_de_secretos(monkeypatch)
    (tmp_path / ".env").write_text("DISCORD_BOT_TOKEN=\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        ne.resolve_token()


def test_m3_token_en_blanco_tampoco_cuela(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    _sin_fuente_de_secretos(monkeypatch)
    (tmp_path / ".env").write_text('DISCORD_BOT_TOKEN="   "\n', encoding="utf-8")
    with pytest.raises(SystemExit):
        ne.resolve_token()
