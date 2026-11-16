"""Un test por hallazgo del veredicto `e900acb139321583` (gate ciclo 3)."""
import json
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import ncl_cron_embed as ce  # noqa: E402
import ncl_embed as ne  # noqa: E402

# ---------- H1 (high): claves entre comillas / dentro de llaves ----------

FUGAS = [
    '{"db_password": "Sup3rS3cret0"}',
    "{'api_key': 'ABC123XYZ789'}",
    "environ({'DB_PASSWORD': 'pw-real-123'})",
    'resp = {"auth": {"slack_webhook_url": "https://hooks.slack.com/services/T1/B1/xyz"}}',
    '{"token": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.firma"}',
]
MARCADORES = ["Sup3rS3cret0", "ABC123XYZ789", "pw-real-123", "T1/B1/xyz", "eyJhbGciOiJIUzI1NiJ9"]


def test_h1_json_y_dict_no_filtran_claves_entre_comillas():
    for crudo in FUGAS:
        salida = ce.scrub(crudo)
        assert not [m for m in MARCADORES if m in salida], f"fuga en {crudo[:40]!r}: {salida!r}"


LIMPIEZAS = [
    '{"token_count": 1200}',
    "{'user': 'ana', 'role': 'admin'}",
    '{"error": "not_found"}',
]


def test_h1_json_legitimo_no_se_destruye():
    for crudo in LIMPIEZAS:
        assert ce.scrub(crudo).strip() == crudo.strip()


# ---------- M1 (medium): los valores falsy no se vuelven "—" ----------

def test_m1_valor_cero_llega_como_cero():
    emb = ne.embed_from_spec({"title": "t", "fields": [{"name": "Fallos", "value": 0}]})
    assert emb["fields"][0]["value"] == "0"


def test_m1_valor_false_llega_como_false():
    emb = ne.embed_from_spec({"title": "t", "fields": [{"name": "OK", "value": False}]})
    assert emb["fields"][0]["value"] == "False"


def test_m1_name_vacio_sigue_siendo_guion():
    emb = ne.embed_from_spec({"title": "t", "fields": [{"name": None, "value": "x"}]})
    assert emb["fields"][0]["name"] == "—", "un nombre realmente ausente sí debe ser el sustituto"


def test_m1_el_conteo_de_chars_no_pierde_el_cero():
    emb = ne.embed_from_spec({"title": "t", "fields": [{"name": "a", "value": 0}]})
    assert ne._embed_chars(emb) >= len("a") + len("0")


# ---------- M2 (medium): install.sh --check no escribe ----------

def _run(*args, **env):
    entorno = {**os.environ, **env}
    return subprocess.run(["bash", str(RAIZ / "install.sh"), *args],
                          capture_output=True, text=True, env=entorno, timeout=120)


def test_m2_check_no_crea_el_directorio(tmp_path):
    destino = tmp_path / "no-existe"
    r = _run("--check", DEST_DIR=str(destino))
    assert not destino.exists(), "--check no debe escribir en disco"


def test_m2_flag_desconocido_no_instala(tmp_path):
    destino = tmp_path / "otro"
    r = _run("--help", DEST_DIR=str(destino))
    assert r.returncode == 2, f"--help debe fallar con código 2, salió {r.returncode}: {r.stdout}"
    assert "uso:" in (r.stdout + r.stderr).lower()
    assert not destino.exists(), "un flag desconocido no puede crear ni sobreescribir nada"
