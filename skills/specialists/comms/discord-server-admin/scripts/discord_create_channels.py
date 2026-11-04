#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Crea canales de texto bajo una categoría en un servidor Discord vía REST.
Edita GUILD/CATEGORY/CANALES según necesidad. Requiere DISCORD_BOT_TOKEN en /opt/data/.env."""
import os, re, json, urllib.request, urllib.error

ENV = "/opt/data/.env"
GUILD = os.environ.get("DISCORD_GUILD", "1493354289266167808")          # NeuralCrew Labs
CATEGORY = os.environ.get("DISCORD_CATEGORY", "1493354289773674758")    # "Canales de texto"

CANALES = [
    ("canal-slug", "Descripción del canal."),
    # ("hermodr-connect", "Hermóðr — NeuralCrew Connect: atención multicanal, voz, WhatsApp, email."),
]

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

def create(name, topic):
    body = json.dumps({"name": name, "type": 0, "topic": topic, "parent_id": CATEGORY}).encode()
    req = urllib.request.Request(
        f"https://discord.com/api/v10/guilds/{GUILD}/channels",
        data=body,
        headers={"Authorization": f"Bot {get_token()}",
                 "User-Agent": "DiscordBot (https://neuralcrew.labs, 1.0)",
                 "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode())
            return r.status, d.get("id"), d.get("name")
    except urllib.error.HTTPError as e:
        return e.code, None, e.read().decode()[:200]

for name, topic in CANALES:
    code, cid, info = create(name, topic)
    print(f"{name}: {code} -> {info} ({cid})")