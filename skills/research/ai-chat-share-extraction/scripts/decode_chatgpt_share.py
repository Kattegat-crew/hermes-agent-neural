#!/usr/bin/env python3
"""decode_chatgpt_share.py — recupera la conversación completa de un link público de
ChatGPT (chatgpt.com/share/<id>) sin login, sin cookies y sin navegador.

Uso:
    python3 decode_chatgpt_share.py <url-o-archivo.html> [salida.md]

Por qué funciona: el HTML SSR (~1 MB) trae la conversación entera dentro de
    <script>window.__reactRouterContext.streamController.enqueue("[...]")</script>
codificada en el formato "flatten" (devalue / turbo-stream, React Router v7
single-fetch): array plano donde las referencias son índices del array, los objetos
son {"_<idx>": ref} y los enteros negativos son literales.

Límites: los outputs de plugins salen redactados por OpenAI; las imágenes adjuntas
son punteros internos (file-service://) no descargables sin sesión.
"""
import json
import os
import sys
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")
MARKER = "streamController.enqueue("
LITS = {-1: None, -2: None, -3: "NaN", -4: "Infinity", -5: None, -6: 0}
NOISE = {"thoughts", "reasoning_recap", "code", "execution_output", "model_editable_context"}
REDACTED = "The output of this plugin was redacted"


def fetch(src):
    if os.path.exists(src):
        return open(src, encoding="utf-8", errors="ignore").read()
    req = urllib.request.Request(src, headers={"User-Agent": UA, "Accept-Language": "es,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="ignore")


def js_string_at(html, start):
    """start apunta a la comilla de apertura; devuelve el literal crudo (con escapes)."""
    if html[start] != '"':
        raise ValueError("no hay string JS en la posicion esperada")
    i, buf = start + 1, []
    while i < len(html):
        c = html[i]
        if c == "\\":
            buf.append(html[i:i + 2]); i += 2; continue
        if c == '"':
            return "".join(buf)
        buf.append(c); i += 1
    raise ValueError("string JS sin cerrar")


def payload_array(html):
    i = html.find(MARKER)
    if i < 0:
        raise SystemExit("No hay payload streamController.enqueue en el HTML "
                         "(share caducado, no publico, o formato nuevo: revisar a mano)")
    q = html.index('"', i)
    inner = json.loads('"' + js_string_at(html, q) + '"')  # des-escapar string JS
    return json.loads(inner)                                # array plano (flatten)


def resolver(arr):
    cache = {}

    def val(v, d=0):
        if isinstance(v, str) or v is None:
            return v
        if isinstance(v, dict):
            out = {}
            for k, x in v.items():
                key = res(int(k[1:]), d + 1) if (isinstance(k, str) and k.startswith("_")) else k
                out[str(key)] = res(x, d + 1)
            return out
        if isinstance(v, list):
            return [res(x, d + 1) for x in v]
        return v

    def res(ref, d=0):
        if d > 80:
            return "<deep>"
        if isinstance(ref, bool) or ref is None:
            return ref
        if isinstance(ref, int):
            if ref < 0:
                return LITS.get(ref, "<lit%d>" % ref)
            if ref >= len(arr):
                return "<badref%d>" % ref
            if ref in cache:
                return cache[ref]
            cache[ref] = None
            cache[ref] = val(arr[ref], d + 1)
            return cache[ref]
        if isinstance(ref, float):
            return ref
        return val(ref, d + 1)

    return res


def find_conversation(root):
    stack, seen = [root], set()
    while stack:
        o = stack.pop()
        if id(o) in seen:
            continue
        seen.add(id(o))
        if isinstance(o, dict):
            lc = o.get("linear_conversation")
            if isinstance(lc, list) and lc:
                return o
            stack.extend(list(o.values())[:400])
        elif isinstance(o, list):
            stack.extend(o[:400])
    return None


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    src = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "chatgpt-share.md"
    html = fetch(src)
    print("html bytes:", len(html))
    arr = payload_array(html)
    print("elementos del payload:", len(arr))
    root = resolver(arr)(0)
    conv = find_conversation(root)
    if not conv:
        raise SystemExit("payload decodificado pero sin linear_conversation")
    msgs = []
    for n in conv["linear_conversation"]:
        m = (n or {}).get("message") if isinstance(n, dict) else None
        if not m:
            continue
        c = m.get("content") or {}
        parts = c.get("parts") or []
        msgs.append({
            "role": (m.get("author") or {}).get("role"),
            "ct": c.get("content_type"),
            "text": "\n".join(p for p in parts if isinstance(p, str)),
            "imgs": sum(1 for p in parts if isinstance(p, dict)),
        })
    roles = {}
    for m in msgs:
        roles[m["role"]] = roles.get(m["role"], 0) + 1
    title = conv.get("title") or "(sin titulo)"
    print("titulo:", title)
    print("nodos:", len(msgs), "| por rol:", roles)
    lines = ["# ChatGPT share — %s" % title, "", "- fuente: %s" % src,
             "- nodos: %d | roles: %s" % (len(msgs), roles), ""]
    kept = 0
    for i, m in enumerate(msgs):
        t = (m["text"] or "").strip()
        if not t or t.startswith(REDACTED) or m["ct"] in NOISE:
            continue
        kept += 1
        lines.append("### [%d] %s (%s, %d chars, %d img-refs)" % (i, m["role"], m["ct"], len(t), m["imgs"]))
        lines.append(t)
        lines.append("")
    open(out_path, "w", encoding="utf-8").write("\n".join(lines))
    print("mensajes con texto:", kept)
    print("salida:", os.path.abspath(out_path))


if __name__ == "__main__":
    main()
