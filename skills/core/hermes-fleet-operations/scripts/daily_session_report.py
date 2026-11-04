#!/usr/bin/env python3
"""
Recolector de actividad diaria para el cron de guardado en memoria (guardado-doble-memoria).

Uso:  python3 daily_session_report.py [YYYY-MM-DD]
Resuelve la DB relativa a este script (<scripts>/../state.db) salvo que se defina
HERMES_DB_PATH (para perfiles: <profile-home>/state.db).
Emite un reporte de texto plano con las sesiones de trabajo de la jornada,
que el agente del cron usa para el doble guardado (Engram + memoria nativa).

PROPÓSITO MULTI-PERFIL: copiar este archivo al scripts/ de CADA perfil → resuelve
automáticamente la state.db de ESE perfil (verificación: ejecutar y ver la línea
"DB resuelta"). No requiere toolset terminal del agente: lo ejecuta el scheduler del cron.

Salida ESTABLE: nada volátil por ejecución (sin timestamps propios).
"""
import os
import sqlite3
import sys
import datetime

DB = os.environ.get("HERMES_DB_PATH") or os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "state.db")
)
DAY = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()

MIN_MSGS = 4            # ignorar pings/toques triviales
MAX_BODY = 420          # recorte del primer mensaje de usuario
# 'cron' y 'tui' son automatizaciones/pruebas del propio sistema, no "trabajo"
EXCLUDE_SOURCES = ("cron", "tui")


def q(conn, sql, args=()):
    return conn.execute(sql, args).fetchall()


def first_user_msg(conn, sid):
    rows = q(conn, (
        "SELECT substr(trim(content), 1, ?) FROM messages "
        "WHERE session_id=? AND role='user' AND content IS NOT NULL "
        "ORDER BY id LIMIT 1"
    ), (MAX_BODY, sid))
    return (rows[0][0] or "") if rows else ""


def main():
    if not os.path.exists(DB):
        print(f"[ERROR] state.db no encontrado: {DB}")
        sys.exit(2)

    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = q(conn, """
        SELECT s.id,
               datetime(s.started_at,'unixepoch','localtime'),
               s.source,
               COALESCE(s.display_name,''),
               COALESCE(s.title,''),
               s.message_count, s.tool_call_count,
               COALESCE(s.last_activity_description,''),
               COALESCE(s.cwd,'')
        FROM sessions s
        WHERE date(s.started_at,'unixepoch','localtime') = ?
          AND s.source NOT IN (%s)
          AND s.message_count >= ?
        ORDER BY s.started_at ASC
    """ % ",".join("?" * len(EXCLUDE_SOURCES)),
        (DAY, *EXCLUDE_SOURCES, MIN_MSGS))

    print(f"# Jornada de trabajo — {DAY}")
    print("(reporte generado por daily_session_report.py)\n")

    if not rows:
        print("Sin sesiones de trabajo en esta jornada (solo se han considerado "
              "sesiones de conversación real).")
        conn.close()
        return

    for sid, inicio, source, disp, title, n_msg, n_tools, last_act, cwd in rows:
        who = disp or source
        first = first_user_msg(conn, sid).replace("\n", " ")
        hora = inicio[11:16]
        print(f"## [{source}] {who} — inicio {hora}")
        print(f"  título: {title or '(sin título)'}")
        print(f"  msgs: {n_msg} · tool calls: {n_tools}")
        if last_act:
            print(f"  última actividad: {last_act[:240]}")
        if first:
            print(f"  pidió: {first}")
        if cwd:
            print(f"  cwd: {cwd}")
        print()

    conn.close()


if __name__ == "__main__":
    main()