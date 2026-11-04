#!/usr/bin/env python3
"""Revisor generico con glm5.3-flash (NaN Builders) en STREAMING.

Uso: python3 nan_reviewer.py <prompt_file.md> <out_file.md> [max_tokens]

El prompt_file contiene TODO (instrucciones + material). Se separa
delta.reasoning_content de delta.content (el modelo razona mucho y con
max_tokens bajo devuelve vacio). Streaming para evitar el 524 de Cloudflare.
"""
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

PROMPT = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(sys.argv[2])
MAXTOK = int(sys.argv[3]) if len(sys.argv) > 3 else 20000

key = os.environ.get("NAN_API_KEY")
if not key:
    for env_path in ["/opt/hermes-agent-data/.env", "/root/hermes-agent-legacy-docker/data/.env", "/root/hermes-agent-legacy-docker/.env"]:
        p = pathlib.Path(env_path)
        if p.is_file():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.startswith("NAN_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
        if key:
            break
if not key:
    sys.exit("sin NAN_API_KEY")

payload = {
    "model": "glm5.3-flash",
    "messages": [
        {
            "role": "system",
            "content": "Eres un revisor senior independiente. Respondes en espanol, "
                       "tecnico y directo, sin relleno. No inventas hechos: si no "
                       "puedes verificar algo con el material, lo dices.",
        },
        {"role": "user", "content": PROMPT.read_text(encoding="utf-8")},
    ],
    "max_tokens": MAXTOK,
    "temperature": 0.2,
    "stream": True,
}
req = urllib.request.Request(
    "https://api.nan.builders/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/event-stream",
    },
)

t0 = time.time()
buf, rb, usage, finish = [], [], None, None
try:
    with urllib.request.urlopen(req, timeout=1500) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except Exception:
                continue
            if obj.get("usage"):
                usage = obj["usage"]
            for ch in obj.get("choices", []):
                if ch.get("finish_reason"):
                    finish = ch["finish_reason"]
                delta = ch.get("delta") or {}
                if delta.get("reasoning_content"):
                    rb.append(delta["reasoning_content"])
                if delta.get("content"):
                    buf.append(delta["content"])
except urllib.error.HTTPError as e:
    sys.exit(f"HTTPError {e.code}: {e.read()[:300]}")
except Exception as e:
    sys.exit(f"ERR {type(e).__name__}: {e}")

txt, reasoning = "".join(buf), "".join(rb)
OUT.write_text(txt, encoding="utf-8")
if reasoning:
    OUT.with_suffix(".reasoning.md").write_text(reasoning, encoding="utf-8")
print(
    f"[{OUT.name}] glm5.3-flash | {time.time() - t0:.0f}s | finish={finish} | "
    f"razonamiento={len(reasoning)} chars | respuesta={len(txt)} chars"
)
print(f"[{OUT.name}] usage: {json.dumps(usage) if usage else 'n/d'}")
