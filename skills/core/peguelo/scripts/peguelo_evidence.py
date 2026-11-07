#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""peguelo_evidence.py — dossier forense de una sesion Hermes, en SOLO LECTURA.

Uso:
  python3 peguelo_evidence.py                 # sesion actual ($HERMES_SESSION_ID) o la ultima activa
  python3 peguelo_evidence.py --session ID    # sesion concreta
  python3 peguelo_evidence.py --last 3        # las N ultimas sesiones + agregado
  python3 peguelo_evidence.py --lineage       # incluye cadena parent_session_id (sesiones partidas)
  python3 peguelo_evidence.py --json          # imprime el JSON completo
  python3 peguelo_evidence.py --selftest      # prueba determinista contra una DB sintetica

Salida: digest legible en stdout + JSON completo en --out
(default /opt/data/cache/peguelo/<id>.json). No escribe nada en state.db.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timezone

SCHEMA_VERSION = 1
DB_CANDIDATES = [
    os.environ.get("HERMES_STATE_DB") or "",
    "/opt/data/state.db",
    "/opt/hermes-agent-data/state.db",
    os.path.expanduser("~/.hermes/state.db"),
]
OUT_DIR = os.environ.get("PEGUELO_OUT_DIR") or "/opt/data/cache/peguelo"

WRITE_TOOLS = {"write_file", "patch", "edit_file", "create_file", "str_replace_editor", "apply_patch"}
# Editar exige que el archivo YA exista: si hay patch sin lectura previa, la violacion es inequivoca.
EDIT_TOOLS = {"patch", "edit_file", "str_replace_editor", "apply_patch"}
READ_TOOLS = {"read_file", "view_file", "search_files", "grep", "list_dir"}
REPEATABLE_TOOLS = {"kanban_heartbeat", "process_manage", "job_output", "wait", "sleep"}
PATH_KEYS = ("path", "file_path", "target", "target_file", "filename", "file")
CMD_KEYS = ("command", "cmd", "script", "code")

VERIFY_RE = re.compile(
    r"(pytest|npm (run )?test|pnpm test|yarn test|go test|cargo test|ruff|flake8|eslint|tsc\b|mypy|"
    r"make test|shellcheck|python3? -m (pytest|unittest)|curl\s|git diff|git status|git log|"
    r"psql|sqlite3|sha256sum|md5sum|--version|--help)", re.I)
DESTRUCTIVE_RE = re.compile(
    r"(rm\s+-rf|git reset --hard|git clean -fd|git push[^\n]*--force|drop\s+(table|database)|"
    r"truncate\s+table|delete\s+from|docker\s+(rm|rmi)|systemctl\s+(stop|restart|disable)|"
    r"killall|pkill|\bmkfs\b|dd\s+if=)", re.I)
CLAIM_RE = re.compile(
    r"\b(listo|hecho|completado|verificado|terminado|funciona|funcionando|desplegado|publicado|"
    r"enviado|done|completed|verified|deployed|fixed|arreglado|quedo listo|ya esta)\b", re.I)
PROMISE_RE = re.compile(
    r"\b(voy a|procedo a|ahora (ejecuto|hago|aplico|reviso)|ejecuto|aplico|a continuacion|"
    r"i'?ll|let me|next,? i)\b", re.I)
CORRECTION_RE = re.compile(
    r"(\bno,\s|\bno es lo que\b|\bno era eso\b|\best[aá] mal\b|\bas[ií] no\b|\botra vez\b|"
    r"\bde nuevo\b|\bcorrige\b|\bcorr[ií]gelo\b|\bequivoc|\bte equivocaste\b|\bno me entendiste\b|"
    r"\bno ped[ií] eso\b|\bno funciona\b|\bsigue fallando\b|\bno sirve\b|\bte falta\b|"
    r"\brevisa(lo)? (otra vez|de nuevo|bien)\b|\bya te lo dije\b)", re.I)
CORRECTION_STRONG_RE = re.compile(
    r"(\bno,\s|\best[aá] mal\b|\bas[ií] no\b|\bno es lo que\b|\bno era eso\b|\bcorrige\b|"
    r"equivoc|no me entendiste)", re.I)
# Pregunta o pedido de estado. Si no trae rechazo explicito NO es correccion,
# aunque contenga "falta", "error" o "revisa" (falso positivo medido en sesion real).
QUESTION_RE = re.compile(
    r"^\s*(dame|dime|mu[eé]strame|resumen|estado|qu[eé]|c[oó]mo|cu[aá]l|cu[aá]ndo|d[oó]nde|"
    r"cu[aá]nto|hay|tienes|puedes|sigue|contin[uú]a)\b", re.I)
FAIL_RX = [
    ("hook", re.compile(r"failed closed", re.I)),
    ("traceback", re.compile(r"Traceback \(most recent call last\)")),
    ("text_error", re.compile(r"(?m)^(?:Error|ERROR|Exception|FATAL|command not found|bash: .*not found)\b")),
]
SECRET_RX = re.compile(
    r"(sk-[A-Za-z0-9_\-]{12,}|xox[baprs]-[A-Za-z0-9\-]{10,}|ghp_[A-Za-z0-9]{20,}|"
    r"AIza[0-9A-Za-z_\-]{20,}|(?i:bearer)\s+[A-Za-z0-9._\-]{16,})")


# ───────────────────────── utilidades ─────────────────────────
def redact(txt, limit=None):
    if not isinstance(txt, str):
        try:
            txt = json.dumps(txt, ensure_ascii=False)
        except Exception:
            txt = str(txt)
    txt = SECRET_RX.sub("***REDACTED***", txt)
    if limit and len(txt) > limit:
        return txt[:limit] + "…"
    return txt


def iso(ts):
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).astimezone().isoformat(timespec="seconds")
    except Exception:
        return None


def canon(args):
    try:
        return json.dumps(args, sort_keys=True, ensure_ascii=False)
    except Exception:
        return str(args)


def short_hash(text):
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:12]


def pick(args, keys):
    for k in keys:
        if isinstance(args, dict) and args.get(k):
            return args[k]
    return None


def summarize_args(name, args):
    if not isinstance(args, dict):
        return redact(str(args), 120)
    bits = []
    for k in ("path", "file_path", "command", "query", "url", "session_id", "task_id", "name",
              "skill", "action", "pattern", "title"):
        if args.get(k):
            bits.append("%s=%s" % (k, redact(str(args[k]), 90)))
    if not bits:
        for k, v in list(args.items())[:3]:
            if isinstance(v, (str, int, float, bool)):
                bits.append("%s=%s" % (k, redact(str(v), 60)))
    return " ".join(bits)[:180] or "{}"


# ───────────────────────── DB ─────────────────────────
def find_db(explicit=None):
    if explicit:
        if not os.path.isfile(explicit):
            raise SystemExit("peguelo: no existe la DB %s" % explicit)
        return explicit
    for c in DB_CANDIDATES:
        if c and os.path.isfile(c):
            return c
    raise SystemExit("peguelo: no encuentro state.db (probado: %s)" % ", ".join(x for x in DB_CANDIDATES if x))


def connect(db):
    con = sqlite3.connect("file:%s?mode=ro" % db, uri=True, timeout=20)
    con.row_factory = sqlite3.Row
    return con


def get_session(con, sid):
    row = con.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
    return dict(row) if row else None


def latest_sessions(con, n, skip_empty=True):
    sql = "SELECT s.id FROM sessions s"
    if skip_empty:
        # Una sesion sin mensajes es un arranque de cron sin actividad, no una sesion analizable:
        # se excluye del barrido y del agregado (si no, diluye las tasas y gasta cuota de N).
        sql += (" WHERE COALESCE(s.message_count, 0) > 0 OR EXISTS("
                "SELECT 1 FROM messages m WHERE m.session_id = s.id AND COALESCE(m.active, 1) = 1)")
    sql += " ORDER BY COALESCE(s.last_activity_at, s.started_at) DESC LIMIT ?"
    rows = con.execute(sql, (n,)).fetchall()
    return [r["id"] for r in rows]


def skipped_empty_count(con, n, kept):
    """Cuantas de las N sesiones mas recientes se omitieron por no tener actividad."""
    top_all = latest_sessions(con, n, skip_empty=False)
    return max(0, len(top_all) - len(set(top_all) & set(kept)))


def lineage(con, sid, depth=5):
    chain, cur, seen = [sid], sid, {sid}
    for _ in range(depth):
        row = get_session(con, cur)
        if not row:
            break
        parent = row.get("parent_session_id")
        if not parent or parent in seen:
            break
        chain.append(parent)
        seen.add(parent)
        cur = parent
    return list(reversed(chain))


def get_messages(con, sids, cap):
    placeholders = ",".join("?" for _ in sids)
    base = ("SELECT id, session_id, role, content, tool_name, tool_call_id, tool_calls, timestamp "
            "FROM messages WHERE session_id IN (%s)")
    # active=1 es la transcripcion canonica: sessions.message_count coincide con esas filas.
    # active=0 son generaciones historicas (pre-compaccion / rewind) y duplican el mismo turno.
    rows = con.execute(base % placeholders + " AND COALESCE(active, 1) = 1 ORDER BY timestamp, id",
                       tuple(sids)).fetchall()
    if not rows:
        rows = con.execute(base % placeholders + " ORDER BY timestamp, id", tuple(sids)).fetchall()
    total = len(rows)
    truncated = False
    if total > cap:
        rows = rows[:100] + rows[-(cap - 100):]
        truncated = True
    return [dict(r) for r in rows], total, truncated


# ───────────────────────── parsing ─────────────────────────
def parse_tool_calls(raw):
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if isinstance(data, dict):
        data = data.get("tool_calls") or [data]
    out = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        fn = item.get("function") if isinstance(item.get("function"), dict) else item
        name = fn.get("name") or item.get("name") or "?"
        raw_args = fn.get("arguments", item.get("arguments", ""))
        if isinstance(raw_args, str) and raw_args.strip():
            try:
                args = json.loads(raw_args)
            except Exception:
                args = {"_raw": raw_args[:300]}
        elif isinstance(raw_args, dict):
            args = raw_args
        else:
            args = {}
        out.append({
            "call_id": item.get("call_id") or item.get("id") or "",
            "name": name,
            "args": args,
        })
    return out


def classify_result(content):
    txt = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    obj = None
    s = txt.strip()
    if s.startswith("{"):
        try:
            obj = json.loads(s)
        except Exception:
            obj = None
    if isinstance(obj, dict):
        err = obj.get("error")
        if err:
            return "fail", "json_error", redact(str(err), 240)
        if "exit_code" in obj and obj.get("exit_code") not in (0, None, "0"):
            return "fail", "exit_code", redact("exit_code=%s" % obj.get("exit_code"), 240)
        if obj.get("success") is False:
            return "fail", "success_false", redact(s, 240)
        if str(obj.get("status", "")).lower() in ("error", "failed", "failure"):
            return "fail", "status_error", redact(s, 240)
    if "<untrusted-tool-result" in txt and re.search(r'"success"\s*:\s*false', txt):
        return "fail", "tool_success_false", redact(txt, 240)
    head = txt[:800]  # solo la cabecera: evita marcar como fallo un volcado largo que mencione "error"
    for kind, rx in FAIL_RX:
        if rx.search(head):
            return "fail", kind, redact(head, 240)
    return "ok", "", redact(txt, 160)


# ───────────────────────── analisis ─────────────────────────
def analyze_session(con, sid, cap=4000):
    srow = get_session(con, sid)
    if not srow:
        raise SystemExit("peguelo: la sesion %s no existe en %s" % (sid, con.execute("PRAGMA database_list").fetchone()["file"]))
    msgs, total_msgs, truncated = get_messages(con, [sid], cap)

    calls = []          # por invocacion
    results = {}        # call_id -> {status, kind, excerpt, idx, tool}
    seq = []            # timeline compacta
    message_index = {}
    for pos, m in enumerate(msgs):
        message_index[m["id"]] = pos
        role = m.get("role")
        if role == "assistant":
            for c in parse_tool_calls(m.get("tool_calls")):
                calls.append({
                    "idx": pos, "msg_id": m["id"], "ts": m.get("timestamp"),
                    "call_id": c["call_id"], "name": c["name"], "args": c["args"],
                    "arg_hash": short_hash(c["name"] + "|" + canon(c["args"])),
                    "summary": summarize_args(c["name"], c["args"]),
                })
            seq.append({"i": pos, "role": "assistant", "text": redact(m.get("content") or "", 200) or None,
                        "calls": [c["name"] for c in parse_tool_calls(m.get("tool_calls"))]})
        elif role == "tool":
            status, kind, excerpt = classify_result(m.get("content") or "")
            results[m.get("tool_call_id") or "#%s" % m["id"]] = {
                "status": status, "kind": kind, "excerpt": excerpt, "idx": pos,
                "tool": m.get("tool_name"), "chars": len(m.get("content") or ""),
            }
            seq.append({"i": pos, "role": "tool", "tool": m.get("tool_name"), "status": status,
                        "kind": kind, "chars": len(m.get("content") or "")})
        else:
            seq.append({"i": pos, "role": role, "text": redact(m.get("content") or "", 400)})

    for c in calls:
        r = results.get(c["call_id"])
        c["status"] = r["status"] if r else "no_result"
        c["error_kind"] = r["kind"] if r else "no_result"
        c["result_chars"] = r["chars"] if r else 0
        c["error_excerpt"] = r["excerpt"] if r and r["status"] == "fail" else ""

    # ── metricas por herramienta
    tools = {}
    for c in calls:
        t = tools.setdefault(c["name"], {"calls": 0, "failures": 0, "result_chars": 0})
        t["calls"] += 1
        t["result_chars"] += c["result_chars"]
        if c["status"] == "fail":
            t["failures"] += 1

    failures = [{"idx": c["idx"], "tool": c["name"], "kind": c["error_kind"],
                 "excerpt": c["error_excerpt"], "args": c["summary"]}
                for c in calls if c["status"] == "fail"]

    # ── repeticiones y bucles
    by_hash = {}
    for c in calls:
        by_hash.setdefault((c["name"], c["arg_hash"]), []).append(c)
    duplicates, loops = [], []
    for (name, _h), group in by_hash.items():
        if len(group) < 2:
            continue
        if name in REPEATABLE_TOOLS:
            continue
        entry = {"tool": name, "count": len(group), "first_idx": group[0]["idx"],
                 "last_idx": group[-1]["idx"], "args": group[0]["summary"]}
        passed_repeat = sum(1 for g in group if g["status"] != "fail")
        if len(group) >= 2 and passed_repeat == 0:
            entry["kind"] = "repeat_failure"
            loops.append(entry)
        elif len(group) >= 3:
            entry["kind"] = "repeat_identical"
            duplicates.append(entry)
        else:
            duplicates.append(entry)

    failure_clusters = {}
    for f in failures:
        key = (f["tool"], f["kind"])
        failure_clusters.setdefault(key, []).append(f)
    clusters = [{"tool": k[0], "kind": k[1], "count": len(v)} for k, v in failure_clusters.items() if len(v) >= 3]

    # ── higiene de escritura (read-before-write)
    writes = []
    read_paths = set()
    preflight_seen = False
    for c in calls:
        path = pick(c["args"], PATH_KEYS)
        if c["name"] in READ_TOOLS and path:
            read_paths.add(str(path))
        if c["name"] == "terminal":
            cmd = str(pick(c["args"], CMD_KEYS) or "")
            if re.search(r"git (status|pull|fetch|log)|^ls\b|\bls ", cmd):
                preflight_seen = True
            for p in re.findall(r"(/[\w./\-]{6,})", cmd):
                read_paths.add(p)
        if c["name"] in WRITE_TOOLS:
            p = str(path) if path else None
            prior = bool(p and p in read_paths)
            if c["name"] in EDIT_TOOLS:
                # patch/edit exigen archivo existente: sin lectura previa es violacion inequivoca.
                created, ambiguous = False, False
            else:
                # write_file crea o sobrescribe. Si el archivo no existe HOY es creacion.
                # Si existe, no puedo distinguir si nacio en esta sesion: se marca ambigua y no se acusa.
                # (exists() se evalua al analizar, no en el instante de la llamada.)
                created = bool(p) and not os.path.exists(p)
                ambiguous = bool(p) and not created and not prior
            writes.append({"idx": c["idx"], "tool": c["name"], "path": p,
                           "prior_read": prior, "created": created, "ambiguous": ambiguous})
    writes_without_read = [w for w in writes
                           if w["path"] and not w["prior_read"] and not w["created"] and not w["ambiguous"]]
    ambiguous_writes = [w for w in writes if w["path"] and w["ambiguous"]]
    creates = [w for w in writes if w["path"] and w["created"]]

    verify_calls = []
    last_write_idx = max([w["idx"] for w in writes], default=None)
    if last_write_idx is not None:
        for c in calls:
            if c["idx"] <= last_write_idx:
                continue
            blob = c["name"] + " " + summarize_args(c["name"], c["args"])
            if VERIFY_RE.search(blob) or (c["name"] in READ_TOOLS and pick(c["args"], PATH_KEYS) in [w["path"] for w in writes]):
                verify_calls.append({"idx": c["idx"], "tool": c["name"], "args": c["summary"]})

    destructive = [{"idx": c["idx"], "cmd": redact(str(pick(c["args"], CMD_KEYS) or ""), 200)}
                   for c in calls
                   if c["name"] == "terminal" and DESTRUCTIVE_RE.search(str(pick(c["args"], CMD_KEYS) or ""))]

    # ── usuario: turnos y correcciones
    user_msgs = [m for m in msgs if m.get("role") == "user"]
    corrections = []
    for m in user_msgs[1:]:
        txt = redact(m.get("content") or "", 400)
        if len(txt) > 4000:
            continue
        if not CORRECTION_RE.search(txt):
            continue
        if QUESTION_RE.match(txt) and not CORRECTION_STRONG_RE.search(txt):
            continue
        corrections.append({"idx": message_index.get(m["id"]), "text": txt})
    corrections = corrections[:8]
    # Todas las intervenciones del humano, sin filtro: permite auditar el recall del regex a mano.
    turns_text = [{"idx": message_index.get(m["id"]), "text": redact(m.get("content") or "", 240)}
                  for m in user_msgs][-30:]

    # ── afirmaciones sin evidencia y promesas sin accion
    claims_without_evidence, promises_without_action = [], []
    for pos, m in enumerate(msgs):
        if m.get("role") != "assistant":
            continue
        txt = redact(m.get("content") or "", 400)
        has_calls = bool(parse_tool_calls(m.get("tool_calls")))
        if not txt or has_calls:
            continue
        if CLAIM_RE.search(txt):
            window = msgs[max(0, pos - 4):pos]
            evidenced = any(w.get("role") == "tool" and results.get(w.get("tool_call_id") or "", {}).get("status") == "ok"
                            for w in window)
            if not evidenced:
                claims_without_evidence.append({"idx": pos, "text": txt})
        if PROMISE_RE.search(txt):
            nxt = msgs[pos + 1] if pos + 1 < len(msgs) else None
            if nxt is None or nxt.get("role") == "user":
                promises_without_action.append({"idx": pos, "text": txt})

    # ── ensamblado
    started = srow.get("started_at")
    last = srow.get("last_activity_at") or started
    report = {
        "schema": SCHEMA_VERSION,
        "generated_at": iso(time.time()),
        "db": con.execute("PRAGMA database_list").fetchone()["file"],
        "session": {
            "id": sid,
            "title": srow.get("title"),
            "source": srow.get("source"),
            "profile": srow.get("profile_name"),
            "model": srow.get("model"),
            "started_at": iso(started),
            "last_activity_at": iso(last),
            "duration_min": round((float(last) - float(started)) / 60.0, 1) if started and last else None,
            "message_count": srow.get("message_count"),
            "tool_call_count": srow.get("tool_call_count"),
            "api_call_count": srow.get("api_call_count"),
            "input_tokens": srow.get("input_tokens"),
            "output_tokens": srow.get("output_tokens"),
            "cache_read_tokens": srow.get("cache_read_tokens"),
            "estimated_cost_usd": srow.get("estimated_cost_usd"),
            "parent_session_id": srow.get("parent_session_id"),
            "cwd": srow.get("cwd"),
            "git_branch": srow.get("git_branch"),
        },
        "lineage": [sid],
        "messages": {"read": len(msgs), "total": total_msgs, "truncated": truncated},
        "totals": {
            "tool_calls": len(calls),
            "tool_results": len(results),
            "no_result": sum(1 for c in calls if c["status"] == "no_result"),
            "failures": len(failures),
            "failure_rate": round(len(failures) / len(calls), 3) if calls else 0.0,
            "distinct_tools": len(tools),
            "repeated_calls": sum(max(0, v["count"] - 1) for v in duplicates) + sum(max(0, v["count"] - 1) for v in loops),
        },
        "tools": tools,
        "tool_sequence": [c["name"] for c in calls][:300],
        "failures": failures[:25],
        "loops": loops[:10],
        "duplicates": duplicates[:10],
        "failure_clusters": clusters,
        "hygiene": {
            "preflight_command_seen": preflight_seen,
            "writes": writes,
            "creates": creates[:50],
            "ambiguous_writes": ambiguous_writes[:50],
            "writes_without_prior_read": writes_without_read,
            "verification_after_write": bool(verify_calls),
            "verification_calls": verify_calls[:10],
            "destructive_commands": destructive,
        },
        "user": {"turns": len(user_msgs), "corrections": corrections, "turns_text": turns_text},
        "flags": {
            "claims_without_evidence": claims_without_evidence[:6],
            "promises_without_action": promises_without_action[:6],
        },
        "timeline": seq if truncated else [],
        "notes": [
            "status de tool = heuristica (JSON error/exit_code, 'failed closed', Traceback, lineas Error:)",
            "writes_without_prior_read = heuristica por ruta/ comandos git|ls",
            "coste puede venir 0.0 si el perfil no tiene pricing; usar tokens como proxy",
        ],
    }
    return report


# ───────────────────────── patrones cross-sesion ─────────────────────────
def _norm_text(t, limit=90):
    t = (t or "").lower()
    t = re.sub(r"[^a-záéíóúñü0-9 ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:limit]


def _collapse(ts):
    """Colapsa runs consecutivos: 'terminal,terminal,terminal' no es un procedimiento, es un run."""
    out = []
    for t in ts:
        if not out or out[-1] != t:
            out.append(t)
    return out


def patterns(reports, min_sessions=3):
    """Lo que se repite en N sesiones distintas no es torpeza puntual: es sistema."""
    from collections import defaultdict
    fail, loop, wr, corr, seq = (defaultdict(dict) for _ in range(5))
    no_seq = 0

    def bump(store, key, sid, **extra):
        d = store.setdefault(key, {"sessions": [], "examples": []})
        if sid not in d["sessions"]:
            d["sessions"].append(sid)
        for k, v in extra.items():
            if v not in (None, "") and not d.get(k):
                d[k] = v

    for r in reports:
        sid = (r.get("session") or {}).get("id") or "?"
        for f in r.get("failures") or []:
            bump(fail, "%s [%s]" % (f.get("tool"), f.get("kind")), sid,
                 excerpt=(f.get("excerpt") or "")[:120], idx=f.get("idx"))
        for l in r.get("loops") or []:
            bump(loop, "%s x%d %s" % (l.get("tool"), l.get("count") or 0, (l.get("args") or "")[:60]), sid,
                 args=(l.get("args") or "")[:120], kind=l.get("kind"))
        for w in (r.get("hygiene") or {}).get("writes_without_prior_read") or []:
            if w.get("path"):
                bump(wr, w["path"], sid, tool=w.get("tool"))
        for c in (r.get("user") or {}).get("corrections") or []:
            bump(corr, _norm_text(c.get("text")), sid, text=(c.get("text") or "")[:140])
        ts = _collapse(r.get("tool_sequence") or [])
        if len(ts) >= 3:
            for i in range(len(ts) - 2):
                bump(seq, " -> ".join(ts[i:i + 3]), sid, seq=ts[i:i + 3])
        else:
            no_seq += 1

    def rank(store):
        rows = []
        for k, v in store.items():
            row = {"pattern": k, "sessions": len(v["sessions"]), "ids": v["sessions"][:8]}
            for kk, vv in v.items():
                if kk != "sessions":
                    row[kk] = vv
            if row["sessions"] >= min_sessions:
                rows.append(row)
        return sorted(rows, key=lambda x: -x["sessions"])[:10]

    return {
        "sessions": len(reports),
        "min_sessions": min_sessions,
        "sessions_sin_secuencia": no_seq,
        "fallos_recurrentes": rank(fail),
        "bucles_de_sistema": rank(loop),
        "escrituras_repetidas": rank(wr),
        "correcciones_repetidas": rank(corr),
        "procedimientos": rank(seq),
    }


def digest_patterns(p):
    out = ["PEGUELO PATRONES · %d sesiones con actividad · umbral %d sesiones"
           % (p["sessions"], p["min_sessions"])]
    bloques = [
        ("FALLOS RECURRENTES", p["fallos_recurrentes"], "excerpt"),
        ("BUCLES DE SISTEMA", p["bucles_de_sistema"], "args"),
        ("ESCRITURAS SIN LECTURA", p["escrituras_repetidas"], "tool"),
        ("CORRECCIONES REPETIDAS", p["correcciones_repetidas"], "text"),
        ("PROCEDIMIENTOS (candidato a skill)", p["procedimientos"], None),
    ]
    hubo = False
    for titulo, rows, extra in bloques:
        if not rows:
            continue
        hubo = True
        out.append("%s:" % titulo)
        for r in rows[:6]:
            det = (r.get(extra) if extra else "") or ""
            out.append("  x%d %s%s" % (r["sessions"], r["pattern"][:110],
                                       (" · " + det[:70]) if det else ""))
    if not hubo:
        out.append("sin patrones sobre el umbral: cada fallo aparece en < %d sesiones" % p["min_sessions"])
    if p.get("sessions_sin_secuencia"):
        out.append("nota: %d sesion(es) con <3 tool calls no aportan a procedimientos" % p["sessions_sin_secuencia"])
    return "\n".join(out)


# ───────────────────────── digest ─────────────────────────
def digest(r):
    s = r["session"]
    t = r["totals"]
    out = []
    out.append("PEGUELO · %s · %s" % (s["id"], (s["title"] or "")[:70]))
    out.append("modelo=%s fuente=%s perfil=%s dur=%smin msgs=%s tools=%s api=%s tok_in=%s tok_out=%s" % (
        s.get("model"), s.get("source"), s.get("profile"), s.get("duration_min"),
        r["messages"]["read"], t["tool_calls"], s.get("api_call_count"),
        s.get("input_tokens"), s.get("output_tokens")))
    out.append("fallos=%d/%d (%.0f%%) sin_resultado=%d herramientas=%d repeticiones=%d" % (
        t["failures"], t["tool_calls"], 100 * t["failure_rate"], t["no_result"], t["distinct_tools"], t["repeated_calls"]))
    top = sorted(r["tools"].items(), key=lambda kv: kv[1]["calls"], reverse=True)[:8]
    out.append("tools: " + " · ".join("%s %d%s" % (k, v["calls"], ("/%df" % v["failures"]) if v["failures"] else "") for k, v in top))
    if r["failures"]:
        out.append("FALLOS:")
        for f in r["failures"][:6]:
            out.append("  #%s %s [%s] %s" % (f["idx"], f["tool"], f["kind"], f["excerpt"][:110].replace("\n", " ")))
    if r["loops"]:
        out.append("BUCLES:")
        for l in r["loops"][:4]:
            out.append("  %s x%d (%s) %s" % (l["tool"], l["count"], l["kind"], l["args"][:90]))
    if r["duplicates"]:
        out.append("REPETIDAS: " + "; ".join("%s x%d" % (d["tool"], d["count"]) for d in r["duplicates"][:6]))
    h = r["hygiene"]
    out.append("higiene: escrituras=%d creaciones=%d ambiguas=%d sin_lectura_previa=%d verificacion_post=%s destructivos=%d" % (
        len(h["writes"]), len(h.get("creates") or []), len(h.get("ambiguous_writes") or []),
        len(h["writes_without_prior_read"]), h["verification_after_write"], len(h["destructive_commands"])))
    for w in h["writes_without_prior_read"][:4]:
        out.append("  sin_lectura: %s %s" % (w["tool"], w["path"]))
    for d in h["destructive_commands"][:3]:
        out.append("  destructivo: %s" % d["cmd"][:100])
    u = r["user"]
    out.append("usuario: turnos=%d correcciones_candidatas=%d" % (u["turns"], len(u["corrections"])))
    for c in u["corrections"][:5]:
        out.append("  correccion #%s: %s" % (c["idx"], c["text"][:160].replace("\n", " ")))
    f = r["flags"]
    if f["claims_without_evidence"]:
        out.append("SIN EVIDENCIA (%d):" % len(f["claims_without_evidence"]))
        for c in f["claims_without_evidence"][:3]:
            out.append("  #%s %s" % (c["idx"], c["text"][:140].replace("\n", " ")))
    if f["promises_without_action"]:
        out.append("PROMESAS SIN ACCION (%d):" % len(f["promises_without_action"]))
        for c in f["promises_without_action"][:3]:
            out.append("  #%s %s" % (c["idx"], c["text"][:140].replace("\n", " ")))
    return "\n".join(out)


def aggregate(reports):
    agg = {"sessions": len(reports), "tool_calls": 0, "failures": 0, "by_tool": {},
           "corrections": 0, "claims_without_evidence": 0, "promises_without_action": 0,
           "writes_without_prior_read": 0}
    for r in reports:
        agg["tool_calls"] += r["totals"]["tool_calls"]
        agg["failures"] += r["totals"]["failures"]
        agg["corrections"] += len(r["user"]["corrections"])
        agg["claims_without_evidence"] += len(r["flags"]["claims_without_evidence"])
        agg["promises_without_action"] += len(r["flags"]["promises_without_action"])
        agg["writes_without_prior_read"] += len(r["hygiene"]["writes_without_prior_read"])
        for k, v in r["tools"].items():
            a = agg["by_tool"].setdefault(k, {"calls": 0, "failures": 0})
            a["calls"] += v["calls"]
            a["failures"] += v["failures"]
    return agg


# ───────────────────────── selftest ─────────────────────────
def selftest():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript("""
    CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, source TEXT, profile_name TEXT, model TEXT,
        started_at REAL, last_activity_at REAL, message_count INT, tool_call_count INT, api_call_count INT,
        input_tokens INT, output_tokens INT, cache_read_tokens INT, estimated_cost_usd REAL,
        parent_session_id TEXT, cwd TEXT, git_branch TEXT);
    CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, tool_name TEXT,
        tool_call_id TEXT, tool_calls TEXT, timestamp REAL, active INTEGER DEFAULT 1);
    """)
    now = time.time()
    con.execute("INSERT INTO sessions VALUES ('S1','prueba','cli','default','m',?,?,21,10,5,1000,200,0,0.0,NULL,'/tmp','main')", (now - 600, now))
    # S2 existe como fila pero no tiene mensajes: arranque de cron vacio (D2)
    con.execute("INSERT INTO sessions VALUES ('S2','vacia','cron','default','m',?,?,0,0,0,0,0,0,0.0,NULL,NULL,NULL)", (now - 900, now - 800))
    _fd, existente = tempfile.mkstemp(suffix=".txt")
    os.close(_fd)
    nuevo = "/tmp/peguelo_selftest_nuevo_%d.txt" % os.getpid()
    msgs = []
    def add(role, content="", tool_name=None, call_id=None, calls=None):
        msgs.append((role, content, tool_name, call_id, json.dumps(calls) if calls else ""))
    def call(cid, name, args):
        return {"call_id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
    add("user", "hazlo")
    add("assistant", "", calls=[call("a1", "terminal", {"command": "ls"}), call("a2", "read_file", {"path": "/tmp/x"})])
    add("tool", '{"exit_code": 0, "output": "ok"}', "terminal", "a1")
    add("tool", '{"content": "hola"}', "read_file", "a2")
    # creacion: el archivo no existia -> NO es violacion de pre-flight (D1)
    add("assistant", "", calls=[call("a3", "write_file", {"path": nuevo, "content": "x"})])
    add("tool", '{"ok": true}', "write_file", "a3")
    # write_file sobre archivo existente sin lectura: ambigua (no se puede probar si nacio aqui)
    add("assistant", "", calls=[call("a5", "write_file", {"path": existente, "content": "x"})])
    add("tool", '{"ok": true}', "write_file", "a5")
    # patch sobre archivo existente sin lectura: violacion inequivoca (editar exige que exista)
    add("assistant", "", calls=[call("a6", "patch", {"path": existente, "old_string": "a", "new_string": "b"})])
    add("tool", '{"ok": true}', "patch", "a6")
    add("assistant", "", calls=[call("a4", "terminal", {"command": "pytest -q"})])
    add("tool", '{"exit_code": 0, "output": "3 passed"}', "terminal", "a4")
    add("assistant", "Listo, verificado.")
    add("user", "no, eso esta mal, revisa el archivo")
    # pregunta de estado: NO es correccion, aunque diga "falta" (D3)
    add("user", "mientras arreglamos eso dame un resumen de como vas, que falta")
    for i, cid in enumerate(("b1", "b2", "b3")):
        add("assistant", "", calls=[call(cid, "terminal", {"command": "python3 roto.py"})])
        add("tool", '{"error": "hook /x.py failed closed: command not found"}', "terminal", cid)
    add("assistant", "Voy a ejecutarlo ahora.")
    for i, (role, content, tool_name, call_id, calls) in enumerate(msgs, start=1):
        con.execute("INSERT INTO messages (id, session_id, role, content, tool_name, tool_call_id, tool_calls, timestamp, active) "
                    "VALUES (?,?,?,?,?,?,?,?,1)", (i, "S1", role, content, tool_name, call_id, calls, now - 600 + i))
    r = analyze_session(con, "S1")
    def _latest(n, skip=True):
        try:
            return latest_sessions(con, n, skip_empty=skip)
        except TypeError:  # version sin el filtro (D2): el test debe fallar, no romper
            return latest_sessions(con, n)
    checks = [
        ("tool_calls", r["totals"]["tool_calls"], 9),
        ("failures", r["totals"]["failures"], 3),
        ("writes", len(r["hygiene"]["writes"]), 3),
        ("creaciones", len(r["hygiene"].get("creates") or []), 1),
        ("ambiguas", len(r["hygiene"].get("ambiguous_writes") or []), 1),
        ("edicion_sin_lectura", len(r["hygiene"]["writes_without_prior_read"]), 1),
        ("verificacion", r["hygiene"]["verification_after_write"], True),
        ("correcciones", len(r["user"]["corrections"]), 1),
        ("sesiones_utiles", _latest(5), ["S1"]),
        ("sesiones_sin_filtro", sorted(_latest(5, skip=False)), ["S1", "S2"]),
        ("omitidas_vacias", skipped_empty_count(con, 5, ["S1"]), 1),
        ("bucle", len(r["loops"]), 1),
        ("promesa_sin_accion", len(r["flags"]["promises_without_action"]), 1),
        ("claim_con_evidencia", len(r["flags"]["claims_without_evidence"]), 0),
    ]
    for p in (existente, nuevo):
        try:
            os.unlink(p)
        except OSError:
            pass
    # ── patrones cross-sesion (F4): lo que se repite en 3 sesiones no es torpeza puntual
    P = globals().get("patterns")
    def _pat(reps):
        if P is None:  # funcion aun no implementada: el check debe fallar, no romper
            return {"fallos_recurrentes": [], "procedimientos": [], "escrituras_repetidas": [],
                    "correcciones_repetidas": [], "bucles_de_sistema": [], "sessions": len(reps)}
        return P(reps, min_sessions=3)

    def fake(sid):
        return {"session": {"id": sid},
                "failures": [{"tool": "terminal", "kind": "exit_code", "idx": 3, "excerpt": "exit_code=2"}],
                "loops": [], "hygiene": {"writes_without_prior_read": []},
                "user": {"corrections": []},
                "tool_sequence": ["read_file", "patch", "terminal"]}

    p3 = _pat([fake("A"), fake("B"), fake("C")])
    p2 = _pat([fake("A"), fake("B")])
    checks += [
        ("patron_fallo_recurrente", len(p3["fallos_recurrentes"]), 1),
        ("patron_fallo_3_sesiones", p3["fallos_recurrentes"][0]["sessions"] if p3["fallos_recurrentes"] else 0, 3),
        ("patron_procedimiento", len(p3["procedimientos"]), 1),
        ("patron_umbral_respetado", len(p2["fallos_recurrentes"]), 0),
    ]
    # un run de 6 'terminal' no es un procedimiento: se colapsa antes de los n-gramas
    run = {"session": {"id": "D"}, "failures": [], "loops": [],
           "hygiene": {"writes_without_prior_read": []}, "user": {"corrections": []},
           "tool_sequence": ["terminal"] * 6}
    prun = P([run], min_sessions=1) if P else {"procedimientos": []}
    checks.append(("patron_runs_colapsados", len(prun["procedimientos"]), 0))
    bad = [(n, got, exp) for n, got, exp in checks if got != exp]
    for n, got, exp in checks:
        print("%-22s %-8s got=%r exp=%r" % (n, "OK" if got == exp else "FALLA", got, exp))
    if bad:
        print("SELFTEST FALLIDO: %d" % len(bad))
        return 1
    print("SELFTEST OK (%d comprobaciones)" % len(checks))
    return 0


# ───────────────────────── main ─────────────────────────
def main(argv=None):
    ap = argparse.ArgumentParser(description="Dossier forense de sesion Hermes (solo lectura)")
    ap.add_argument("--session", help="id de sesion")
    ap.add_argument("--last", type=int, default=0, help="analizar las N ultimas sesiones CON actividad")
    ap.add_argument("--patrones", nargs="?", type=int, const=25, default=None,
                    metavar="N", help="barrido cross-sesion de las N ultimas sesiones con actividad (default 25)")
    ap.add_argument("--include-empty", action="store_true", help="incluir sesiones sin mensajes (auditoria)")
    ap.add_argument("--lineage", action="store_true", help="incluir cadena parent_session_id")
    ap.add_argument("--db", help="ruta de state.db")
    ap.add_argument("--out", help="ruta del JSON de salida")
    ap.add_argument("--json", action="store_true", help="imprimir JSON completo")
    ap.add_argument("--cap", type=int, default=4000, help="max mensajes por sesion")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    db = find_db(args.db)
    con = connect(db)

    if args.patrones:
        n = max(2, int(args.patrones))
        sids = latest_sessions(con, n, skip_empty=not args.include_empty)
        if not sids:
            raise SystemExit("peguelo: no hay sesiones con actividad en %s" % db)
        reps = [analyze_session(con, s, cap=args.cap) for s in sids]
        pat = patterns(reps)
        out = args.out or os.path.join(OUT_DIR, "patrones-%s.json" % time.strftime("%Y%m%d-%H%M%S"))
        try:
            d = os.path.dirname(out)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(pat, fh, ensure_ascii=False, indent=1)
        except Exception as exc:
            print("peguelo: no pude escribir %s (%s); uso stdout" % (out, exc))
            out = None
        if args.json:
            print(json.dumps(pat, ensure_ascii=False, indent=1))
        else:
            print(digest_patterns(pat))
        print("FULL_JSON: %s" % (out or "(stdout)"))
        return 0

    skipped_empty = 0
    if args.last and args.last > 1:
        sids = latest_sessions(con, args.last, skip_empty=not args.include_empty)
        if not args.include_empty:
            # Cuantas de las N mas recientes se omitieron: se compara contra el ranking sin filtro,
            # no contra otro LIMIT N (que devolveria siempre N y daria 0).
            skipped_empty = skipped_empty_count(con, args.last, sids)
    else:
        sid = args.session or os.environ.get("HERMES_SESSION_ID") or (latest_sessions(con, 1) or [None])[0]
        if not sid:
            raise SystemExit("peguelo: no hay sesiones en %s" % db)
        sids = [sid]

    reports = []
    for sid in sids:
        ids = lineage(con, sid) if args.lineage else [sid]
        rep = analyze_session(con, sid, cap=args.cap)
        if len(ids) > 1:
            merged = rep
            merged["lineage"] = ids
            merged["lineage_reports"] = []
            for parent in ids[:-1]:
                pr = analyze_session(con, parent, cap=args.cap)
                merged["lineage_reports"].append({"id": parent, "totals": pr["totals"],
                                                  "user": pr["user"], "flags": pr["flags"]})
            reports.append(merged)
        else:
            reports.append(rep)

    if len(reports) == 1:
        payload = reports[0]
    else:
        agg = aggregate(reports)
        agg["sessions_skipped_empty"] = skipped_empty
        payload = {"schema": SCHEMA_VERSION, "generated_at": iso(time.time()),
                   "sessions": reports, "aggregate": agg}
    out = args.out
    if not out:
        os.makedirs(OUT_DIR, exist_ok=True) if not os.environ.get("PEGUELO_SKIP_MKDIR") else None
        out = os.path.join(OUT_DIR, "%s.json" % (sids[0] if len(sids) == 1 else "last%d" % len(sids)))
    try:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
    except Exception as exc:
        print("peguelo: no pude escribir %s (%s); uso stdout" % (out, exc))
        out = None

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    else:
        if len(reports) == 1:
            print(digest(reports[0]))
        else:
            for r in reports:
                print(digest(r)); print("-" * 60)
            print("AGREGADO:", json.dumps(payload["aggregate"], ensure_ascii=False))
        print("FULL_JSON: %s" % (out or "(stdout)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
