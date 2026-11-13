#!/usr/bin/env python3
"""Hook `read-before-patch`: bloquea patch/edit_file sobre contenido no visto (CA1-CA10).

Contrato de shell_hooks.py (02-design §1):
- entrada (stdin JSON): {hook_event_name, tool_name, tool_input, session_id, cwd, extra}
- salida (stdout JSON opcional): {"decision": "block", "reason": "..."}; bloqueo = exit 2
- fail-open: cualquier error interno -> exit 0 + línea {"ev":"error"} en el ledger (CA10)

Eventos:
- pre_tool_call  (patch|edit_file): decide allow/block según el ledger de la sesión.
  Permitido solo si la huella (mtime_ns, size) del archivo coincide con la última
  lectura/escritura registrada (CA2-CA4). Ruta inexistente -> allow (CA5).
  Rutas relativas contra `cwd` del payload; symlinks vía realpath (CA6).
  Sin cwd y ruta relativa -> 'unknown_cwd', se permite, NUNCA se resuelve contra
  os.getcwd() del proceso (ronda 2 / L2). Sin clave 'path' -> 'no_path' en el
  ledger, se permite con rastro (ronda 2 / L3).
- post_tool_call (read_file|write_file|patch|edit_file): registra la huella.
  Registra SOLO si extra.status == 'ok' o si la clave no viene (payload legacy con
  'ok'; sin ninguna de las dos se asume exitoso). Con status 'error'|'cancelled'|'blocked'
  NUNCA registra: un patch bloqueado (status='blocked') dispara post_tool_call y no
  debe marcar la ruta como vista, o el reintento idéntico pasaría (ronda 2 / H1).
  - read_file (ronda 4 / TOCTOU): el pre dejó una entrada 'read_pending' con la
    huella capturada ANTES de la lectura; el post promueve ESA huella (lo que el
    agente vio). Sin pendiente (hook legacy sin pre, o pre sin sesión) se registra
    la huella de disco actual, como siempre: es el mismo comportamiento de antes,
    y el pre corre en toda instalación viva.
  - patch mode='patch' V4A (ronda 4 / H2): registra CADA ruta de las cabeceras
    '*** Update|Delete|Add File:' del texto con la huella posterior, igual que
    hace el pre al decidir; así dos V4A consecutivos no se bloquean.
  Cualquier otra tool no toca el ledger.

Modos (CA7/CA8): env READ_BEFORE_PATCH_MODE=shadow|enforce o archivo MODE junto al
ledger; default shadow. En shadow: exit 0 siempre, {"ev":"would_block"} en el ledger,
payload sin 'decision':'block'. Kill switch: archivo DISABLED -> permite todo (CA9);
el evento 'disabled' se loguea UNA vez por sesión (se consulta el ledger bajo LOCK_SH
entre procesos, ronda 2 / L1).

Uso: python3 guard_read_before_patch.py < event.json   (main() -> exit code)
"""

import hashlib
import json
import os
import re
import sys

import read_before_patch_state as state

EDIT_TOOLS = {"patch", "edit_file"}
RECORD_TOOLS = {"read_file", "write_file", "patch", "edit_file"}

_disabled_logged = set()  # "lo registra una vez" (CA9): por sesión y proceso

# V4A: cabeceras de parche multi-archivo. Anclada a línea; admite espacios
# sobrantes y rutas con espacios. NO matchea '*** Move to:', '*** Begin Patch'
# ni '*** End Patch' (solo Update/Delete/Add File).
_V4A_HEADER_RE = re.compile(
    r"^\*\*\*[ \t]+(Update|Delete|Add)[ \t]+File:[ \t]*(.+?)[ \t]*$",
    re.MULTILINE,
)


def _v4a_file_ops(patch_text: str):
    """Extrae [(accion, ruta)] de las cabeceras V4A, en orden de aparición.
    accion en {'Update', 'Delete', 'Add'}; rutas crudas (relativas o absolutas)."""
    ops = []
    for match in _V4A_HEADER_RE.finditer(patch_text or ""):
        action = match.group(1)
        raw_path = match.group(2)
        if raw_path:
            ops.append((action, raw_path))
    return ops


def _fingerprint_ok(session_id, resolved, root=None):
    """(huella_vigente, last, current): True si el ledger registra una lectura
    de `resolved` con huella (mtime_ns, size) igual a la actual en disco
    (CA2-CA4); desempata por contenido si hay digest (mismo tamaño en el
    mismo tick del reloj)."""
    last = state.last_seen(session_id, resolved, root=root)
    current = state.fingerprint(resolved)
    if last and (last.get("mtime_ns"), last.get("size")) == tuple(current):
        lsha = last.get("sha256")
        csha = state.file_digest(resolved)
        if not (lsha and csha) or lsha == csha:
            return True, last, current
    return False, last, current


def _stale_reason(resolved, last, current) -> str:
    return (
        "Ejecuta read_file %s antes de editarlo: cambió desde la última lectura "
        "(o no la hubo en esta sesión). Huella registrada: %s/%s. Actual: %s/%s."
        % (
            resolved,
            last.get("mtime_ns") if last else "-",
            last.get("size") if last else "-",
            current[0],
            current[1],
        )
    )


def _raw_path(event: dict):
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    raw = tool_input.get("path")
    return raw if isinstance(raw, str) and raw else None


def _resolve(event: dict):
    """Ruta real contra la que comparar: realpath(join(cwd del payload, path)).
    Devuelve (ruta, problema) con problema en {None, 'no_path', 'unknown_cwd'}:
    - sin clave 'path' (o vacía) -> ('', 'no_path')  (ronda 2 / L3)
    - cwd ausente/vacío y path relativo -> ('', 'unknown_cwd'): jamás se resuelve
      contra os.getcwd() del proceso, el hook puede correr en otro directorio
      (ronda 2 / L2). Un path ABSOLUTO no necesita cwd y se resuelve igual."""
    raw = _raw_path(event)
    if not raw:
        return "", "no_path"
    cwd = event.get("cwd")
    has_cwd = isinstance(cwd, str) and bool(cwd.strip())
    if not has_cwd and not os.path.isabs(raw):
        return "", "unknown_cwd"
    try:
        return os.path.realpath(os.path.join(str(cwd) if has_cwd else "", raw)), None
    except Exception:
        return os.path.realpath(raw), None


def _log_error(session_id, root, exc: Exception) -> None:
    try:
        state.log_event(
            session_id,
            "error",
            root=root,
            error="%s: %s" % (type(exc).__name__, exc),
        )
    except Exception:
        pass


def _pre_v4a(event: dict, session_id, root=None, tool_input=None):
    """pre_tool_call de `patch` en modo V4A: tool_input={'mode': 'patch',
    'patch': <texto>} y SIN 'path'. Parsea las cabeceras del parche y aplica la
    misma regla por archivo que mode='replace':
    - Add File (creación) -> no exige lectura (crear no es ciego).
    - Update/Delete File de archivo existente -> exige huella vigente (CA2-CA4).
    - Varias rutas: basta UNA sin huella para bloquear; el reason nombra SOLO
      la primera ruta fallida (no las ya leídas).
    - Sin cabeceras reconocibles -> se permite con evento 'unparsed_patch'."""
    tool = "patch"
    patch_text = (tool_input or {}).get("patch")
    ops = _v4a_file_ops(patch_text) if isinstance(patch_text, str) else []
    if not ops:
        state.log_event(session_id, "unparsed_patch", root=root, tool=tool)
        return 0, {}

    if not session_id:
        # Sin sesión no se puede atribuir la lectura: allow + log (02-design §2.4).
        state.log_event(None, "no_session", root=root, tool=tool, path=ops[0][1])
        return 0, {}

    cwd = event.get("cwd")
    has_cwd = isinstance(cwd, str) and bool(cwd.strip())

    # Ronda 9 / G1: recorrer TODAS las rutas de las cabeceras y capturar
    # snapshot/pendiente de cada una ANTES de decidir el retorno/bloqueo. En
    # shadow el bucle de decisión retorna en la PRIMERA ruta no leída: sin esta
    # separación, las rutas posteriores del mismo parche multi-archivo quedan
    # sin pendiente y el post las certifica por el fallback legacy (huella de
    # disco al llegar el post, aunque un tercero las haya sobrescrito tras el
    # patch). Se captura aunque luego se bloquee: el post de un patch bloqueado
    # no registra nada de todos modos (ronda 2 / H1).
    decided_ops = []
    for action, raw_path in ops:
        if action == "Add":
            continue  # crear no es ciego
        if not has_cwd and not os.path.isabs(raw_path):
            # L2: no se resuelve contra os.getcwd() del proceso; se registra y
            # esa ruta no exige huella (las demás rutas del parche siguen).
            state.log_event(
                session_id, "unknown_cwd", root=root, tool=tool, path=raw_path
            )
            continue
        try:
            resolved = os.path.realpath(
                os.path.join(str(cwd) if has_cwd else "", raw_path)
            )
        except Exception:
            resolved = os.path.realpath(raw_path)
        if not os.path.exists(resolved):
            continue  # CA5: la herramienta de edición reportará su propio error
        _snapshot_write_pending(session_id, resolved, root=root, call_id=_call_id(event))
        decided_ops.append(resolved)

    # Decisión (ronda 9 / G1): SOLO tras capturar todas las pendientes.
    for resolved in decided_ops:
        try:
            ok, last, current = _fingerprint_ok(session_id, resolved, root=root)
        except Exception as exc:  # CA10: fail-open
            _log_error(session_id, root, exc)
            continue
        if ok:
            continue  # vio exactamente el contenido que hay ahora

        reason = _stale_reason(resolved, last, current)
        if state.mode(root) == "enforce":
            state.log_event(session_id, "block", root=root, tool=tool, path=resolved)
            return 2, {"decision": "block", "reason": reason}
        # shadow: registra lo que habría bloqueado y NO bloquea (CA7)
        state.log_event(
            session_id, "would_block", root=root, tool=tool, path=resolved, reason=reason
        )
        return 0, {"ev": "would_block", "reason": reason}

    return 0, {}


def _call_id(event: dict):
    """Identificador de llamada para emparejar pendientes pre/post (ronda 6 / B1):
    extra.tool_call_id si viene; si no, uno derivado de forma DETERMINISTA del
    payload (session_id + tool_input), que el pre y el post de la MISMA llamada
    recalculan igual. None si no hay forma estable de derivarlo."""
    extra = event.get("extra")
    if isinstance(extra, dict):
        cid = extra.get("tool_call_id")
        if isinstance(cid, str) and cid:
            return cid
    tool_input = event.get("tool_input")
    try:
        base = json.dumps(
            {"s": event.get("session_id"), "ti": tool_input},
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
    except Exception:
        return None
    return "derived:" + hashlib.sha256(
        base.encode("utf-8", "surrogateescape")
    ).hexdigest()[:16]


def _snapshot_write_pending(session_id, resolved, root=None, call_id=None) -> None:
    """Captura en el PRE de patch/edit_file el contenido previo como pendiente
    de escritura {'ev':'write_pending', path, mtime_ns, size, pre_sha256,
    call_id, snap} (ronda 6 / B2; ronda 7 / H-A): el POST reconstruye desde
    aquí el contenido ESPERADO y solo certifica si coincide con el disco al
    llegar el post. El CONTENIDO previo va a un snapshot EFÍMERO fuera del
    ledger (state.snapshot_write: <root>/snapshots/<session>/<call_id>.snap,
    directorio 0700 y archivo 0600, borrado por el post que lo consume y con
    barrido TTL en la poda): el ledger JSONL jamás contiene contenido de
    archivo (02-design §4, 'solo huellas'). Si el snapshot no se puede escribir
    (permisos/ENOSPC o archivo > DIGEST_CAP) la pendiente marca 'snap_failed':
    el POST cae fail-closed (no certificar) en vez de certificar la huella de
    disco. Nunca lanza (CA10)."""
    try:
        mtime_ns, size = state.fingerprint(resolved)
        fields = {"path": resolved, "mtime_ns": mtime_ns, "size": size}
        snap = state.snapshot_write(session_id, resolved, root=root, call_id=call_id)
        if snap:
            fields["snap"] = snap
        else:
            fields["snap_failed"] = True
        pre_sha = state.file_digest(resolved)
        if pre_sha:
            fields["pre_sha256"] = pre_sha
        if call_id:
            fields["call_id"] = call_id
        state.log_event(session_id, "write_pending", root=root, **fields)
    except Exception as exc:  # CA10: fail-open
        _log_error(session_id, root, exc)


def _pending_content(pending, root=None) -> "str | None":
    """Contenido previo de una pendiente de escritura (ronda 7 / H-A): se lee
    del snapshot EFÍMERO (pendiente['snap']) y el archivo .snap se BORRA en el
    mismo acto (consumo único: el post que lo consume es el único que lo usa).
    Compat: pendientes escritas por versiones anteriores con 'content' dentro
    del ledger (solo lectura; el ledger nuevo jamás escribe contenido).
    None si no hay contenido utilizable (snapshot ausente para ese path)."""
    if not isinstance(pending, dict):
        return None
    snap = pending.get("snap")
    if isinstance(snap, str) and snap:
        content = state.snapshot_read(snap)
        state.snapshot_delete(snap)
        if content is not None:
            return content
    legacy = pending.get("content")
    if isinstance(legacy, str):
        return legacy
    return None


def _expected_after_replace(snapshot: str, tool_input) -> "str | None":
    """Contenido esperado tras un patch/edit_file mode='replace' (ronda 6 / B2a):
    old_string -> new_string sobre el snapshot del pre (una vez, o todas con
    replace_all). None si el reemplazo no es reconstruible (sin old/new, o
    old_string no está en el snapshot: la tool fallaría igual)."""
    if not isinstance(tool_input, dict):
        return None
    old = tool_input.get("old_string")
    new = tool_input.get("new_string")
    if not (isinstance(old, str) and isinstance(new, str)):
        return None
    if old not in snapshot:
        return None
    if tool_input.get("replace_all"):
        return snapshot.replace(old, new)
    return snapshot.replace(old, new, 1)


def _v4a_sections(patch_text: str):
    """[(accion, raw_path, body)] por sección del parche V4A (ronda 6 / B2b):
    body son las líneas del cuerpo (hunks) entre esta cabecera y la siguiente,
    sin cabeceras ni líneas '@@'. Ancla idéntica a _v4a_file_ops."""
    text = patch_text or ""
    matches = list(_V4A_HEADER_RE.finditer(text))
    sections = []
    for i, match in enumerate(matches):
        start = match.end()
        # El salto de línea de la propia cabecera no es parte del cuerpo: sin
        # esto, splitlines() deja una línea vacía inicial que el aplicador
        # interpretaría como contexto y descartaría el parche (ronda 6 / B2).
        if start < len(text) and text[start] == "\n":
            start += 1
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = []
        for line in text[start:end].splitlines():
            if line.startswith("***"):
                break  # '*** End Patch' u otra directiva: fin del cuerpo
            if line.startswith("@@"):
                continue
            body.append(line)
        sections.append((match.group(1), match.group(2), body))
    return sections


def _apply_v4a_body(old_text: str, body: list) -> "str | None":
    """Aplica los hunks del cuerpo de una sección V4A al contenido previo
    (ronda 6 / B2b). Devuelve el texto esperado, o None si el parche no aplica
    de forma determinista (contexto/minus desalineado, p. ej. un hunk que no
    empieza en la primera línea del contenido previo) — en ese caso el post
    cae fail-closed ('write_unverifiable', ronda 7 / H-B) en vez de certificar
    a ciegas."""
    ops = []
    for line in body:
        if line.startswith("+"):
            ops.append(("+", line[1:]))
        elif line.startswith("-"):
            ops.append(("-", line[1:]))
        else:
            # contexto (' ...') o línea en blanco: ambas son líneas intactas
            ops.append((" ", line[1:] if line.startswith(" ") else line))
    old_lines = old_text.split("\n")
    out = []
    i = 0
    for op, txt in ops:
        if op == "+":
            out.append(txt)
            continue
        if i < len(old_lines) and old_lines[i] == txt:
            if op == " ":
                out.append(old_lines[i])
            i += 1
        else:
            return None
    out.extend(old_lines[i:])
    return "\n".join(out)


def _expected_add_file(body: list) -> str:
    """Contenido esperado de un '*** Add File:' (ronda 6 / B2c): el bloque
    literal, una línea por cada '+' del cuerpo (con \\n final por línea)."""
    return "".join(line[1:] + "\n" for line in body if line.startswith("+"))


def _certify_against_snapshot(session_id, tool, resolved, expected_text, root=None) -> bool:
    """Certificación por intención del POST de escritura (ronda 6 / B2):
    sha256(esperado reconstruido) vs sha256(disco al llegar el post).
    Iguales -> registra la huella con ESE sha256 y devuelve True.
    Distintos (u omitido el digest: archivo > cap) -> NO registra, anota
    'write_concurrent' (fail-closed) y devuelve False. Nunca lanza (CA10)."""
    try:
        expected_sha = hashlib.sha256(
            expected_text.encode("utf-8", "surrogateescape")
        ).hexdigest()
        disk_sha = state.file_digest(resolved)
        if disk_sha is None or disk_sha != expected_sha:
            state.log_event(
                session_id, "write_concurrent", root=root, tool=str(tool), path=resolved
            )
            return False
        mtime_ns, size = state.fingerprint(resolved)
        state.record_seen(
            session_id, tool, resolved, mtime_ns, size, root=root, sha256=expected_sha
        )
        return True
    except Exception as exc:  # CA10: fail-open
        _log_error(session_id, root, exc)
        return False


def _pre_read(event: dict, session_id, root=None):
    """pre_tool_call de read_file (ronda 4 / TOCTOU-H1): captura la huella ANTES
    de que la tool lea, como entrada pendiente {'ev':'read_pending', path,
    mtime_ns, size, t}. El post de la MISMA lectura la promueve a 'seen', así que
    otro proceso que escriba entre la lectura y el post NO queda certificado
    como visto. Las reglas de resolución son las mismas del pre de edición
    (cwd del payload, realpath; sin cwd y ruta relativa -> nada pendiente, L2)."""
    if not session_id:
        return 0, {}
    tool_input = event.get("tool_input")
    raw = tool_input.get("path") if isinstance(tool_input, dict) else None
    if not isinstance(raw, str) or not raw:
        return 0, {}
    cwd = event.get("cwd")
    has_cwd = isinstance(cwd, str) and bool(cwd.strip())
    if not has_cwd and not os.path.isabs(raw):
        return 0, {}  # L2: jamás se resuelve contra os.getcwd() del proceso
    try:
        resolved = os.path.realpath(os.path.join(str(cwd) if has_cwd else "", raw))
    except Exception:
        try:
            resolved = os.path.realpath(raw)
        except Exception:
            return 0, {}
    if not os.path.exists(resolved):
        return 0, {}  # la lectura fallará; no hay contenido que certificar
    try:
        mtime_ns, size = state.fingerprint(resolved)
        state.log_event(
            session_id,
            "read_pending",
            root=root,
            path=resolved,
            mtime_ns=mtime_ns,
            size=size,
            call_id=_call_id(event),  # ronda 6 / B1: empareje pre-post por llamada
        )
    except Exception as exc:  # CA10: fail-open
        _log_error(session_id, root, exc)
    return 0, {}


def _pre(event: dict, session_id, root=None):
    tool = event.get("tool_name")
    if tool == "read_file":
        return _pre_read(event, session_id, root)
    if tool not in EDIT_TOOLS:
        return 0, {}

    tool_input = event.get("tool_input")
    if tool == "patch" and isinstance(tool_input, dict) and tool_input.get("mode") == "patch":
        # Bypass V4A: mode='patch' con SOLO la clave 'patch' (sin 'path').
        # La decisión sale de las cabeceras del texto, no de la clave 'path'.
        return _pre_v4a(event, session_id, root, tool_input)

    resolved, issue = _resolve(event)
    if issue == "no_path":
        # L3: sin qué editar no hay decisión que tomar; se permite CON rastro.
        state.log_event(session_id, "no_path", root=root, tool=str(tool))
        return 0, {}
    if issue == "unknown_cwd":
        # L2: cwd ausente/vacío y path relativo -> no se resuelve contra
        # os.getcwd(); se registra y se permite.
        state.log_event(
            session_id, "unknown_cwd", root=root, tool=str(tool), path=_raw_path(event)
        )
        return 0, {}
    if not session_id:
        # Sin sesión no se puede atribuir la lectura: allow + log (02-design §2.4).
        state.log_event(None, "no_session", root=root, tool=str(tool), path=resolved)
        return 0, {}
    if not os.path.exists(resolved):
        return 0, {}  # CA5: la herramienta de edición reportará su propio error

    # Ronda 6 / B2: snapshot del contenido previo (str_replace) para la
    # certificación del post. Igual que en V4A: capturar aunque luego bloquee.
    _snapshot_write_pending(session_id, resolved, root=root, call_id=_call_id(event))

    try:
        last = state.last_seen(session_id, resolved, root=root)
        current = state.fingerprint(resolved)
    except Exception as exc:  # CA10: fail-open
        _log_error(session_id, root, exc)
        return 0, {}

    if last and (last.get("mtime_ns"), last.get("size")) == tuple(current):
        # La huella coincide, pero dos escrituras del mismo tamaño pueden caer en
        # el mismo tick del reloj: desempata por contenido si hay digest en el ledger.
        lsha = last.get("sha256")
        csha = state.file_digest(resolved)
        if not (lsha and csha) or lsha == csha:
            return 0, {}  # CA2/CA4: vio exactamente el contenido que hay ahora

    reason = (
        "Ejecuta read_file %s antes de editarlo: cambió desde la última lectura "
        "(o no la hubo en esta sesión). Huella registrada: %s/%s. Actual: %s/%s."
        % (
            resolved,
            last.get("mtime_ns") if last else "-",
            last.get("size") if last else "-",
            current[0],
            current[1],
        )
    )

    if state.mode(root) == "enforce":
        state.log_event(session_id, "block", root=root, tool=str(tool), path=resolved)
        return 2, {"decision": "block", "reason": reason}

    # shadow: registra lo que habría bloqueado y NO bloquea (CA7)
    state.log_event(
        session_id, "would_block", root=root, tool=str(tool), path=resolved, reason=reason
    )
    return 0, {"ev": "would_block", "reason": reason}


def _post_v4a(event: dict, session_id, root=None, tool_input=None):
    """post_tool_call de patch V4A con resultado ok: registra CADA ruta de las
    cabeceras '*** Update|Delete|Add File:'. Ronda 6 / B2: con snapshot del pre
    ('write_pending') el contenido ESPERADO se reconstruye desde tool_input
    ((b) hunks del patch_text sobre el contenido previo para Update/Delete;
    (c) bloque literal '+' para Add File) y solo se certifica si
    sha256(esperado) == sha256(disco al llegar el post); si difiere NO registra
    y anota 'write_concurrent' (fail-closed). Ronda 7 / H-B: fail-closed REAL —
    con pendiente viva, si la reconstrucción/verificación no es posible (hunk
    no aplicable, snapshot ausente para ese path, pendiente ambigua o snapshot
    no escribible en el pre) NO registra nada y anota 'write_unverifiable': el
    fallback legacy (huella de disco) certificaba una versión potencialmente
    ajena. El fallback legacy queda SOLO para payloads SIN pendiente (post sin
    pre, imposible en producción: el pre corre en toda instalación viva).
    Mismo parsing y resolución que el pre (_pre_v4a). Solo se llega aquí tras
    validar status=='ok' en _post, así que un patch V4A bloqueado no registra
    nada."""
    patch_text = (tool_input or {}).get("patch")
    sections = _v4a_sections(patch_text) if isinstance(patch_text, str) else []
    if not sections:
        return 0, {}
    cwd = event.get("cwd")
    has_cwd = isinstance(cwd, str) and bool(cwd.strip())
    call_id = _call_id(event)
    for action, raw_path, body in sections:
        if not has_cwd and not os.path.isabs(raw_path):
            continue  # L2: no se resuelve contra os.getcwd() del proceso
        try:
            resolved = os.path.realpath(
                os.path.join(str(cwd) if has_cwd else "", raw_path)
            )
        except Exception:
            try:
                resolved = os.path.realpath(raw_path)
            except Exception:
                continue
        if not os.path.exists(resolved):
            # Delete File: el archivo ya no existe (nada que certificar);
            # Add/Update fallado: igual.
            continue
        try:
            if action == "Add":
                # (c) Add File: el contenido esperado es el bloque literal.
                expected = _expected_add_file(body)
            else:
                status, pending = state.pending_write_match(
                    session_id, resolved, root=root, call_id=call_id
                )
                if status == "none":
                    # Ronda 9 / G1: distinguir 'sin pendiente por payload
                    # legacy' (el pre nunca corrió para esta llamada: CERO
                    # pendientes de escritura con este call_id) de 'sin
                    # pendiente por procesamiento incompleto' (el pre capturó
                    # pendientes de OTRAS rutas del MISMO parche multi-archivo
                    # pero no de esta: retorno anticipado en shadow o pre
                    # interrumpido). En el segundo caso la huella de disco
                    # puede certificar contenido ajeno (otro proceso
                    # sobrescribió tras el patch) -> fail-closed: no registrar
                    # y anotar 'write_unverifiable'.
                    if state.has_pending_call(session_id, call_id, root=root):
                        state.log_event(
                            session_id,
                            "write_unverifiable",
                            root=root,
                            tool="patch",
                            path=resolved,
                        )
                        continue
                    # Sin pendiente: payload legacy sin pre (imposible en
                    # producción, el pre corre en toda instalación viva):
                    # comportamiento de antes (ronda 6 / B2).
                    state.record(session_id, "patch", resolved, ok=True, root=root)
                    continue
                content = None
                if status == "match" and isinstance(pending, dict):
                    # (b) Update/Delete: hunks del parche sobre el contenido
                    # previo del snapshot efímero (H-A: se consume y borra).
                    content = _pending_content(pending, root=root)
                # Ronda 7 / H-B: pendiente ambigua, snapshot ausente para el
                # path o hunk no aplicable -> reconstrucción no verificable.
                expected = _apply_v4a_body(content, body) if content is not None else None
                if expected is None:
                    state.log_event(
                        session_id,
                        "write_unverifiable",
                        root=root,
                        tool="patch",
                        path=resolved,
                    )
                    continue
            _certify_against_snapshot(session_id, "patch", resolved, expected, root=root)
        except Exception as exc:  # CA10: fail-open también al registrar
            _log_error(session_id, root, exc)
    return 0, {}


def _result_certified(event: dict) -> bool:
    """Certificación por resultado estructurado (ronda 5 / H2): el post trae
    extra.result con el JSON string del WriteResult/PatchResult
    (tools/file_operations_common.py: WriteResult → {bytes_written, verified,
    error, ...}; PatchResult → {success, diff, files_modified, error, ...};
    `_content_sha256` NO se expone en el dict, así que no se puede comparar el
    contenido intencionado para patch/edit_file — solo para write_file, vía
    tool_input['content']).

    Devuelve True solo si el resultado acredita escritura verificable:
    - sin clave 'result' en extra (payload legacy/antiguo): True — el status ya
      filtró los fallos marcados y se conserva el comportamiento de antes.
    - result no parseable a dict (JSON corrupto), con 'error' presente,
      success=False o verified=False: False (fail-closed: no registrar).
    - éxito: SOLO cuando el resultado reporta success is True o verified is True
      (un resultado sin ninguna marca de éxito tampoco certifica).
    Nota: 'verified' (WriteResult) solo cubre que el disco coincidía con lo
    escrito al terminar la tool."""
    extra = event.get("extra")
    if not isinstance(extra, dict) or "result" not in extra:
        return True  # payload sin resultado estructurado: comportamiento legacy
    result = extra.get("result")
    data = result
    if isinstance(result, (str, bytes)):
        try:
            data = json.loads(result)
        except (ValueError, TypeError):
            return False  # JSON corrupto: no se puede acreditar el éxito
    if not isinstance(data, dict):
        return False
    if data.get("error"):
        return False
    if data.get("success") is False or data.get("verified") is False:
        return False
    return data.get("success") is True or data.get("verified") is True


def _read_result_certified(event: dict) -> bool:
    """Validación del resultado estructurado de read_file (ronda 9 / G2): el
    status 'ok' del runner NO garantiza que la lectura entregara contenido —
    extra.result puede traer el JSON de un ReadResult fallido
    (tools/file_operations_common.py: ReadResult → {content, total_lines,
    error, not_found, ...}; to_dict omite los campos None).

    Devuelve True solo si la lectura es acreditable:
    - sin clave 'result' en extra (payload legacy/antiguo): True — se conserva
      el comportamiento de antes (el status ya filtró los fallos marcados y los
      posts sin result de las rondas previas dependen de esa vía).
    - result no parseable a dict (JSON corrupto) o no-dict: False (no
      verificable -> no promover).
    - con 'error' presente, not_found truthy o success=False: False — la
      lectura NO entregó contenido al agente.
    - éxito (ReadResult.to_dict sin marcas de error): True."""
    extra = event.get("extra")
    if not isinstance(extra, dict) or "result" not in extra:
        return True  # payload sin resultado estructurado: comportamiento legacy
    result = extra.get("result")
    data = result
    if isinstance(result, (str, bytes)):
        try:
            data = json.loads(result)
        except (ValueError, TypeError):
            return False  # JSON corrupto: no se puede acreditar la lectura
    if not isinstance(data, dict):
        return False
    if data.get("error"):
        return False
    if data.get("not_found"):
        return False
    if data.get("success") is False:
        return False
    return True


def _post(event: dict, session_id, root=None):
    """post_tool_call de read_file|write_file|patch|edit_file: registra la huella.
    Registra SOLO si extra.status == 'ok' o si la clave no viene (payload legacy con
    'ok'; sin ninguna de las dos se asume exitoso). Con status 'error'|'cancelled'|'blocked'
    NUNCA registra: un patch bloqueado (status='blocked') dispara post_tool_call y no
    debe marcar la ruta como vista, o el reintento idéntico pasaría (ronda 2 / H1).
    - read_file (ronda 4 / TOCTOU): el pre dejó una entrada 'read_pending' con la
      huella capturada ANTES de la lectura; el post promueve ESA huella (lo que el
      agente vio). Sin pendiente (hook legacy sin pre, o pre sin sesión) se registra
      la huella de disco actual, como siempre: es el mismo comportamiento de antes,
      y el pre corre en toda instalación viva (el matcher del pre del diseño §3
      incluye read_file, ronda 5 / H1).
    - write_file (ronda 5 / H2): certifica por INTENCIÓN. Con tool_input['content']
      (str) reconstruye sha256(content) y lo compara con el sha256 del disco al
      llegar el post: solo si COINCIDEN registra la huella y ese sha256; si DIFIERE
      (otro proceso escribió entre la tool y el post) NO registra nada y anota
      'write_concurrent' en el ledger — fail-closed: mejor falso bloqueo que
      certificar contenido que el agente no escribió. Sin 'content' (payload
      legacy) conserva el comportamiento de antes (huella de disco). Si el disco
      supera DIGEST_CAP el digest no es computable: no se certifica (fail-closed).
    - patch/edit_file (ronda 5 / H2): SOLO registra si extra.result (JSON string
      del PatchResult, tools/file_operations_common.py) reporta success is True o
      verified is True; con success=false / error presente no registra (_result_certified).
      Ronda 7 (H-A/H-B): el contenido esperado se reconstruye desde tool_input
      sobre el snapshot EFÍMERO del pre (fuera del ledger, 0600/0700); si la
      reconstrucción/verificación no es posible NO registra nada y anota
      'write_unverifiable' (fail-closed real), y el fallback legacy queda solo
      para payloads sin pendiente. 'verified' (WriteResult) SOLO cubre que el
      disco coincidía con lo escrito AL TERMINAR la tool — la ventana entre la
      tool y este post la cubre la certificación por reconstrucción contra el
      snapshot del pre.
    - patch mode='patch' V4A (ronda 4 / H2): registra CADA ruta de las cabeceras
      '*** Update|Delete|Add File:' del texto con la huella posterior, igual que
      hace el pre al decidir; así dos V4A consecutivos no se bloquean.
    Cualquier otra tool no toca el ledger."""
    tool = event.get("tool_name")
    if tool not in RECORD_TOOLS:
        return 0, {}
    if not session_id:
        return 0, {}

    extra = event.get("extra")
    if isinstance(extra, dict):
        status = extra.get("status")
        if status is not None:
            # H1: el payload real trae status ('ok'|'error'|'cancelled'|'blocked').
            # Solo un resultado 'ok' vio/escribió contenido. Crítico para 'blocked':
            # un patch bloqueado dispara post_tool_call y NO debe marcar la ruta
            # como vista, o el reintento idéntico pasaría.
            if str(status).strip().lower() != "ok":
                return 0, {}
        elif "ok" in extra and not extra.get("ok"):
            return 0, {}  # payload legacy con ok=False
        # Sin 'status' ni 'ok': payload antiguo mínimo -> se asume exitoso (H1).

    tool_input = event.get("tool_input")
    if tool in EDIT_TOOLS and not _result_certified(event):
        # Ronda 5 / H2: el resultado estructurado reporta fallo (success=false,
        # error, verified=false o sin marca de éxito): la tool no escribió nada,
        # no registrar (refuerzo sobre el status). Cubre el patch con 'path' Y
        # el V4A (el gate va antes del dispatch).
        return 0, {}

    if (
        tool == "patch"
        and isinstance(tool_input, dict)
        and tool_input.get("mode") == "patch"
    ):
        # V4A (ronda 4 / H2): sin clave 'path', el registro sale de las
        # cabeceras del texto, igual que la decisión del pre.
        return _post_v4a(event, session_id, root, tool_input)

    resolved, issue = _resolve(event)
    if issue or not resolved or not os.path.exists(resolved):
        return 0, {}

    try:
        if tool == "read_file":
            # Ronda 9 / G2: validar el resultado REAL de la tool antes de
            # promover. El status 'ok' del runner no garantiza que la lectura
            # entregara contenido (extra.result puede traer error/not_found):
            # con resultado fallido o no verificable se DESCARTA la pendiente
            # (no promover, ni ahora ni en un empareje posterior) y no se
            # registra nada.
            if not _read_result_certified(event):
                state.pending_discard(
                    session_id, resolved, root=root, call_id=_call_id(event)
                )
                return 0, {}
            # Ronda 4 / TOCTOU-H1 + ronda 6 / B1: empareje de la pendiente por
            # call_id (extra.tool_call_id o derivado del payload, idéntico en
            # pre y post). Con VARIAS pendientes vivas del mismo path y sin
            # call_id útil NO se promueve ninguna huella (fail-closed: el post
            # de otra lectura intercalada no debe autorizar contenidos que esta
            # lectura no vio). Sin pendiente (hook legacy sin pre) se registra
            # la huella de disco actual como siempre.
            status, pending = state.pending_read_match(
                session_id, resolved, root=root, call_id=_call_id(event)
            )
            if status == "ambiguous":
                return 0, {}  # B1: fail-closed, nada que certificar
            if status == "match" and isinstance(pending, dict):
                mtime_ns = pending.get("mtime_ns")
                size = pending.get("size")
                if isinstance(mtime_ns, int) and isinstance(size, int):
                    state.record_seen(
                        session_id, tool, resolved, mtime_ns, size, root=root
                    )
                    return 0, {}
            state.record(session_id, tool, resolved, ok=True, root=root)
            return 0, {}
        if tool == "write_file":
            content = (
                tool_input.get("content")
                if isinstance(tool_input, dict)
                else None
            )
            if isinstance(content, str):
                # Ronda 5 / H2: certificar por intención — lo que el agente
                # quiso escribir debe ser EXACTAMENTE lo que hay en disco al
                # llegar el post; si no, la huella de disco certificaría un
                # contenido que el agente nunca escribió.
                intent_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
                disk_sha = state.file_digest(resolved)
                if disk_sha is None or intent_sha != disk_sha:
                    state.log_event(
                        session_id,
                        "write_concurrent",
                        root=root,
                        path=resolved,
                    )
                    return 0, {}
                mtime_ns, size = state.fingerprint(resolved)
                state.record_seen(
                    session_id, tool, resolved, mtime_ns, size,
                    root=root, sha256=intent_sha,
                )
                return 0, {}
            # payload legacy sin 'content': no hay intención que reconstruir;
            # comportamiento de antes (huella de disco).
        if tool in EDIT_TOOLS:
            # Ronda 6 / B2 (a) + ronda 7 / H-B: str_replace sobre el snapshot
            # efímero del pre (H-A). El post reconstruye el contenido ESPERADO
            # (old->new) y solo certifica si coincide con el disco al llegar el
            # post; en carrera NO registra ('write_concurrent', fail-closed).
            # Fail-closed REAL: con pendiente viva, si la reconstrucción no es
            # verificable (old/new ausentes o ajenos al snapshot, snapshot
            # ausente para ese path, pendiente ambigua o snapshot no escribible
            # en el pre) NO registra nada y anota 'write_unverifiable': el
            # fallback legacy (huella de disco) certificaba una versión
            # potencialmente ajena. El fallback legacy queda SOLO para payloads
            # SIN pendiente (post sin pre, imposible en producción).
            status, pending = state.pending_write_match(
                session_id, resolved, root=root, call_id=_call_id(event)
            )
            expected = None
            if status == "match" and isinstance(pending, dict):
                content = _pending_content(pending, root=root)
                if content is not None:
                    expected = _expected_after_replace(content, tool_input)
            if status == "none":
                # Sin pendiente: payload legacy sin pre — huella de disco,
                # comportamiento de antes (ronda 6 / B2).
                state.record(session_id, tool, resolved, ok=True, root=root)
                return 0, {}
            if expected is None:
                # Ronda 7 / H-B: fail-closed real (reconstrucción no
                # verificable con pendiente viva).
                state.log_event(
                    session_id,
                    "write_unverifiable",
                    root=root,
                    tool=str(tool),
                    path=resolved,
                )
                return 0, {}
            _certify_against_snapshot(session_id, tool, resolved, expected, root=root)
            return 0, {}
        # write_file legacy sin 'content' (y write_file con content solo llega
        # hasta aquí si certificó arriba): huella de disco, comportamiento de
        # antes (ronda 5 / H2, payload legacy).
        state.record(session_id, tool, resolved, ok=True, root=root)
    except Exception as exc:  # CA10: fail-open también al registrar
        _log_error(session_id, root, exc)
    return 0, {}


def handle(event, root=None):
    """Punto de entrada del hook. event = dict del contrato shell_hooks.
    Devuelve (exit_code, payload). Nunca lanza: ante error interno -> (0, {} + log)."""
    try:
        if not isinstance(event, dict):
            return 0, {}

        if state.disabled(root):  # CA9: kill switch, permite todo
            sid = str(event.get("session_id") or "unknown")
            # L1: 'disabled' una vez por SESIÓN, no por proceso. Los hooks son
            # one-shot: la memoria del proceso (_disabled_logged) no basta, se
            # consulta el ledger bajo LOCK_SH antes de escribir.
            if sid not in _disabled_logged and not state.has_event(sid, "disabled", root=root):
                _disabled_logged.add(sid)
                state.log_event(sid, "disabled", root=root)
            return 0, {}

        event_name = event.get("hook_event_name")
        session_id = event.get("session_id") or None
        if event_name == "pre_tool_call":
            return _pre(event, session_id, root)
        if event_name == "post_tool_call":
            return _post(event, session_id, root)
        return 0, {}
    except Exception as exc:  # CA10: el guard jamás tumba la edición
        try:
            _log_error(
                (event or {}).get("session_id") if isinstance(event, dict) else None,
                root,
                exc,
            )
        except Exception:
            pass
        return 0, {}


def main() -> int:
    """Lee el evento por stdin, imprime el payload JSON (si lo hay) y devuelve el
    exit code. Cualquier error -> exit 0 + línea {'ev':'error'} en el ledger si se puede."""
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw and raw.strip() else {}
        if not isinstance(event, dict):
            event = {}
        code, payload = handle(event)
    except Exception as exc:
        try:
            state.log_event(None, "error", error="%s: %s" % (type(exc).__name__, exc))
        except Exception:
            pass
        code, payload = 0, {}
    if payload:
        try:
            print(json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass
    return code


if __name__ == "__main__":
    sys.exit(main())
