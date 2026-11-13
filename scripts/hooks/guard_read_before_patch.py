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
    """post_tool_call de patch V4A con resultado ok (ronda 4 / H2): registra CADA
    ruta de las cabeceras '*** Update|Delete|Add File:' con la huella posterior.
    Mismo parsing y resolución que el pre (_pre_v4a), para que dos V4A
    consecutivos no se bloqueen y un parche multi-archivo registre todas sus
    rutas. Solo se llega aquí tras validar status=='ok' en _post, así que un
    patch V4A bloqueado no registra nada."""
    patch_text = (tool_input or {}).get("patch")
    ops = _v4a_file_ops(patch_text) if isinstance(patch_text, str) else []
    if not ops:
        return 0, {}
    cwd = event.get("cwd")
    has_cwd = isinstance(cwd, str) and bool(cwd.strip())
    for _action, raw_path in ops:
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
            state.record(session_id, "patch", resolved, ok=True, root=root)
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
      NOTA (docstring exigida): el contenido INTENCIONADO de un Update V4A no es
      reconstruible localmente (el guard solo ve el texto del parche, no el
      resultado por archivo), así que para V4A la certificación se limita al éxito
      reportado más la huella de disco observada; y 'verified' (WriteResult) SOLO
      cubre que el disco coincidía con lo escrito AL TERMINAR la tool — no protege
      contra escrituras posteriores entre la tool y este post (para eso está la
      certificación por intención de write_file; para patch/edit_file la ventana
      queda cubierta por el desempate por digest en el pre).
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
            # Ronda 4 / TOCTOU-H1: promueve la huella pendiente del PRE (lo que
            # el agente vio), no la de disco al llegar el post. Sin pendiente
            # (hook legacy sin pre, o pre sin sesión/cwd) se registra la huella
            # de disco actual como siempre: prefiero el mismo comportamiento
            # de antes a dejar de registrar lecturas legítimas.
            pending = state.pending_read(session_id, resolved, root=root)
            if pending is not None:
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
