#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lista canales de un servidor Discord vía REST con User-Agent correcto.
Uso: python3 discord_list_channels.py [guild_id]
Requiere DISCORD_BOT_TOKEN en /opt/data/.env (o en $DISCORD_TOKEN)."""
import os, re, sys, json, urllib.request, urllib.error

ENV = "/opt/data/.env"
GUILD = sys.argv[1] if len(sys.argv) > 1 else "1493354289266167808"  # NeuralCrew Labs

def get_token():
    t = os.environ.get("DISCORD_TOKEN")
    if t:
        return t
    with open(ENV, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"DISCORD_BOT_TOKEN=(.+)", line.strip())
            if m:
                return m.group(1).strip().strip('"').strip("'")
    return None

def call(url):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bot {get_token()}",
        "User-Agent": "DiscordBot (https://neuralcrew.labs, 1.0)",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]

code, data = call(f"https://discord.com/api/v10/users/@me")
print(f"auth /users/@me: {code}", f"(bot {data.get('username', '')})" if code == 200 else f" -> {data}")

code, data = call(f"https://discord.com/api/v10/guilds/{GUILD}/channels")
if code == 200:
    for c in data:
        print(f"{c['id']} | type={c['type']} | #{c.get('name','')} | parent={c.get('parent_id')}")
    print(f"TOTAL: {len(data)}")
else:
    print(f"channels: {code} -> {data}")