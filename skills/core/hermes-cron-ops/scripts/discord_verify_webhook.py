#!/usr/bin/env python3
"""Verifica la URL de un webhook de Discord contra la API del guild.

Uso:
  python3 discord_verify_webhook.py "https://discord.com/api/webhooks/<id>/<token>"
  python3 discord_verify_webhook.py <url> --guild <guild_id> --send "texto de prueba"

Por qué existe: un `50027 Invalid Webhook Token` suele ser UN carácter mal
copiado, no un webhook inexistente. Este script localiza el webhook por su id
en el guild, compara el token pegado contra el real (carácter por carácter) e
imprime la URL correcta. `--send` postea un mensaje de prueba (204 = ok) — es
un efecto real en el canal, úsalo solo para verificar (y bórralo después si es
ruido: DELETE /channels/{ch}/messages/{id} con el token del bot).

Requiere `DISCORD_BOT_TOKEN` en /opt/data/.env y permiso MANAGE_WEBHOOKS.
"""
import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://discord.com/api/v10"
UA = "DiscordBot (hermes,1.0)"
ENV = Path("/opt/data/.env")


def bot_token() -> str:
    for line in ENV.read_text().splitlines():
        if line.startswith("DISCORD_BOT_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("DISCORD_BOT_TOKEN no encontrado en /opt/data/.env")


def api(path: str, token: str | None = None, method: str = "GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"User-Agent": UA, "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bot {token}"
    req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        body = resp.read().decode()
        return resp.status, (json.loads(body) if body.strip() else None)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:300]


def created_at(webhook_id: str) -> str:
    ms = (int(webhook_id) >> 22) + 1420070400000
    return datetime.fromtimestamp(ms / 1000, timezone.utc).astimezone().isoformat()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--guild", help="guild_id (si el bot está en varios servidores)")
    ap.add_argument("--send", help="postear este texto de prueba en el canal")
    args = ap.parse_args()

    parts = args.url.rstrip("/").split("/")
    wid, given = parts[-2], parts[-1]
    token = bot_token()

    guild = args.guild
    if not guild:
        status, guilds = api("/users/@me/guilds", token)
        if status != 200:
            raise SystemExit(f"no pude listar guilds: {status} {guilds}")
        print("guilds:", [(g["id"], g["name"]) for g in guilds])
        if len(guilds) != 1:
            raise SystemExit("pasa --guild <id>")
        guild = guilds[0]["id"]

    status, hooks = api(f"/guilds/{guild}/webhooks", token)
    if status != 200:
        raise SystemExit(f"webhooks no accesibles ({status}) — falta MANAGE_WEBHOOKS: {hooks}")
    status, channels = api(f"/guilds/{guild}/channels", token)
    names = {c["id"]: c["name"] for c in channels} if status == 200 else {}

    target = next((h for h in hooks if h["id"] == wid), None)
    if target is None:
        print(f"✗ webhook {wid} (creado {created_at(wid)}) NO está en este guild;")
        print(f"  ids vistos: {[h['id'] for h in hooks]}")
        return 1

    channel = names.get(target.get("channel_id"), target.get("channel_id"))
    print(f"✓ webhook {wid} → #{channel} | nombre={target.get('name')!r} | creado={created_at(wid)}")
    real = target.get("token") or ""
    if real == given:
        print("✓ el token pegado coincide con el de la API")
    else:
        diffs = [(i, a, b) for i, (a, b) in enumerate(zip(real, given)) if a != b]
        print(f"✗ token DISTINTO (len real={len(real)} dado={len(given)}) diffs={diffs}")
        print(f"  URL correcta: https://discord.com/api/webhooks/{wid}/{real}")

    if args.send:
        status, body = api(f"/webhooks/{wid}/{real}", None, "POST", {"content": args.send})
        print("prueba enviada" if status == 204 else f"✗ prueba falló: {status} {body}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
