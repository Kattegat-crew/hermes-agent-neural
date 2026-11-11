#!/usr/bin/env python3
"""F1.5 — Ciclo de vida de sesión: cierra sesiones de chat envejecidas para que el asistente
arranque una conversación limpia (hallazgo H1: la causa raíz de los turnos de 7 minutos).

Por qué existe: en esta versión de Hermes el "reset diario" del config
(`session_reset` / `default_reset_policy`) es un tipo LEGACY INERTE —
`gateway/config.py::SessionResetPolicy` dice literalmente "Gateway configuration and session lifecycle
do not consume this datatype". Sin este job, un chat puede atender con semanas de contexto
(medido en F0: sesión de 17,6 días y 226.210 tokens de entrada en Goldie; 22 días y 9,7 M en Jacqueline).

Cómo funciona (verificado contra el código del core):
  1. Marca la fila como cerrada con `SessionDB.promote_to_session_reset()` — el método oficial:
     `UPDATE sessions SET ended_at=?, end_reason='idle' WHERE id=? AND (ended_at IS NULL OR
     end_reason IN ('agent_close','ws_orphan_reap','superseded_by_resume','startup_orphan_reap'))`
     y avanza la generación de conversación en la misma transacción (`_end_and_bump`).
  2. En el siguiente mensaje, el gateway detecta la ruta obsoleta ("is ended in state.db but still live
     in sessions.json"), suelta la entrada y crea una sesión NUEVA — `_route_recover` no la resucita
     porque `idle` es un motivo de reset (no recuperable).

GARANTÍA DE MEMORIA (orden pedido por el Admin): antes de cerrar la sesión de un perfil se comprueba
que su job `guardar-diario-memoria` haya corrido dentro de la ventana aceptada. Si no, **ese perfil se
omite** (fail-closed): es preferible un chat largo un día más que perder la memoria de la jornada.

Uso:
    python3 session_reset.py --clientes                  # dry-run (por defecto NO escribe)
    python3 session_reset.py --clientes --apply          # cierra las envejecidas (con guarda de memoria)
    python3 session_reset.py --clientes --apply --quiet   # modo cron (silencio si todo va bien)
"""
import argparse
import datetime
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, "/opt/hermes")

DATA_BASE = Path("/opt/data")

CLIENTES = ["golden-game", "lucky-club", "helmer", "jacqueline", "nancy", "yulieth", "ivan", "alejandro"]


def db_de(perfil: str, base: Path | None = None) -> Path:
    """Ruta del state.db de un perfil. El perfil `default` (Admin) NO vive en profiles/:
    su base es la raíz de datos."""
    base = Path(base or DATA_BASE)
    if perfil == "default":
        return base / "state.db"
    return base / "profiles" / perfil / "state.db"


def clientes_flota(base: Path | None = None) -> list[str]:
    """Perfiles con state.db, descubiertos del disco (27-oct-2026).

    Antes la lista era fija y se quedaron fuera gerardo, isa, oscar y alejo: sus sesiones nunca
    se cerraban (la de Gerardo llegó a 3,5 M de tokens de entrada y a respuestas a pedazos).

    `default` se incluye (11-nov-2026): su state.db está en la raíz de datos y quedaba fuera por el
    filtro de `profiles/`, así que en la práctica tenía sesiones abiertas de 41 días y una con
    3,85 M de tokens de entrada que se re-leían en cada turno. Solo se excluye `neural-admin-test`
    (perfil de pruebas, no atiende a nadie).
    """
    base = Path(base or DATA_BASE)
    excluir = {"neural-admin-test", "default"}
    try:
        nombres = [p.parent.name for p in (base / "profiles").glob("*/state.db") if p.parent.name not in excluir]
    except OSError:
        nombres = []
    if (base / "state.db").exists():
        nombres.append("default")
    nombres.sort()
    if not nombres and base == DATA_BASE:
        return list(CLIENTES)
    return nombres


MAX_AGE_HOURS = 24
# Umbral de tokens: por encima de esto la sesión se cierra SIN exigir inactividad (11-nov-2026,
# orden del Admin). Una sesión de 300 k arrastra el inventario de herramientas y las skills del día
# en que nació: en Goldie/Lucky el widget web quedaba ACTIVO siempre, así que con el criterio de
# inactividad de 60 min nunca entraba al reset y llevaba 28,8 días y 5,68 M de tokens de entrada.
MAX_TOKENS = 300_000


def candidatas(db_path: Path, max_age_h: float, max_idle_min: float = 60.0,
               max_tokens: float = MAX_TOKENS):
    """Sesiones de CHAT (con session_key) que superan alguno de los dos caminos:

      A) tokens de entrada >= max_tokens   → cierra YA, sin mirar inactividad.
      B) edad > max_age_h  Y  inactividad > max_idle_min  → cierra por vejez.

    Por qué dos caminos: la causa raíz de H1 (Goldie, 17,6 días / 226.210 tokens) estaba ACTIVA el
    mismo día, así que un criterio de sola inactividad no la habría reseteado; y cortar por edad a
    secas partiría una conversación en curso. El camino A cubre el caso contrario: sesiones que
    nunca quedan quietas (api_server del widget) pero que ya son enormes.
    """
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    hace = time.time() - max_idle_min * 60
    filas = con.execute(
        """SELECT id, session_key, started_at, last_activity_at, message_count,
                  input_tokens, output_tokens
           FROM sessions
           WHERE ended_at IS NULL AND session_key IS NOT NULL AND session_key <> ''
             AND (
                   COALESCE(input_tokens, 0) >= ?
                   OR (COALESCE(last_activity_at, started_at) < ?
                       AND COALESCE(started_at, 0) < ?)
                 )
           ORDER BY COALESCE(last_activity_at, started_at)""",
        (max_tokens, hace, time.time() - max_age_h * 3600)).fetchall()
    con.close()
    out = []
    for f in filas:
        ts = f["last_activity_at"] or f["started_at"] or 0
        por_tokens = (f["input_tokens"] or 0) >= max_tokens
        out.append({
            "id": f["id"], "key": f["session_key"],
            "edad_dias": round((time.time() - (f["started_at"] or 0)) / 86400, 1),
            "inactiva_h": round((time.time() - ts) / 3600, 1),
            "mensajes": f["message_count"],
            "tokens_in": f["input_tokens"] or 0,
            "motivo": "tokens" if por_tokens else "edad",
        })
    return out


def memoria_reciente(perfil: str, horas: float = 20.0, base: Path | None = None):
    """¿Se guardó la memoria de este perfil en las últimas `horas`?

    Señal: el artefacto de salida del job `guardar-diario-memoria` en
    `profiles/<perfil>/cron/output/<job_id>/` (un .md por corrida). Para `default` el job y sus
    salidas viven en la RAÍZ de datos (`/opt/data/cron/...`), no bajo `profiles/`.
    Devuelve (ok, detalle).
    """
    base = Path(base or DATA_BASE)
    pdir = base if perfil == "default" else base / "profiles" / perfil
    jobs = pdir / "cron" / "jobs.json"
    if not jobs.exists():
        return False, "sin cron/jobs.json (no existe el job de memoria)"
    try:
        data = json.loads(jobs.read_text())
        lista = data if isinstance(data, list) else data.get("jobs", [])
        job = next((x for x in lista if x.get("name") == "guardar-diario-memoria"), None)
    except Exception as e:
        return False, f"jobs.json ilegible: {e}"
    if not job:
        return False, "sin job 'guardar-diario-memoria'"
    odir = pdir / "cron" / "output" / str(job.get("id"))
    if not odir.is_dir():
        return False, f"sin salidas del job en {odir}"
    limite = time.time() - horas * 3600
    archivos = [f for f in odir.iterdir() if f.is_file()]
    recientes = [f for f in archivos if f.stat().st_mtime >= limite]
    if not recientes:
        ultimo = max((f.stat().st_mtime for f in archivos), default=0)
        cuando = datetime.datetime.fromtimestamp(ultimo).strftime("%Y-%m-%d %H:%M") if ultimo else "nunca"
        return False, f"última corrida del job de memoria: {cuando} (> {horas:.0f} h)"
    ult = max(recientes, key=lambda f: f.stat().st_mtime)
    # Un artefacto de corrida BLOQUEADA por el preflight de cron (p. ej. failure_deliver apuntando a
    # una plataforma que el perfil no tiene: discord) NO acredita memoria guardada: el core escribe
    # ~600 B con '**Status:** BLOCKED (configuration)' y el agente NUNCA corrió. Sin esta comprobación
    # la guarda se satisface con un bloqueo y se cierran sesiones cuya jornada no quedó en memoria.
    if not _artefacto_acredita(ult):
        return False, f"última corrida BLOQUEADA/no válida ({ult.name}) — no acredita guardado"
    if str(job.get("last_status") or "") == "blocked_config":
        return False, "job bloqueado por config (last_status=blocked_config) — no acredita guardado"
    return True, "memoria guardada " + datetime.datetime.fromtimestamp(ult.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def _artefacto_acredita(archivo: Path) -> bool:
    """¿El artefacto de salida es de una corrida REAL (el agente corrió) y no de un bloqueo?

    Criterio: la cabecera del core lleva '**Status:** BLOCKED (configuration)' cuando el preflight
    aborta sin llamar al modelo; un artefacto legítimo (aunque cierre en [SILENT]) pesa varios KB.
    """
    try:
        if archivo.stat().st_size < 800:
            return False
        cabeza = archivo.read_text(errors="ignore")[:800]
    except Exception:
        return False
    for linea in cabeza.splitlines():
        if linea.strip().startswith("**Status:**") and "BLOCKED" in linea.upper():
            return False
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", action="append")
    ap.add_argument("--clientes", action="store_true", help="todos los perfiles con state.db de la flota")
    ap.add_argument("--max-age-hours", type=float, default=MAX_AGE_HOURS)
    ap.add_argument("--max-idle-minutes", type=float, default=60.0)
    ap.add_argument("--max-tokens", type=float, default=MAX_TOKENS,
                    help="tokens de entrada a partir de los cuales la sesión se cierra SIN exigir "
                         "inactividad (una sesión gorda congela herramientas y skills viejas)")
    ap.add_argument("--apply", action="store_true", help="escribe (por defecto solo informa)")
    ap.add_argument("--memory-max-hours", type=float, default=20.0,
                    help="antigüedad máxima aceptada del guardado de memoria")
    ap.add_argument("--force", action="store_true",
                    help="IGNORA la comprobación de memoria (peligroso: se puede perder la jornada)")
    ap.add_argument("--quiet", action="store_true",
                    help="modo cron: sin salida si todo va bien (el scheduler no entrega nada)")
    ap.add_argument("--data-base", default=str(DATA_BASE), help="raíz de datos (pruebas)")
    a = ap.parse_args(argv)
    base = Path(a.data_base)

    perfiles = clientes_flota(base) if a.clientes else []
    if a.profile:
        perfiles += a.profile
    if not perfiles:
        sys.exit("indica --profile <perfil> o --clientes")

    out = []
    problemas = []
    total = 0
    out.append(f"F1.5 · (tokens >= {int(a.max_tokens)}, sin exigir inactividad) o "
               f"(edad > {a.max_age_hours} h e inactividad > {a.max_idle_minutes:.0f} min) · "
               f"modo: {'ESCRITURA' if a.apply else 'DRY-RUN'}")
    for p in perfiles:
        db = db_de(p, base)
        if not db.exists():
            out.append(f"  [{p}] sin state.db — se omite")
            continue
        cands = []
        try:
            cands = candidatas(db, a.max_age_hours, a.max_idle_minutes, a.max_tokens)
        except Exception as e:
            # Un state.db corrupto o sin tabla `sessions` no puede tumbar el run completo:
            # el resto de la flota debe seguir cerrándose y el problema se reporta.
            problemas.append(f"{p}: no se pudo leer {db} ({e})")
            out.append(f"  [{p}] ⚠ sin lectura de sesiones ({e}) — se omite")
            continue
        out.append(f"  [{p}] {len(cands)} sesión(es) de chat envejecidas")
        for c in cands:
            out.append(f"      - {c['id']} | {c['key']} | edad {c['edad_dias']} d | "
                       f"inactiva {c['inactiva_h']} h | {c['mensajes']} msgs | {c['tokens_in']} tok | {c.get('motivo','edad')}")
        if not cands:
            continue
        if a.apply and not a.force:
            ok, det = memoria_reciente(p, a.memory_max_hours, base)
            if not ok:
                out.append(f"      ⚠ SE OMITE {p}: memoria NO verificada ({det})")
                problemas.append(f"{p}: {det}")
                continue
            out.append(f"      memoria OK — {det}")
        total += len(cands)
        if a.apply:
            from hermes_state import SessionDB
            sdb = SessionDB(db_path=db)
            for c in cands:
                try:
                    ok = sdb.promote_to_session_reset(c["id"], reason="idle")
                except Exception as e:
                    ok = False
                    problemas.append(f"{p} {c['id']}: error al cerrar ({e})")
                out.append(f"      {'RESET OK' if ok else 'SIN CAMBIO'}  {c['id']}")
            try:
                sdb.close()
            except Exception:
                pass
    out.append(f"Total sesiones {'cerradas' if a.apply else 'candidatas'}: {total}")
    out.append("ts: " + datetime.datetime.now().isoformat(timespec="seconds"))

    # Modo cron: silencio total si no hay nada que reportar ni problemas.
    if a.quiet and not problemas:
        return
    print("\n".join(out))
    if problemas:
        print("\n⚠ PROBLEMAS (" + str(len(problemas)) + "):")
        for x in problemas:
            print("  -", x)


if __name__ == "__main__":
    main()
