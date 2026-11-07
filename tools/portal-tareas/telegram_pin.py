#!/usr/bin/env python3
"""Mantiene el mensaje fijado de pendientes en Telegram, editándolo en su sitio.

No manda un mensaje nuevo por cada cambio: reutiliza el mismo y lo reescribe,
así el chat no se llena. Si el mensaje ya no existe, crea otro y lo fija.

Uso:
    python3 telegram_pin.py          # sincroniza (crea o edita)
    python3 telegram_pin.py --force  # fuerza reenvío aunque no haya cambios
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

BOG = timezone(timedelta(hours=-5))
STORE = "/opt/hermes-agent-data/brain/tasks/pending.jsonl"
STATE = "/opt/hermes-agent-data/brain/tasks/.telegram-pin.json"
CHAT = "8709909260"
TOKEN_FILES = [
    "/opt/hermes-agent-data/.env",
    "/opt/hermes-agent-data/state-snapshots/20261005-165034-pre-update/.env",
]

ETQ = {"jonathan": "Jonathan", "chucho": "Chucho", "compartido": "Compartido"}
PRIO = {"alta": "🔴", "media": "🟡", "baja": "⚪"}


def token() -> str:
    for p in TOKEN_FILES:
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8", errors="ignore"):
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if v:
                    return v
    raise SystemExit("no encontré TELEGRAM_BOT_TOKEN")


def api(method: str, **params):
    t = token()
    url = f"https://api.telegram.org/bot{t}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="ignore")
        return {"ok": False, "status": exc.code, "error": body[:400]}


def load_items():
    items = []
    with open(STORE, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return [i for i in items if i.get("estado") != "cerrado"]


def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(items) -> str:
    total = len(items)
    hoy = datetime.now(BOG).strftime("%d/%m %H:%M")
    out = [f"📋 <b>PENDIENTES ABIERTOS</b> — {total}", f"<i>actualizado {hoy}</i>", ""]
    orden = {"alta": 0, "media": 1, "baja": 2}
    for dueno in ("jonathan", "chucho", "compartido"):
        grupo = [i for i in items if i.get("dueno", "compartido") == dueno]
        if not grupo:
            continue
        grupo.sort(key=lambda i: (orden.get(i.get("prioridad"), 1), i["id"]))
        out.append(f"<b>{ETQ[dueno]}</b> ({len(grupo)})")
        for i in grupo:
            p = PRIO.get(i.get("prioridad"), "🟡")
            marca = "▶️ " if i.get("estado") == "en_curso" else ""
            tarea = i["tarea"]
            if len(tarea) > 90:
                tarea = tarea[:87] + "…"
            out.append(f"{p} {marca}<code>{i['id']}</code> {esc(tarea)}")
        out.append("")
    out.append("<i>Detalle completo: reels.neuralcrewlabs.com/tareas</i>")
    txt = "\n".join(out)
    return txt[:4000]


def main():
    force = "--force" in sys.argv
    items = render(load_items())
    digest = hashlib.sha256(items.encode()).hexdigest()[:16]

    st = {}
    if os.path.exists(STATE):
        st = json.load(open(STATE, encoding="utf-8"))
    if not force and st.get("digest") == digest and st.get("message_id"):
        print("sin cambios, no se toca el mensaje")
        return 0

    mid = st.get("message_id")
    if mid:
        r = api("editMessageText", chat_id=CHAT, message_id=mid,
                text=items, parse_mode="HTML", disable_web_page_preview="true")
        if r.get("ok"):
            print(f"editado mensaje {mid}")
        else:
            print("edición falló:", str(r)[:150])
            if "message is not modified" in str(r):
                json.dump({"message_id": mid, "digest": digest}, open(STATE, "w"))
                return 0
            mid = None

    if not mid:
        r = api("sendMessage", chat_id=CHAT, text=items, parse_mode="HTML",
                disable_web_page_preview="true")
        if not r.get("ok"):
            print("envío falló:", str(r)[:200])
            return 1
        mid = r["result"]["message_id"]
        print(f"mensaje nuevo {mid}")
        p = api("pinChatMessage", chat_id=CHAT, message_id=mid, disable_notification="true")
        print("fijado:", p.get("ok"))

    json.dump({"message_id": mid, "digest": digest,
               "actualizado": datetime.now(BOG).isoformat(timespec="seconds")},
              open(STATE, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
