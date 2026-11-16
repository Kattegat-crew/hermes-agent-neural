#!/usr/bin/env python3
"""Tests deterministas de ncl_cron_embed (sin red, sin ejecutar comandos reales)."""
import json
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ncl_cron_embed as ce  # noqa: E402


def test_parse_convierte_clave_valor_en_field():
    fields, desc = ce.parse_output("Reservas: 12\nIngreso: USD 1.240\nTexto libre del día")
    assert fields[0] == {"name": "Reservas", "value": "12", "inline": True}
    assert fields[1]["name"] == "Ingreso"
    assert desc == "Texto libre del día"


def test_parse_no_convierte_urls():
    fields, desc = ce.parse_output("Repo: https://github.com/x/y")
    assert fields == []
    assert "github.com" in desc


def test_parse_capa_fields_a_ocho():
    texto = "\n".join(f"k{i}: v{i}" for i in range(20))
    fields, _ = ce.parse_output(texto)
    assert len(fields) == ce.MAX_FIELDS_FROM_STDOUT


def test_status_por_exit_y_stderr():
    assert ce.status_for(0, "") == "ok"
    assert ce.status_for(0, "warning") == "warn"
    assert ce.status_for(1, "") == "error"
    assert ce.status_for(124, "timeout") == "error"


def test_error_mete_stderr_en_descripcion():
    e = ce.build_embed(job="j", stderr="Traceback: boom", exit_code=2, duration_s=1.5)
    assert e["color"] == 15158332
    assert "Traceback" in e["description"]
    assert e["description"].startswith("```")


def test_fields_fijos_siempre_presentes():
    e = ce.build_embed(job="mi-job", stdout="a: 1", duration_s=2.0)
    names = [f["name"] for f in e["fields"]]
    assert "🔧 Job" in names and "⏱️ Duración" in names and "🚦 Exit" in names
    assert e["color"] == 3066993


def test_warn_cuando_hay_stderr_sin_fallo():
    e = ce.build_embed(job="j", stdout="a: 1", stderr="aviso", exit_code=0)
    assert e["color"] == 16776960


def test_silent_if_empty_no_publica(monkeypatch, capsys):
    monkeypatch.setattr(ce, "post_embed", lambda *a, **k: pytest.fail("no debe publicar"))
    rc = ce.main(["--job", "j", "--channel", "1", "--run", "true",
                  "--silent-if-empty", "--stdin-output", "   "])
    assert rc == 0
    assert "sin novedad" in capsys.readouterr().out


def test_publica_cuando_hay_salida(monkeypatch, capsys):
    sent = {}

    def fake_post(channel, embed, **kw):
        sent["channel"] = channel
        sent["embed"] = embed
        return {"message_id": "999"}

    monkeypatch.setattr(ce, "post_embed", fake_post)
    rc = ce.main(["--job", "j", "--channel", "42", "--run", "true",
                  "--stdin-output", "Pedidos: 3"])
    out = capsys.readouterr().out
    assert rc == 0 and sent["channel"] == "42"
    assert any(f["name"] == "Pedidos" for f in sent["embed"]["fields"])
    assert "publicado 999" in out


def test_dry_run_no_ejecuta_ni_publica(monkeypatch, capsys):
    monkeypatch.setattr(ce, "post_embed", lambda *a, **k: pytest.fail("no debe publicar"))
    rc = ce.main(["--job", "j", "--channel", "1", "--run", "exit 7", "--dry-run"])
    assert rc == 0
    assert "dry-run" in capsys.readouterr().out


def test_silencio_por_defecto_sin_salida(monkeypatch, capsys):
    monkeypatch.setattr(ce, "post_embed", lambda *a, **k: pytest.fail("no debe publicar"))
    rc = ce.main(["--job", "j", "--channel", "1", "--run", "true", "--stdin-output", ""])
    assert rc == 0
    assert "sin novedad" in capsys.readouterr().out


def test_always_publica_aunque_no_haya_salida(monkeypatch):
    sent = {}
    monkeypatch.setattr(ce, "post_embed", lambda ch, emb, **k: sent.update(emb=emb) or {"message_id": "1"})
    rc = ce.main(["--job", "j", "--channel", "1", "--run", "true", "--stdin-output", "", "--always"])
    assert rc == 0 and "embeds" not in sent and sent["emb"]["color"] == 3066993


def test_exit_no_cero_devuelve_codigo():
    # el wrapper propaga el exit del script para que el scheduler marque el fallo
    stdout, stderr, code, _ = ce.run_command(
        f'{sys.executable} -c "raise SystemExit(3)"', timeout=10
    )
    assert code == 3


def test_timeout_devuelve_124():
    stdout, stderr, code, dur = ce.run_command("sleep 3", timeout=1)
    assert code == 124 and "timeout" in stderr.lower()


def test_timeout_mata_el_grupo_y_no_deja_huerfanos(tmp_path):
    marca = tmp_path / "sobrevivio.txt"
    guion = tmp_path / "lento.py"
    guion.write_text(
        "import pathlib, time\n"
        "time.sleep(2)\n"
        f"pathlib.Path({str(marca)!r}).write_text('x')\n",
        encoding="utf-8",
    )
    _, _, code, _ = ce.run_command(f"{sys.executable} {guion}", timeout=1)
    assert code == 124
    time.sleep(2.5)
    assert not marca.exists(), "el proceso hijo sobrevivió al timeout"


def test_scrub_redacta_token_de_entorno():
    assert "abc123" not in ce.scrub("DISCORD_BOT_TOKEN=abc123")


def test_scrub_redacta_webhook():
    limpio = ce.scrub("https://discord.com/api/webhooks/123/abcdefghijklmnop")
    assert "abcdefghijklmnop" not in limpio


# --- redacción de credenciales: tabla de casos (rondas 2 y 3 del reviewer) ---

TOKEN = "MTA5abcdefghijklmnopqrstuv.abcdef.abcdefghijklmnopqrstuvwxyzABCDE"
S = "correcthorsebatterystaple"          # secreto opaco: sin forma de token conocido
OPACO = "s3cr3t0p4c0qu3"                 # tampoco tiene forma reconocible
_SFD = "IOSFODNN7EXAMPLE"
LARGO = "Zq8Lm2Np5Rt7Vw9Xy3Kb6Hd4Fg1Js0C"   # 32 chars: para patrones que exigen longitud
_SECRETOS = [TOKEN, "defghijklmnopqrstuvwxyzABCDEF", "correct", "horse", "battery", "staple",
             "abc123", "abcdefghijklmnopqrstuvwxyzABCDEF", S, OPACO, "shortsecret",
             _SFD, "supersecretovalor123", LARGO]
_WEBHOOK = ("https://discord.com/api/" + "v10/" + "webhooks/"
            + "123456789012345678/abcdefghijklmnopqrstuvwxyzABCDEF")

CASOS_FUGA = {
    # token con forma conocida
    "token_corto": "DISCORD_BOT_TOKEN=abc123",
    "split_indentado": "DISCORD_BOT_TOKEN=abc\n  defghijklmnopqrstuvwxyzABCDEF",
    "split_tab": "DISCORD_BOT_TOKEN=abc\n\tdefghijklmnopqrstuvwxyzABCDEF",
    "split_plano": "DISCORD_BOT_TOKEN=abc\ndefghijklmnopqrstuvwxyzABCDEF",
    "clave_sola": "DISCORD_BOT_TOKEN\n" + TOKEN,
    "dict_repr": "environ({'DISCORD_BOT_TOKEN': '" + TOKEN + "'})",
    "json_api_key": '{"api_key": "supersecretovalor123"}',  # valor en _SECRETOS
    "webhook_v10": _WEBHOOK,
    "webhook_sin_esquema": _WEBHOOK.replace("https://", ""),
    # ronda 4: claves que faltaban o valor en la línea siguiente
    "export_key_newline": "export DB_PASSWORD\n  " + S,
    "bot_token_label_nl": "Bot Token:\n  " + S,
    "bearer_label_nl": "Bearer:\n  " + S,
    "token_del_bot": "Token del bot:\n  " + S,
    "pass_key": "pass=" + S,
    "pwd_key": "pwd: " + S,
    "query_access_token": "https://example.com/cb?access_token=" + S,
    "query_api_key": "?a=1&api_key=" + S,
    "password_con_espacios": 'PASSWORD="correct horse battery staple"',  # review-gate:ignore — fixture del caso XKCD, no es credencial real
    "env_password_con_espacios": "DB_PASSWORD=correct horse battery staple",
    # ronda 5: cabecera en medio de línea, con token opaco (no lo caza _VALUE_PATTERNS)
    "midline_bearer_opaco": "HTTP 401: Bearer " + S,
    "midline_bot_opaco": "aviso: Bot " + S,
    "midline_bearer_curl": "curl -H 'authorization: Bearer " + S + "' https://x",
    "bearer_corto": "Bearer shortsecret",
    "bot_solo": "Bot " + TOKEN,
    "bearer_solo": "Bearer " + TOKEN,
    # ronda 5: concatenaciones sin separador que la subcadena sí cogía
    "mailpass": "MAILPASS=" + S,
    "userpass": "USERPASS=" + S,
    "dbpass_camel": "DBPass=" + S,
    "passphrase_mayus": "PASSPHRASE=" + S,
    "passphrase_min": "passphrase: " + S,
    "dbpassword_bare": "DBPASSWORD\n  " + S,
    # ronda 5: asignación en medio de una línea con más palabras
    "midline_pass": "INFO user=ana pass=" + S + " done",
    "midline_password_espacios": "auth falló: password=" + S + " (reintento)",
    # ronda 5: fila CSV y argv
    "csv_row": "2026-11-14,ana,ACTIVE,user@x.com,pass," + S,
    "argv_repr": "sys.argv=['p.py','--password','" + S + "']",
    "yaml_flow": "config: {name: x, password: " + S + ", active: true}",
    # ronda 5: prosa y castellano
    "prosa_es": "La contraseña es " + S,
    "contrasena_key": "CONTRASEÑA=" + S,
    # ronda 6: clave en medio de línea con valor en la misma línea
    "error_password": "error: password=" + S,
    "error_token": "ERROR: token=" + S,
    "aviso_pass": "aviso: pass=" + S,
    "nota_secreto": "nota: secreto=" + S,
    "auth_fallo_password": "auth falló: password=" + S + " (reintento)",
    # ronda 6: valor multi-palabra con espacios
    "prosa_multi_palabra": "La contraseña es correct horse battery staple",
    "password_is_espacios": "password is correct horse battery staple",
    # ronda 6: etiquetas con el valor en la MISMA línea
    "bearer_misma_linea": "Bearer: " + OPACO,
    "bearer_sin_espacio": "Bearer:" + OPACO,
    "token_de_acceso": "token de acceso: " + OPACO,
    "clave_de_acceso": "clave de acceso: " + OPACO,
    "credencial_sola": "credencial: " + OPACO,
    "cred_userinfo": "curl -u ana:" + OPACO + " https://x",
    "hash_query_token": "https://x/cb#access_token=" + OPACO,
    # ronda 7c: valor en la línea siguiente sin puntuación que lo delate
    "nueva_linea_4_palabras": "The new password is\n  correct horse battery staple",
    "nueva_linea_prosa": "La contraseña del usuario es\n  " + S,
    "nueva_linea_sin_puntuar": "credencial usada por el job\n" + OPACO,
    "etiqueta_bearer_sin_dospuntos": "Bearer\n  " + OPACO,
    # ronda 7c: query string con clave en castellano
    "query_clave": "https://x/cb?clave=" + OPACO,
    "query_contrasena": "https://x/cb?contrasena=" + OPACO,
    # ronda 7c: sufijos pegados que acaban en KEY / abreviaturas
    "privatekey_pegado": "PRIVATEKEY=" + OPACO,
    "mykey_pegado": "MYKEY=" + OPACO,
    "dbkey_pegado": "DBKEY=" + OPACO,
    "pw_corto": "pw=" + OPACO,
    "passcode": "passcode=" + OPACO,
    # ronda 8: raíz corta pegada en mayúsculas (el guard de longitud la descartaba)
    "dbpw": "DBPW=" + OPACO,
    "export_dbpw": "export DBPW=" + OPACO,
    "dbpw_con_espacios": "DBPW = " + OPACO,
    "mypw": "MYPW=" + OPACO,
    # ronda 8: abreviaturas y contraseñas en otros idiomas
    "passw": "PASSW=" + OPACO,
    "pword": "PWORD=" + OPACO,
    "pswd": "PSWD=" + OPACO,
    "passwort": "PASSWORT=" + OPACO,
    "senha": "SENHA=" + OPACO,
    "motdepasse": "MOTDEPASSE=" + OPACO,
    "wachtwoord": "WACHTWOORD=" + OPACO,
    "kennwort": "KENNWORT=" + OPACO,
    "heslo": "HESLO=" + OPACO,
    # ronda 8: query percent-encoded y separador `;`
    "query_percent": "https://x/?%63lave=" + OPACO,
    "query_semicolon": "https://x/p;token=" + OPACO,
    # ronda 9: abreviaturas pegadas y dígito final
    "dbpassw_pegado": "DBPASSW=" + OPACO,
    "mypassw_pegado": "MYPASSW=" + OPACO,
    "dbpswd_pegado": "DBPSWD=" + OPACO,
    "mypword_pegado": "MYPWORD=" + OPACO,
    "dbpwd_pegado": "DBPWD=" + OPACO,
    "dbpw_con_digito": "DBPW2=" + OPACO,
    "passwort_con_digito": "PASSWORT1=" + OPACO,
    "password_con_digito": "PASSWORD1=" + OPACO,
    # ronda 9: raíz corta en minúsculas con prefijo conocido
    "mailpass_minusculas": "mailpass: " + OPACO,
    "dbpw_minusculas": "dbpw: " + OPACO,
    "privatekey_minusculas": "privatekey: " + OPACO,
    # ronda 9: credencial en query string
    "query_credencial": "https://x/?credencial=" + OPACO,
    "query_credenciales": "https://x/?credenciales=" + OPACO,
    # ronda 10: el secreto va en la RUTA del webhook, no en un campo con nombre
    "slack_webhook_env": "SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/" + OPACO,
    "slack_webhook_export": "export SLACK_WEBHOOK=https://hooks.slack.com/services/T000/A000/" + OPACO,
    "activepieces_webhook": "AP_WEBHOOK_URL=http://100.73.30.29:8088/api/v1/webhooks/" + OPACO,
    "teams_webhook": 'TEAMS_WEBHOOK="https://example.webhook.office.com/webhookb2/abc@def/IncomingWebhook/' + OPACO + '/xyz"',
    "webhook_generico": "https://ejemplo.com/api/v1/webhooks/" + OPACO,
    "passkey": "passkey: " + OPACO,
    # ronda 11: la clase entera de webhooks, no solo 3 rutas conocidas
    "slack_workflows": "SLACK_WEBHOOK_URL=https://hooks.slack.com/workflows/T00000000/A00000000/123456789012345678/" + OPACO,
    "mattermost": "MATTERMOST_WEBHOOK_URL=https://mm.example.com/hooks/" + OPACO,
    "zapier": "ZAPIER_WEBHOOK_URL=https://hooks.zapier.com/hooks/catch/1234567/" + OPACO + "/",
    "webhook_url_generico": "WEBHOOK_URL=https://ejemplo.com/" + OPACO,
    "slack_sin_esquema": "hooks.slack.com/services/T000/B000/" + OPACO,
    # ronda 12: la credencial de los webhooks modernos va en el query, no en el nombre
    "azure_sig_traceback": "HTTPError: 404 for url: https://prod-12.westeurope.logic.azure.com:443/workflows/x/triggers/manual/paths/invoke?api-version=2016-06-01&sv=1.0&sig=" + OPACO,
    "query_signature": "callback: https://api.example.com/cb?signature=" + OPACO,
    "query_hmac": "https://api.example.com/cb?hmac=" + OPACO,
    "make_hook": "MAKE_HOOK_URL=https://api.example.com/make/" + OPACO,
    "n8n_webhook_test": "N8N_HOOK_URL=https://n8n.example.com/webhook-test/" + OPACO,
    "webhooks_plural": "WEBHOOKS_URL=https://api.example.com/notificar/" + OPACO,
    "web_hook_con_guion": "WEB_HOOK_URL=https://api.example.com/" + OPACO,
    "hook_singular": "PUT: https://hooks.example.com/hook/" + OPACO,
    # ronda 13: Make/Integromat en su forma real (token pegado al host, sin ruta)
    "make_url_sola": "HTTPError: 404 Client Error: Not Found for url: https://hook.eu1.make.com/" + OPACO,
    "integromat_url_sola": "https://hook.integromat.com/" + OPACO,
    # formatos de proveedor
    "slack": "xoxb-" + LARGO,
    "google": "AIza" + LARGO,
    "aws": "AK" + "IA" + _SFD,
}

def test_todos_los_casos_de_fuga_llevan_un_secreto_conocido():
    """Un caso cuyo valor no está en _SECRETOS pasa siempre: el assert sería vacuo.

    Este test existe porque en la ronda 6 y otra vez en la 13 los casos de fuga se
    quedaron sin secreto comprobable y la suite siguió verde.
    """
    sin_secreto = [n for n, t in CASOS_FUGA.items() if not any(s in t for s in _SECRETOS)]
    assert not sin_secreto, f"casos de fuga sin secreto verificable: {sin_secreto}"


# estos DOS parámetros son los que ejercitan la evidencia de seguridad: si desaparecen,
# la suite sigue verde sin probar nada. No los borres al reordenar el archivo.
@pytest.mark.parametrize("nombre,texto", CASOS_FUGA.items())
def test_scrub_no_deja_pasar_credenciales(nombre, texto):
    out = ce.scrub(texto)
    fugados = [s for s in _SECRETOS if s in out]
    assert not fugados, f"{nombre}: sigue filtrando {fugados}"


CASOS_LIMPIOS = {
    "prosa": "Informe: 12 pedidos, 0 fallos",
    "metricas": "Tokens usados: 1200",
    "ruta": "Guardado en /opt/data/backups/2026-11-14.tar.gz",
    "duracion": "Duracion: 176s",
    "multilinea": "Job: backup\nDuracion: 176s\nExit: 0",
    "prosa_bot": "El bot publicó 3 mensajes",
    "prosa_bearer": "Se envió el header Bearer en la petición",
    "exactitud": "Exactitud 100% en las respuestas donde aparece esta marca.",
    "max_tokens": "max_tokens: 4096",
    "tokens_mayus": "Tokens: 1200",
    "tokens_per_second": "tokens_per_second: 12",
    "tokenizer": "tokenizer: bpe",
    "bot_conectado": "Bot conectado: sí",
    "secretary": "Secretary: Ana",
    "bypass": "bypass: true",
    "bot_desconectado": "Bot desconectado",
    "bot_reconectado": "Bot reconectado tras 3 intentos",
    "bot_configurado": "bot configurado",
    "token_type": "token_type: Bearer",
    "token_count": "token_count: 1200",
    "token_length": "token_length: 40",
    "token_limit": "token_limit: 100",
    "webhook_id": "webhook_id: 123",
    "hookup": "hookup: OK",
    "salt_cero": "Salt: 0",
    "turkey": "Turkey: 5 kg",
    "turnkey": "turnkey solution entregada",
    "monkey": "Monkey: George",
    "hockey": "Hockey: final",
    "keyboard": "keyboard layout español",
    "keynote": "Keynote presentada",
    "monkey_patch": "monkey patch aplicado",
    "token_url": "token_url: https://auth.google.com/o/oauth2/token",
    "authorization_url": "authorization_url: https://accounts.google.com/o/oauth2/auth",
    "url_sin_credenciales": "https://ejemplo.com/page?x=1&y=2",
    "linea_de_job": "🔧 Job: content-intel-daily",
    "linea_de_exit": "🚦 Exit: 0",
    "linea_duracion": "⏱️ Duración: 3.0 seg",
    "extracto_banco": "• `2026-10-01` nu-tarjeta:Google — 31,500.00 COP",
    "conciliacion": "✅ 1 pares conciliados de 3 recibos × 36 líneas de extracto",
    "email": "user@x.com envió el formulario",
}


@pytest.mark.parametrize("nombre,texto", CASOS_LIMPIOS.items())
def test_scrub_no_destruye_texto_legitimo(nombre, texto):
    assert ce.scrub(texto) == texto


def test_error_no_filtra_secreto_en_la_descripcion():
    e = ce.build_embed(job="j", stderr="DISCORD_BOT_TOKEN=abc123", exit_code=2)
    assert "abc123" not in e["description"]


def test_stdout_con_secreto_tampoco_se_filtra():
    e = ce.build_embed(job="j", stdout="API_KEY: supersecretovalor", exit_code=0)
    assert "supersecretovalor" not in json.dumps(e, ensure_ascii=False)


def test_warn_incluye_stderr_en_la_descripcion():
    e = ce.build_embed(job="j", stderr="aviso: cuota al 80%", exit_code=0)
    assert e["color"] == 16776960
    assert "cuota al 80%" in e["description"]


def test_main_imprime_status_legible(monkeypatch, capsys):
    monkeypatch.setattr(ce, "post_embed", lambda *a, **k: {"message_id": "7"})
    rc = ce.main(["--job", "j", "--channel", "1", "--run", "true", "--stdin-output", "a: 1"])
    assert rc == 0
    assert "status=ok" in capsys.readouterr().out


def test_no_fields_deja_todo_el_stdout_en_la_descripcion():
    e = ce.build_embed(job="j", stdout="- Golden Game: mention n/a\nExactitud 100%",
                       exit_code=0, parse_fields=False)
    assert "- Golden Game: mention n/a" in e["description"]
    assert "Exactitud 100%" in e["description"]
    assert [f["name"] for f in e["fields"]] == ["🔧 Job", "⏱️ Duración", "🚦 Exit"]


def test_por_defecto_convierte_clave_valor_en_field():
    e = ce.build_embed(job="j", stdout="Publicadas: 3", exit_code=0)
    assert any(f["name"] == "Publicadas" for f in e["fields"])


def test_field_title_footer_tambien_se_redactan():
    e = ce.build_embed(job="j", stdout="ok", exit_code=0, title="Job TOKEN=abc123",
                       footer="f", extra_fields=["Token=abc123"])
    blob = json.dumps(e, ensure_ascii=False)
    assert "abc123" not in blob


def test_error_conserva_stdout_y_stderr():
    e = ce.build_embed(job="j", stdout="diagnostico util", stderr="Traceback: boom", exit_code=1)
    assert "diagnostico util" in e["description"]
    assert "Traceback" in e["description"]
