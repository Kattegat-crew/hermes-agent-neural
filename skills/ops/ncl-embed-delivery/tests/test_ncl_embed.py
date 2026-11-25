#!/usr/bin/env python3
"""Tests deterministas del contrato ncl-embed/1 (sin red, sin Discord)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ncl_embed as ne  # noqa: E402


def _spec(**kw):
    base = {"title": "Informe de prueba", "status": "ok"}
    base.update(kw)
    return base


def test_status_define_color_y_emoji():
    ok = ne.embed_from_spec(_spec(status="ok"))
    err = ne.embed_from_spec(_spec(status="error"))
    assert ok["color"] == ne.PALETTE["ok"][0]
    assert err["color"] == ne.PALETTE["error"][0]
    assert ok["title"].startswith(ne.PALETTE["ok"][1])
    assert err["title"].startswith(ne.PALETTE["error"][1])


def test_status_desconocido_cae_a_info():
    e = ne.embed_from_spec(_spec(status="banana"))
    assert e["color"] == ne.PALETTE["info"][0]


def test_titulo_vacio_es_error():
    with pytest.raises(ValueError):
        ne.embed_from_spec({"title": "   ", "status": "ok"})


def test_titulo_largo_se_trunca_sin_exceder_256():
    e = ne.embed_from_spec(_spec(title="X" * 400))
    assert len(e["title"]) == 256
    assert e["title"].endswith("…")


def test_descripcion_larga_se_trunca_a_4096():
    e = ne.embed_from_spec(_spec(description="Y" * 9000))
    assert len(e["description"]) == 4096


def test_fields_se_capan_a_25_y_valor_a_1024():
    spec = _spec(fields=[{"name": f"f{i}", "value": "v" * 2000} for i in range(40)])
    e = ne.embed_from_spec(spec)
    # tres invariantes a la vez: campos, valor por campo y conjunto (Discord rechaza >6000)
    assert len(e["fields"]) <= 25
    assert all(len(f["value"]) <= 1024 for f in e["fields"])
    assert ne._embed_chars(e) <= ne.MAX_TOTAL
    assert e["fields"][0]["name"] == "f0"


def test_footer_y_timestamp_se_incluyen():
    e = ne.embed_from_spec(_spec(footer="NeuralCrew Labs · cron"))
    assert e["footer"]["text"] == "NeuralCrew Labs · cron"
    assert e["timestamp"].endswith("+00:00")


def test_field_por_cli_k_igual_v():
    e = ne.embed_from_spec(_spec(fields_raw=["Servidor=DEV (147.93.3.250)", "Duración=176 seg"]))
    assert e["fields"][0] == {"name": "Servidor", "value": "DEV (147.93.3.250)", "inline": True}
    assert e["fields"][1]["name"] == "Duración"


def test_emoji_custom_no_se_duplica():
    e = ne.embed_from_spec(_spec(title="🎯 Mi job", status="ok"))
    assert e["title"].startswith("🎯")


def test_post_dry_run_no_toca_red(monkeypatch):
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("no debe haber red en dry-run")

    monkeypatch.setattr(ne.urllib.request, "urlopen", boom)
    out = ne.post_embed("1567587939783806996", ne.embed_from_spec(_spec()), token="x", dry_run=True)
    assert out["dry_run"] is True
    assert called["n"] == 0


def test_cli_dry_run_imprime_json_valido():
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "ncl_embed.py"), "--channel", "1567587939783806996", "--title", "T",
         "--status", "warn", "--field", "A=1", "--dry-run"],
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["embeds"][0]["color"] == ne.PALETTE["warn"][0]
    assert payload["embeds"][0]["fields"][0]["name"] == "A"
