#!/usr/bin/env python3
"""Portal de tareas — backend.

Lee y escribe el store canónico de pendientes (`pending.jsonl`) que comparte con
`scripts/pending_tasks.py`. No inventa un segundo sistema: el archivo es el mismo.

Invariantes del store que este servicio respeta:
  · Nada se borra: "quitar" una tarea la cierra con evidencia y autor.
  · La escritura es atómica (tmp + os.replace) y bajo lock (fcntl), para que el
    portal y los scripts de Hermes puedan escribir a la vez sin pisarse.
  · Cada cambio deja rastro en `.portal-events.jsonl` (quién, qué, cuándo).

Arranque:
    PORTAL_STORE=/opt/hermes-agent-data/brain/tasks/pending.jsonl \
    PORTAL_PORT=8791 PORTAL_BIND=100.86.8.81 python3 server.py
"""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BOG = timezone(timedelta(hours=-5))
HERE = os.path.dirname(os.path.abspath(__file__))

STORE = os.environ.get("PORTAL_STORE", "/opt/hermes-agent-data/brain/tasks/pending.jsonl")
EVENTS = os.environ.get("PORTAL_EVENTS", os.path.join(os.path.dirname(STORE), ".portal-events.jsonl"))
PORT = int(os.environ.get("PORTAL_PORT", "8791"))
BIND = os.environ.get("PORTAL_BIND", "127.0.0.1")

ESTADOS = ("abierto", "en_curso", "cerrado")
PRIORIDADES = ("alta", "media", "baja")
DUENOS = ("jonathan", "chucho", "compartido")
LOCK = threading.Lock()


def now_iso() -> str:
    return datetime.now(BOG).isoformat(timespec="seconds")


def load() -> list[dict]:
    if not os.path.exists(STORE):
        return []
    out = []
    with open(STORE, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"pending.jsonl línea {n} corrupta: {exc}") from exc
    return out


def save(items: list[dict]) -> None:
    tmp = STORE + ".portal.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    os.replace(tmp, STORE)


def next_id(items: list[dict]) -> str:
    nums = [int(i["id"].split("-")[1]) for i in items if str(i.get("id", "")).startswith("P-")]
    return f"P-{(max(nums) + 1) if nums else 1:02d}"


def sync_pin() -> None:
    """Refresca el mensaje fijado de Telegram sin bloquear la respuesta.

    Se lanza en un hilo aparte: si Telegram tarda o falla, el portal no se
    entera. El script es idempotente (hash del contenido) y se salta el envío
    si nada cambió.
    """
    def run():
        try:
            subprocess.run([sys.executable, os.path.join(HERE, "telegram_pin.py")],
                           timeout=30, capture_output=True)
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()


def log_event(actor: str, accion: str, id_: str, detalle: str = "") -> None:
    rec = {"ts": now_iso(), "actor": actor, "accion": accion, "id": id_, "detalle": detalle}
    with open(EVENTS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def mutate(fn):
    """Ejecuta `fn(items)` bajo lock exclusivo sobre el store."""
    with LOCK:
        lock_path = STORE + ".lock"
        os.makedirs(os.path.dirname(STORE), exist_ok=True)
        with open(lock_path, "a+") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            try:
                items = load()
                result = fn(items)
                save(items)
                return result
            finally:
                fcntl.flock(lk, fcntl.LOCK_UN)


def payload(items: list[dict]) -> dict:
    abiertos = [i for i in items if i.get("estado") != "cerrado"]
    semana = (datetime.now(BOG) - timedelta(days=7)).strftime("%Y-%m-%d")
    cerrados_semana = [
        i for i in items
        if i.get("estado") == "cerrado" and str(i.get("cerrado_en") or "") >= semana
    ]
    cuenta = {}
    for d in DUENOS:
        propias = [i for i in abiertos if i.get("dueno", "compartido") == d]
        cuenta[d] = {
            "abiertas": sum(1 for i in propias if i.get("estado") == "abierto"),
            "en_curso": sum(1 for i in propias if i.get("estado") == "en_curso"),
            "total": len(propias),
        }
    cerradas = [i for i in items if i.get("estado") == "cerrado"]
    cerradas.sort(key=lambda i: (str(i.get("cerrado_en") or ""), i["id"]), reverse=True)
    return {
        "items": abiertos,
        "cerradas": cerradas[:40],
        "meta": {
            "actualizado": now_iso(),
            "total_store": len(items),
            "abiertas": len(abiertos),
            "cerradas_semana": len(cerrados_semana),
            "por_dueno": cuenta,
            "mtime": os.path.getmtime(STORE) if os.path.exists(STORE) else 0,
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "PortalTareas/1.0"

    def log_message(self, format, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    # ---------- utilidades ----------

    def actor(self) -> str:
        for h in ("X-Auth-Request-Email", "X-Forwarded-User", "X-Auth-Request-User"):
            v = self.headers.get(h)
            if v:
                return v.split("@")[0]
        if self.client_address[0] in ("127.0.0.1", "::1"):
            return "local"
        return "anonimo"

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, ctype):
        with open(path, "rb") as fh:
            body = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    # ---------- rutas ----------

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            return self.send_file(os.path.join(HERE, "static", "index.html"), "text/html; charset=utf-8")
        if p == "/api/tasks":
            return self.send_json(payload(load()))
        if p == "/api/health":
            return self.send_json({"ok": True, "store": STORE, "actor": self.actor()})
        self.send_json({"error": "no encontrado"}, 404)

    def do_POST(self):
        p = urlparse(self.path).path
        body = self.read_json()
        actor = self.actor()

        if p == "/api/tasks":
            tarea = (body.get("tarea") or "").strip()
            if not tarea:
                return self.send_json({"error": "falta 'tarea'"}, 400)
            dueno = body.get("dueno") if body.get("dueno") in DUENOS else "compartido"
            prio = body.get("prioridad") if body.get("prioridad") in PRIORIDADES else "media"

            def crear(items):
                for i in items:
                    if i.get("estado") != "cerrado" and i["tarea"].strip().lower() == tarea.lower():
                        return None, i["id"]
                it = {
                    "id": next_id(items), "tarea": tarea, "estado": "abierto",
                    "prioridad": prio, "area": (body.get("area") or "general").strip(),
                    "dueno": dueno, "fuente": f"portal:{actor}", "alta": now_iso()[:10],
                    "nota": (body.get("nota") or "").strip(), "cerrado_en": None, "evidencia": None,
                }
                items.append(it)
                return it, None

            it, dup = mutate(crear)
            if it is None:
                return self.send_json({"duplicado": True, "id": dup}, 409)
            log_event(actor, "alta", it["id"], tarea[:120]); sync_pin()
            return self.send_json({"ok": True, "item": it}, 201)

        if p.startswith("/api/tasks/") and p.endswith("/close"):
            id_ = p.split("/")[3]
            ev = (body.get("evidencia") or "").strip() or f"Cerrada desde el portal por {actor}"

            def cerrar(items):
                for i in items:
                    if i["id"] == id_:
                        i["estado"] = "cerrado"
                        i["cerrado_en"] = now_iso()[:10]
                        i["evidencia"] = ev
                        return i
                return None

            it = mutate(cerrar)
            if not it:
                return self.send_json({"error": "id inexistente"}, 404)
            log_event(actor, "cierre", id_, ev[:120]); sync_pin()
            return self.send_json({"ok": True, "item": it})

        self.send_json({"error": "no encontrado"}, 404)

    def do_PATCH(self):
        p = urlparse(self.path).path
        if not p.startswith("/api/tasks/"):
            return self.send_json({"error": "no encontrado"}, 404)
        id_ = p.rstrip("/").split("/")[3]
        body = self.read_json()
        actor = self.actor()

        def editar(items):
            for i in items:
                if i["id"] != id_:
                    continue
                cambios = {}
                if body.get("estado") in ESTADOS:
                    cambios["estado"] = body["estado"]
                    if body["estado"] == "cerrado":
                        i["cerrado_en"] = now_iso()[:10]
                        i["evidencia"] = (body.get("evidencia") or f"Cerrada por {actor} desde el portal")
                if body.get("dueno") in DUENOS:
                    cambios["dueno"] = body["dueno"]
                if isinstance(body.get("tarea"), str) and body["tarea"].strip():
                    cambios["tarea"] = body["tarea"].strip()
                if isinstance(body.get("prioridad"), str) and body["prioridad"] in PRIORIDADES:
                    cambios["prioridad"] = body["prioridad"]
                if isinstance(body.get("nota"), str):
                    cambios["nota"] = body["nota"].strip()
                i.update({k: v for k, v in cambios.items() if k != "estado"})
                if "estado" in cambios:
                    i["estado"] = cambios["estado"]
                    if cambios["estado"] != "cerrado":
                        i["cerrado_en"] = None
                        i["evidencia"] = None
                return i, cambios
            return None, None

        it, cambios = mutate(editar)
        if not it:
            return self.send_json({"error": "id inexistente"}, 404)
        log_event(actor, "edicion", id_, json.dumps(cambios, ensure_ascii=False)[:160]); sync_pin()
        return self.send_json({"ok": True, "item": it})

    def do_DELETE(self):
        p = urlparse(self.path).path
        if not p.startswith("/api/tasks/"):
            return self.send_json({"error": "no encontrado"}, 404)
        id_ = p.rstrip("/").split("/")[3]
        actor = self.actor()

        def quitar(items):
            for i in items:
                if i["id"] == id_:
                    i["estado"] = "cerrado"
                    i["cerrado_en"] = now_iso()[:10]
                    i["evidencia"] = f"Quitada desde el portal por {actor} (el store no borra: se cierra)"
                    return i
            return None

        it = mutate(quitar)
        if not it:
            return self.send_json({"error": "id inexistente"}, 404)
        log_event(actor, "quitar", id_, "soft-delete"); sync_pin()
        return self.send_json({"ok": True, "item": it})


def main():
    srv = ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"portal-tareas en http://{BIND}:{PORT} · store={STORE}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
