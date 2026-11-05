#!/usr/bin/env python3
"""notify_discord.py — notificación a Discord (canal de ops) con resumen de la
rendición y rutas de staging para revisión de Plon. Solo stdlib.

Token: DISCORD_BOT_TOKEN del entorno o de las fuentes canónicas del perfil
(/opt/hermes-agent-data/.env, heredado del patrón ncl_discord_mcp). Nunca imprime el token.

Canal por defecto: ⚔️・digital-vikings (forum, 1554961885160415283 — mapa Discord
2026-11-04: un hilo fijo por tema) → hilo fijo "📊 Rendición mensual" que se
REUTILIZA entre corridas (no se crea uno nuevo por run). Si falla, fallback a
🚨・alertas-prod. Override: RENDICION_DISCORD_CHANNEL / RENDICION_DISCORD_THREAD.

uso: python3 notify_discord.py --title "..." --body-file resumen.md [--dry]
"""
import argparse
import json
import os
import re
import sys
import urllib.request

API = "https://discord.com/api/v10"
UA = "DiscordBot (https://hermes-agent.nousresearch.com, 1)"
DEFAULT_CHANNEL = os.environ.get("RENDICION_DISCORD_CHANNEL", "1554961885160415283")  # ⚔️・digital-vikings (foro de trabajo)
DEFAULT_THREAD = os.environ.get("RENDICION_DISCORD_THREAD", "📊 Rendición mensual")
FALLBACK_CHANNEL = "1557152614045581373"  # 🚨・alertas-prod

ENV_PATHS = ("/etc/hermes-vault/profiles/default.secrets.env",
             "/etc/hermes-vault/root.secrets.env",
             "/opt/hermes-agent-data/.env",
             "/opt/data/.env")


def load_token():
    tok = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if tok:
        return tok
    for p in ENV_PATHS:
        try:
            with open(p, encoding="utf-8") as fh:
                m = re.search(r"^DISCORD_BOT_TOKEN=(\S+)", fh.read(), re.M)
                if m:
                    return m.group(1).strip().strip('"').strip("'")
        except (FileNotFoundError, PermissionError, OSError):
            continue
    try:  # fuente de secretos del perfil (Bitwarden) — esquema v0.22.x
        sys.path.insert(0, "/opt/hermes-agent")
        from hermes_cli.env_loader import hydrate_profile_secret_sources
        tok = hydrate_profile_secret_sources("/opt/hermes-agent-data").get(
            "DISCORD_BOT_TOKEN", "").strip()
        if tok:
            return tok
    except Exception:
        pass
    return None


def req(url, payload, method="POST"):
    data = json.dumps(payload).encode()
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Authorization": "Bot " + TOKEN,
                                        "Content-Type": "application/json",
                                        "User-Agent": UA})
    return urllib.request.urlopen(r, timeout=20)


def get_or_create_thread(forum_id, name):
    """Devuelve el id del hilo `name` en el foro (activo o archivado); lo crea si no existe."""
    hdr = {"Authorization": "Bot " + TOKEN, "User-Agent": UA}
    for url in (f"{API}/channels/{forum_id}/threads/active",
                f"{API}/channels/{forum_id}/threads/archived/public?limit=50"):
        try:
            data = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=15))
            for th in data.get("threads", []):
                if th.get("name") == name:
                    if "archived" in url:  # reabrir hilo archivado
                        try:
                            req(f"{API}/channels/{th['id']}", {"archived": False}, method="PATCH")
                        except Exception:
                            pass
                    return th["id"]
        except Exception:
            continue
    r = req(f"{API}/channels/{forum_id}/threads",
            {"name": name, "type": 11, "auto_archive_duration": 10080,
             "message": {"content": "Hilo fijo de la rendición mensual de cuentas "
                                    "(Golden Game · Lucky Brothers). Una corrida = un mensaje."}})
    return json.loads(r.read().decode()).get("id")


def send(channel_id, content):
    # forum (type 15): hilo FIJO reutilizable (mapa Discord 2026-11-04); texto: mensaje directo
    url = f"{API}/channels/{channel_id}"
    try:
        meta = json.load(urllib.request.urlopen(urllib.request.Request(
            url, headers={"Authorization": "Bot " + TOKEN, "User-Agent": UA}), timeout=15))
        if meta.get("type") == 15:
            tid = get_or_create_thread(channel_id, DEFAULT_THREAD)
            r = req(f"{API}/channels/{tid}/messages", {"content": content[:1900]})
            return r.status, tid
    except Exception:
        pass
    r = req(f"{url}/messages", {"content": content[:1900]})
    return r.status, channel_id


def main():
    global TOKEN
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--body-file", default=None)
    ap.add_argument("--body", default="")
    ap.add_argument("--dry", action="store_true", help="imprime el mensaje y no lo envía")
    args = ap.parse_args()

    body = args.body
    if args.body_file and os.path.exists(args.body_file):
        body = open(args.body_file, encoding="utf-8").read()
    content = f"**{args.title}**\n{body}".strip()

    if args.dry:
        print("DRY notify →\n" + content)
        return 0
    TOKEN = load_token()
    if not TOKEN:
        print("notify_discord: sin DISCORD_BOT_TOKEN — no se envía (no bloquea el run)")
        return 5
    try:
        status, cid = send(DEFAULT_CHANNEL, content)
        print(f"notify_discord: enviado al canal {cid} (HTTP {status})")
        return 0
    except Exception as e:
        try:
            status, cid = send(FALLBACK_CHANNEL, content)
            print(f"notify_discord: enviado a fallback {cid} (HTTP {status})")
            return 0
        except Exception as e2:
            print(f"notify_discord: fallo envío: {e} / fallback: {e2}")
            return 6


if __name__ == "__main__":
    sys.exit(main())
