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
- post_tool_call (read_file|write_file|patch|edit_file): registra la huella actual.
  Cualquier otra tool no toca el ledger.

Modos (CA7/CA8): env READ_BEFORE_PATCH_MODE=shadow|enforce o archivo MODE junto al
ledger; default shadow. En shadow: exit 0 siempre, {"ev":"would_block"} en el ledger,
payload sin 'decision':'block'. Kill switch: archivo DISABLED -> permite todo (CA9).

Uso: python3 guard_read_before_patch.py < event.json   (main() -> exit code)
"""

import json
import os
import sys

import read_before_patch_state as state

EDIT_TOOLS = {"patch", "edit_file"}
RECORD_TOOLS = {"read_file", "write_file", "patch", "edit_file"}

_disabled_logged = set()  # "lo registra una vez" (CA9): por sesión y proceso


def _resolve(event: dict) -> str:
    """Ruta real contra la que comparar: realpath(join(cwd del payload, path))."""
    tool_input = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    raw = tool_input.get("path") if isinstance(tool_input, dict) else None
    if not isinstance(raw, str) or not raw:
        return ""
    cwd = event.get("cwd") or os.getcwd()
    try:
        return os.path.realpath(os.path.join(str(cwd), raw))
    except Exception:
        return os.path.realpath(raw)


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


def _pre(event: dict, session_id, root=None):
    tool = event.get("tool_name")
    if tool not in EDIT_TOOLS:
        return 0, {}

    resolved = _resolve(event)
    if not resolved:
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


def _post(event: dict, session_id, root=None):
    tool = event.get("tool_name")
    if tool not in RECORD_TOOLS:
        return 0, {}
    if not session_id:
        return 0, {}

    extra = event.get("extra")
    ok = bool(extra.get("ok", True)) if isinstance(extra, dict) else True
    if not ok:
        return 0, {}  # solo lecturas/escrituras exitosas marcan la ruta como vista

    resolved = _resolve(event)
    if not resolved or not os.path.exists(resolved):
        return 0, {}

    try:
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
            if sid not in _disabled_logged:
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
