#!/usr/bin/env python3
"""Regenerador automático del tablero de prioridades del foro de tickets (NeuralCrew).

Vista derivada: los mensajes del tablero NO se editan a mano; se recalculan aquí.

Estado y curación: `/opt/hermes-agent-data/ticket-board/board.json`
  - `sections[]`: bloques curados (título + entradas con texto humano por ticket)
  - `sin_resp`: bloque de tickets sin responsable + texto fijo de reconciliación
  - `known_open`: ids abiertos en la última corrida (para el Δ)

Qué hace cada corrida:
  (1) releer tags del foro (activos + archivados), (2) soltar lo Cerrado / meter lo nuevo,
  (3) recalcular conteos y Δ, (4) renderizar y PATCH solo lo que cambió.

Modos:
  --seed    construye board.json desde los mensajes vivos del tablero (uso único)
  --check   renderiza y reporta qué cambiaría, sin escribir (dry-run)
  --publish publica (default; lo que corre el cron y el hook de eventos)

Salida por stdout: JSON {changed, patched, posted, rendered_chars}.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, "/opt/hermes-agent-data/scripts")
from _discord_token import discord_token  # noqa: E402

GUILD = "1493354289266167808"
FORUM = "1554957746980261938"
BOARD_ROOT = "1569356056176361605"
STATE_PATH = Path("/opt/hermes-agent-data/ticket-board/board.json")
RUN_LOG = Path("/opt/hermes-agent-data/ticket-board/last-run.json")

STATE_TAGS = {"Pendiente", "En curso", "En revisión", "Cerrado", "Bloqueado"}
OPEN_TAGS = {"Pendiente", "En curso", "En revisión", "Bloqueado"}
MARCAS = {"En curso": " *En curso*", "En revisión": " *En revisión*",
          "Bloqueado": " *Bloqueado*"}
_ua = "DiscordBot (hermes,1.0)"
RE_ENTRY = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*\s*(?:—\s*)?(.*?)\s*\[(\d{17,})\]\([^)]*\)\s*$")
RE_BULLET = re.compile(r"^•\s+\*\*(.+?)\*\*\s*(?:—\s*)?(.*?)\s*\[(\d{17,})\]\([^)]*\)\s*$")


# ------------------------------------------------------------------ REST
def api(path: str, method: str = "GET", body: dict | None = None,
        params: dict | None = None):
    url = "https://discord.com/api/v10" + path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    data = json.dumps(body).encode() if body is not None else None
    token = discord_token()
    if not token:
        raise RuntimeError("no discord token")
    for attempt in range(6):
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bot {token}", "User-Agent": _ua,
            "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                time.sleep(float(exc.headers.get("Retry-After", "2")) + 0.5)
                continue
            if exc.code == 404:
                return None
            raise RuntimeError(f"{exc.code} {path}: {exc.read().decode()[:300]}")
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"retries agotados: {path}")


def link(tid: str) -> str:
    return f"[{tid}](https://discord.com/channels/{GUILD}/{tid})"


def snapshot_foro() -> tuple[dict[str, str], list[dict]]:
    forum = api(f"/channels/{FORUM}") or {}
    tags = {t["id"]: t["name"] for t in forum.get("available_tags", [])}
    hilos: dict[str, dict] = {}
    for t in (api(f"/guilds/{GUILD}/threads/active") or {}).get("threads", []):
        if t.get("parent_id") == FORUM:
            hilos[t["id"]] = t
    before = None
    for _ in range(8):  # archivados: también cuentan si su tag dice abierto
        params = {"limit": "100"}
        if before:
            params["before"] = before
        page = api(f"/channels/{FORUM}/threads/archived/public", params=params) or {}
        if not page.get("threads"):
            break
        for t in page["threads"]:
            hilos.setdefault(t["id"], t)
        if not page.get("has_more"):
            break
        before = page["threads"][-1].get("archive_timestamp")
        time.sleep(0.3)

    registros = []
    for tid, t in hilos.items():
        if tid == BOARD_ROOT:
            continue
        archivado = bool(t.get("thread_metadata", {}).get("archived", False))
        estado = next((tags[x] for x in (t.get("applied_tags") or [])
                       if tags.get(x) in STATE_TAGS), None)
        registros.append({
            "id": tid,
            "estado": estado,
            # archivado sin tag de estado = hilo muerto: no es ticket abierto
            "abierto": (estado in OPEN_TAGS) or (estado is None and not archivado),
            "responsables": [tags[x] for x in (t.get("applied_tags") or [])
                             if tags.get(x) in ("Jonathan", "Chucho")],
            "name": t.get("name") or "",
            "archived": archivado,
        })
    return tags, registros


# ----------------------------------------------------------------- render
def render(state: dict, snap: list[dict]) -> tuple[list[dict], list[dict]]:
    por_id = {r["id"]: r for r in snap}
    abiertos = [r for r in snap if r["abierto"]]
    por_dueño = lambda tag: [r for r in abiertos if tag in r["responsables"]]  # noqa: E731
    n_j, n_c = len(por_dueño("Jonathan")), len(por_dueño("Chucho"))
    compartidos = len([r for r in abiertos
                       if {"Jonathan", "Chucho"} <= set(r["responsables"])])
    archivados = len([r for r in abiertos if r["archived"]])
    ahora = time.strftime("%d-%b %H:%M", time.localtime())

    def encabezado() -> str:
        return (
            "**Estado:** Pendiente · **Entorno:** DEV · **Responsable:** Jonathan · "
            "**Prioridad:** Alta\n"
            f"**Regenerado:** {ahora} (America/Bogota) · **Fuente:** tags del foro + "
            "línea `Estado:` del raíz + actividad de cada hilo\n"
            f"**Alcance:** {len(snap)} hilos → **{len(abiertos)} tickets de trabajo abiertos** "
            f"(+ este tablero · {len(abiertos) - archivados} activos + {archivados} archivados)\n"
            "**Qué es:** vista derivada de los tickets abiertos por responsable real (tag del "
            "foro). No es ticket: **se recalcula con `regenerar_tablero.py`, no se edita a mano**.\n"
            "**Orden:** (1) bloquea otros tickets o ingresos · (2) incidente PROD · "
            "(3) deadline externo · (4) resto por esfuerzo.\n\n"
            f"**🟣 PLON (Jonathan) — {n_j} abiertos ({n_j - compartidos} propios + "
            f"{compartidos} compartidos)"
        )

    mensajes: list[dict] = []
    contador: dict[str, int] = {"plon": 0, "chucho": 0}
    en_ids: set[str] = set()
    # todo ticket ya curado en cualquier sección (para no repetirlo en "nuevos")
    curados = {e["ticket"] for sec in state["sections"] for b in sec["buckets"]
               for e in b["entries"]}
    curados |= {e["ticket"] for e in (state.get("sin_resp") or {}).get("entries", [])}

    for sec in state["sections"]:
        due = sec.get("owner")
        lineas = [encabezado()] if sec.get("con_encabezado") else [f"**{sec['title']}**"]
        for bucket in sec["buckets"]:
            lineas.append(bucket["label"])
            for e in bucket["entries"]:
                tid = e["ticket"]
                en_ids.add(tid)
                reg = por_id.get(tid)
                if reg is None or not reg["abierto"]:
                    continue
                if due in contador:
                    contador[due] += 1
                    pref, nuevo = f"{contador[due]}.", " 🆕" if e.get("fresh") else ""
                else:
                    pref, nuevo = "•", ""
                marca = MARCAS.get(reg["estado"] or "", "")
                detalle = f" — {e['text']}" if e.get("text") else ""
                lineas.append(f"{pref} **{e['title']}**{nuevo}{detalle}{marca} {link(tid)}")
            lineas.append("")
        mensajes.append({"id": sec["message_id"], "content": "\n".join(lineas).rstrip()})

    sr = state.get("sin_resp")
    if sr:
        lineas = ["**⚪ SIN RESPONSABLE**"]
        for e in sr["entries"]:
            reg = por_id.get(e["ticket"])
            en_ids.add(e["ticket"])
            if reg and reg["abierto"]:
                lineas.append(f"• **{e['title']}** — {e['text']} {link(e['ticket'])}")
        sueltos = [r for r in abiertos if not r["responsables"] and r["id"] not in en_ids]
        for r in sueltos:
            en_ids.add(r["id"])
            lineas.append(f"• **{r['name']}** — sin tag de responsable: asignar {link(r['id'])}")
        if sr.get("reconciliacion"):
            lineas += ["", sr["reconciliacion"]]
        mensajes.append({"id": sr["message_id"], "content": "\n".join(lineas).rstrip()})

    # tickets abiertos que ninguna sección tiene curados: aparecieron en el foro
    sin_curar = [r for r in abiertos if r["id"] not in curados]
    if sin_curar:
        lineas = ["**🆕 Nuevos en el foro — sin curar todavía**",
                  "Aparecieron desde la última regeneración: mover a su sección y quitar de aquí."]
        for r in sorted(sin_curar, key=lambda x: x["id"]):
            dueno = ("🟣 Plon" if "Jonathan" in r["responsables"]
                     else "🟢 Chucho" if "Chucho" in r["responsables"] else "⚪ Sin responsable")
            lineas.append(f"• {dueno} · **{r['name']}**{MARCAS.get(r['estado'] or '', '')} "
                          f"{link(r['id'])}")
        cuerpo_nuevos = "\n".join(lineas)
    else:
        cuerpo_nuevos = "🆕 **Nuevos en el foro:** ninguno — todo está curado en sus secciones."
    mensajes.append({"id": (state.get("nuevos") or {}).get("message_id"),
                     "content": cuerpo_nuevos, "slot": "nuevos"})

    prev = set(state.get("known_open", []))
    actuales = {r["id"] for r in abiertos}
    nuevos, fuera = sorted(actuales - prev), sorted(prev - actuales)
    nombre = lambda t: next((r["name"] for r in abiertos if r["id"] == t), t)  # noqa: E731
    delta = ["**🔄 Δ desde la última regeneración automática**",
             ("**Entraron:** " + " · ".join(nombre(t) for t in nuevos)) if nuevos
             else "**Entraron:** ninguno",
             ("**Salieron:** " + " · ".join(f"`{t}`" for t in fuera)) if fuera
             else "**Salieron:** ninguno",
             f"**Sigue abierto:** {len(actuales)} · lo reescribe el cron 06:00 o el "
             "listener de cambios de tag del foro."]
    mensajes.append({"id": state.get("delta_message_id"), "content": "\n".join(delta),
                     "slot": "delta"})

    for m in mensajes:
        if len(m["content"]) > 2000:
            raise RuntimeError(f"mensaje {m['id']} excede 2000: {len(m['content'])}")
    return mensajes, abiertos


# ---------------------------------------------------------------- publicar
def publicar(mensajes: list[dict], check: bool) -> dict:
    vivo = {m["id"]: (m.get("content") or "") for m in
            (api(f"/channels/{BOARD_ROOT}/messages", params={"limit": "50"}) or [])}
    cambios = [(m["id"], m["content"]) for m in mensajes
               if m.get("id") and vivo.get(m["id"]) != m["content"]]
    nuevos = [m for m in mensajes if not m.get("id")]
    res = {"changed": bool(cambios or nuevos),
           "patched": [], "posted": [],
           "chars": [len(c) for _, c in cambios]}
    if check:
        res["would_patch"] = [mid for mid, _ in cambios]
        return res
    for mid, content in cambios:
        api(f"/channels/{BOARD_ROOT}/messages/{mid}", "PATCH", {"content": content})
        res["patched"].append(mid)
        time.sleep(0.5)
    for m in nuevos:
        r = api(f"/channels/{BOARD_ROOT}/messages", "POST", {"content": m["content"]})
        if r and r.get("id"):
            res["posted"].append(r["id"])
        time.sleep(0.5)
    return res


# -------------------------------------------------------------------- seed
def seed() -> int:
    """board.json desde los mensajes vivos (parseo de líneas numeradas/bullets)."""
    msgs = sorted((api(f"/channels/{BOARD_ROOT}/messages", params={"limit": "50"}) or []),
                  key=lambda m: m["id"])
    state = {"message_ids": {"header": msgs[0]["id"]}, "sections": [],
             "known_open": [], "delta_message_id": None, "nuevos": {"message_id": None}}
    sec_actual: dict | None = None
    bucket_actual: dict | None = None
    modo_sr = False
    sin_resp_msg_id: str | None = None
    sr_lines: list[str] = []
    for idx, m in enumerate(msgs):
        contenido = m.get("content") or ""
        lineas = contenido.splitlines()
        first = lineas[0] if lineas else ""
        sec: dict | None = None
        restantes = lineas
        if "**⚪ SIN RESPONSABLE" in first:
            modo_sr, sr_lines = True, lineas
            sin_resp_msg_id = m["id"]
        elif first.startswith("**🔄 Δ"):
            state["delta_message_id"] = m["id"]
        elif first.startswith("**Estado:**"):
            sec = {"message_id": m["id"], "title": "Cabecera", "owner": "plon",
                   "con_encabezado": True, "absorbe_nuevos": True, "buckets": []}
            restantes = lineas[1:]
        elif first.startswith("**🟣 PLON"):
            sec = {"message_id": m["id"], "title": "🟣 PLON — continúa", "owner": "plon",
                   "absorbe_nuevos": False, "buckets": []}
            restantes = lineas[1:]
        elif first.startswith("**🟢 CHUCHO"):
            sec = {"message_id": m["id"], "title": "🟢 CHUCHO — continúa", "owner": "chucho",
                   "absorbe_nuevos": False, "buckets": []}
            restantes = lineas[1:]
        # cualquier otro mensaje del hilo (usuario, notas sueltas) se ignora entero
        if sec is None:
            continue
        state["sections"].append(sec)
        sec_actual, bucket_actual = sec, None
        for raw in restantes:
            linea = raw.rstrip()
            if not linea:
                continue
            me = RE_ENTRY.match(linea)
            if me:
                if bucket_actual is None:
                    bucket_actual = {"label": "📌 **Resto**", "entries": []}
                    sec_actual["buckets"].append(bucket_actual)
                bucket_actual["entries"].append({
                    "ticket": me.group(4), "title": me.group(2).strip(),
                    "text": (me.group(3) or "").strip()})
                continue
            if re.match(r"^[🔴🟠⚪🟢]", linea) or (linea.startswith("**") and linea.endswith("**")):
                if linea.startswith("**🟣") or linea.startswith("**🟢"):
                    continue
                bucket_actual = {"label": linea, "entries": []}
                sec_actual["buckets"].append(bucket_actual)
                continue
            if not linea.startswith(("-", "*")) and "**" in linea and not RE_ENTRY.match(linea):
                if bucket_actual is None:
                    bucket_actual = {"label": "📌 **Notas**", "entries": []}
                    sec_actual["buckets"].append(bucket_actual)

    if modo_sr:
        entries, idx_recon = [], None
        for i, linea in enumerate(sr_lines):
            mb = RE_BULLET.match(linea.strip())
            if mb:
                entries.append({"ticket": mb.group(3), "title": mb.group(1).strip(),
                                "text": (mb.group(2) or "").strip()})
            if "**✅ Tags corregidos" in linea or "**⚠️ Casos inversos" in linea:
                idx_recon = i
        state["sin_resp"] = {
            "message_id": sin_resp_msg_id,
            "entries": entries,
            "reconciliacion": "\n".join(sr_lines[idx_recon:]) if idx_recon else "",
        }

    _tags, snap = snapshot_foro()
    state["known_open"] = sorted(r["id"] for r in snap if r["abierto"])
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    entradas = sum(len(b["entries"]) for s in state["sections"] for b in s["buckets"])
    print(json.dumps({"seeded": str(STATE_PATH), "sections": len(state["sections"]),
                      "entradas_curadas": entradas, "sin_resp": len(state["sin_resp"]["entries"]),
                      "known_open": len(state["known_open"])}, ensure_ascii=False))
    return 0


# --------------------------------------------------------------------- CLI
def main(argv: list[str]) -> int:
    if "--seed" in argv:
        return seed()
    check = "--check" in argv
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    _tags, snap = snapshot_foro()
    mensajes, abiertos = render(state, snap)
    res = publicar(mensajes, check=check)
    if not check:
        # los mensajes nuevos (sin id) se crearon en orden: se les guarda su id para re-usarlos
        pendientes = [m for m in mensajes if not m.get("id")]
        restantes = list(res.get("posted", []))
        for m in pendientes:
            if not restantes:
                break
            mid = restantes.pop(0)
            if m.get("slot") == "nuevos":
                state.setdefault("nuevos", {})["message_id"] = mid
            elif m.get("slot") == "delta":
                state["delta_message_id"] = mid
        state["known_open"] = sorted(r["id"] for r in abiertos)
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1),
                              encoding="utf-8")
        RUN_LOG.write_text(json.dumps(
            {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "abiertos": len(abiertos), **res}, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
