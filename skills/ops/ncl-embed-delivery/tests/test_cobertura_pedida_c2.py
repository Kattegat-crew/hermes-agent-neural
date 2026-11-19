#!/usr/bin/env python3
"""Cobertura que el reviewer del ciclo 2 pidió como no bloqueante: --spec-file y errores HTTP."""
import io
import json
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ncl_embed as ne  # noqa: E402

CANAL = "1567587939783806996"


def _cli(*args, **kwargs):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "ncl_embed.py"), *args],
        capture_output=True,
        text=True,
        timeout=60,
        **kwargs,
    )


def test_spec_file_desde_disco_construye_el_embed(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "channel": CANAL,
                "title": "✅ Prueba — 16-nov-2026",
                "status": "ok",
                "fields": [{"name": "Reservas", "value": "12"}],
                "footer": "NeuralCrew Labs · Prueba",
            }
        ),
        encoding="utf-8",
    )
    res = _cli("--spec-file", str(spec), "--dry-run")
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    embed = payload["embeds"][0]
    assert embed["title"] == "✅ Prueba — 16-nov-2026"
    assert payload["channel"] == CANAL
    assert embed["fields"][0]["name"] == "Reservas"


def test_spec_file_por_stdin():
    spec = json.dumps({"channel": CANAL, "title": "T", "status": "info"})
    res = subprocess.run(
        [sys.executable, str(SCRIPTS / "ncl_embed.py"), "--spec-file", "-", "--dry-run"],
        input=spec,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert res.returncode == 0, res.stderr
    # el título lleva el emoji del estado (info); se comprueba el texto, no el prefijo
    assert "T" in json.loads(res.stdout)["embeds"][0]["title"]


def test_spec_file_sin_canal_falla_claro(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"title": "T"}), encoding="utf-8")
    res = _cli("--spec-file", str(spec), "--dry-run")
    assert res.returncode != 0
    assert "--channel" in (res.stderr + res.stdout)


def test_http_401_aborta_con_el_codigo(monkeypatch):
    def falso(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"message": "401: Unauthorized"}')
        )

    monkeypatch.setattr(ne.urllib.request, "urlopen", falso)
    with pytest.raises(SystemExit) as exc:
        ne.post_embed(CANAL, ne.embed_from_spec({"title": "T"}), token="falso")
    assert "401" in str(exc.value)


def test_http_500_se_reporta_como_http_no_como_red(monkeypatch):
    def falso(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "Server Error", {}, io.BytesIO(b"{}"))

    monkeypatch.setattr(ne.urllib.request, "urlopen", falso)
    with pytest.raises(SystemExit) as exc:
        ne.post_embed(CANAL, ne.embed_from_spec({"title": "T"}), token="falso")
    assert "HTTP 500" in str(exc.value)


def test_red_inalcanzable_se_distingue_de_http(monkeypatch):
    def falso(req, timeout=None):
        raise urllib.error.URLError("Name or service not known")

    monkeypatch.setattr(ne.urllib.request, "urlopen", falso)
    with pytest.raises(SystemExit) as exc:
        ne.post_embed(CANAL, ne.embed_from_spec({"title": "T"}), token="falso")
    assert "red inalcanzable" in str(exc.value)
