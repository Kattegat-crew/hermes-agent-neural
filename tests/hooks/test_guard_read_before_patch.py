"""Suite RED del guard `read-before-patch` (contrato, sin red, sin tocar el ledger real).

Spec:  .specs/read-before-patch-guard/01-spec.md  (criterios CA1-CA11)
Design: .specs/read-before-patch-guard/02-design.md

Contrato asumido (negociado con la implementación, NO se cambia desde los tests):

    scripts/hooks/read_before_patch_state.py
        ledger_path(session_id: str, root: Path | None = None) -> Path
        fingerprint(path: Path) -> tuple[int, int]        # (st_mtime_ns, st_size)
        record(session_id: str, tool: str, path: str, ok: bool = True,
               root: Path | None = None) -> None
        last_seen(session_id: str, path: str, root: Path | None = None) -> dict | None
            # {'path', 'mtime_ns', 'size', 'tool', 't'}
        mode(root: Path | None = None) -> str             # 'shadow' | 'enforce'
        disabled(root: Path | None = None) -> bool

    scripts/hooks/guard_read_before_patch.py
        handle(event: dict, root: Path | None = None) -> tuple[int, dict]
        main() -> int

`root` parametriza el directorio de estado para que ningún test toque
/opt/hermes-agent-data/state/hooks.

CA11 (replay): la implementación aún no fija la firma del reporte; este test asume el
contrato mínimo `read_before_patch_report.report(events: list[dict]) -> dict` con las
llaves `patch_total`, `would_block`, `would_block_pct` y `path_form_suspects` del diseño
(§2.5), y acepta los nombres alternativos `build_report` / `replay`. Si el implementador
elige otra superficie (p. ej. CLI sobre state.db), este test se ajusta al aterrizar el
módulo — la intención (contar bloqueos y falsos positivos por forma de ruta) no cambia.

Los tests NO usan pytest.importorskip: si falta la implementación deben FALLAR.
"""

import importlib
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOKS_SRC = REPO / "scripts" / "hooks"

SESSION = "sess-guard-test"


# ── carga de módulos (RED: fallar, no skipear, si falta la implementación) ──


def _import_hook_module(name: str):
    """Importa un módulo del hook desde scripts/hooks/.

    Falla con mensaje explícito si el archivo no existe todavía (suite RED).
    """
    if str(HOOKS_SRC) not in sys.path:
        sys.path.insert(0, str(HOOKS_SRC))
    module_file = HOOKS_SRC / f"{name}.py"
    if not module_file.is_file():
        pytest.fail(
            f"implementación ausente: {module_file} — la suite RED exige que el "
            "módulo exista para pasar; no se skipea"
        )
    importlib.invalidate_caches()
    return importlib.import_module(name)


def load_modules() -> SimpleNamespace:
    """Carga los módulos del hook; se llama desde el cuerpo de cada test para que la
    ausencia de implementación se reporte como FAILED (no como ERROR de fixture)."""
    return SimpleNamespace(
        state=_import_hook_module("read_before_patch_state"),
        guard=_import_hook_module("guard_read_before_patch"),
        report=_import_hook_module("read_before_patch_report"),
    )


@pytest.fixture
def state_root(tmp_path: Path) -> Path:
    """Directorio de estado del ledger, aislado por test (nunca el real)."""
    root = tmp_path / "rbp-state"
    root.mkdir()
    return root


@pytest.fixture
def enforce(monkeypatch):
    """Modo enforce vía env, sin archivo MODE que pueda ensuciar la decisión."""
    monkeypatch.delenv("READ_BEFORE_PATCH_MODE", raising=False)
    monkeypatch.setenv("READ_BEFORE_PATCH_MODE", "enforce")


# ── helpers ──


def make_event(event_name: str, tool: str, path, cwd, session: str = SESSION) -> dict:
    """Evento JSON del hook según el contrato de shell_hooks.py."""
    return {
        "hook_event_name": event_name,
        "tool_name": tool,
        "tool_input": {"path": str(path)},
        "session_id": session,
        "cwd": str(cwd),
    }


def ledger_events(mods, state_root: Path, session: str = SESSION) -> list[dict]:
    """Lee el ledger del test tolerando líneas corruptas (el hook también debe tolerarlas)."""
    ledger = mods.state.ledger_path(session, state_root)
    if not ledger.exists():
        return []
    events = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def has_event(events: list[dict], ev: str) -> bool:
    return any(e.get("ev") == ev for e in events)


# ── CA1 ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("tool", ["patch", "edit_file"])
def test_ca1_block_existing_file_without_prior_read(state_root, enforce, tmp_path, tool):
    mods = load_modules()
    """CA1: patch/edit_file sobre archivo existente sin lectura previa ⇒ exit 2,
    payload {'decision': 'block'} y reason con la ruta y el read_file exacto a ejecutar."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    code, payload = mods.guard.handle(
        make_event("pre_tool_call", tool, target, tmp_path), root=state_root
    )

    assert code == 2
    assert payload["decision"] == "block"
    reason = payload["reason"]
    assert str(target) in reason
    assert "read_file" in reason


# ── CA2 ──────────────────────────────────────────────────────────────────────


def test_ca2_patch_allowed_after_read_file_with_matching_fingerprint(state_root, enforce, tmp_path):
    mods = load_modules()
    """CA2: patch tras read_file registrado y sin cambios en disco ⇒ permitido (exit 0)."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")
    mods.state.record(SESSION, "read_file", str(target), root=state_root)

    code, payload = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )

    assert code == 0
    assert payload.get("decision") != "block"


# ── CA3 ──────────────────────────────────────────────────────────────────────


def test_ca3_patch_blocked_when_file_changed_on_disk_after_read(state_root, enforce, tmp_path):
    mods = load_modules()
    """CA3: patch tras read_file pero el archivo cambió en disco (otro proceso) ⇒ exit 2."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")
    mods.state.record(SESSION, "read_file", str(target), root=state_root)
    target.write_text("value = 2\n", encoding="utf-8")  # cambio de contenido => size y mtime

    code, payload = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )

    assert code == 2
    assert payload["decision"] == "block"


def test_ca3b_patch_blocked_on_mtime_only_change_after_read(state_root, enforce, tmp_path):
    mods = load_modules()
    """CA3 (variante huella): solo cambia mtime_ns (mismo size) ⇒ también bloqueado,
    porque la huella es (st_mtime_ns, st_size)."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")
    mods.state.record(SESSION, "read_file", str(target), root=state_root)
    st = target.stat()
    os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))

    code, _payload = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )

    assert code == 2


# ── CA4 ──────────────────────────────────────────────────────────────────────


def test_ca4_patch_allowed_after_own_write_file_record(state_root, enforce, tmp_path):
    mods = load_modules()
    """CA4: patch tras write_file propio registrado (sin cambios posteriores) ⇒ exit 0."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")
    mods.state.record(SESSION, "write_file", str(target), root=state_root)

    code, payload = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )

    assert code == 0
    assert payload.get("decision") != "block"


# ── CA5 ──────────────────────────────────────────────────────────────────────


def test_ca5_nonexistent_path_allowed(state_root, enforce, tmp_path):
    mods = load_modules()
    """CA5: patch sobre ruta inexistente ⇒ exit 0 (la herramienta reportará su error)."""
    missing = tmp_path / "no_existe.py"

    code, payload = mods.guard.handle(
        make_event("pre_tool_call", "patch", missing, tmp_path), root=state_root
    )

    assert code == 0
    assert payload.get("decision") != "block"


# ── CA6 ──────────────────────────────────────────────────────────────────────


def test_ca6_relative_path_resolved_against_cwd_and_symlink_matches_realpath(
    state_root, enforce, tmp_path
):
    """CA6: la ruta relativa se resuelve contra event['cwd'] y el symlink coincide
    con su ruta real (realpath): leer por una forma y editar por otra no bloquea."""
    mods = load_modules()
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")
    link = tmp_path / "link.py"
    link.symlink_to(target)
    mods.state.record(SESSION, "read_file", str(target), root=state_root)  # forma real

    # relativa contra cwd, registrada como absoluta
    code_rel, payload_rel = mods.guard.handle(
        make_event("pre_tool_call", "patch", "app.py", tmp_path), root=state_root
    )
    # symlink absoluto, registrado como ruta real
    code_link, payload_link = mods.guard.handle(
        make_event("pre_tool_call", "patch", link, tmp_path), root=state_root
    )

    assert code_rel == 0, payload_rel
    assert code_link == 0, payload_link


# ── CA7 ──────────────────────────────────────────────────────────────────────


def test_ca7_shadow_mode_does_not_block_and_records_would_block(state_root, monkeypatch, tmp_path):
    """CA7: modo shadow (archivo MODE='shadow') no bloquea (exit 0, sin decision:block)
    y deja en el ledger un evento would_block de lo que habría bloqueado."""
    mods = load_modules()
    monkeypatch.delenv("READ_BEFORE_PATCH_MODE", raising=False)
    (state_root / "MODE").write_text("shadow\n", encoding="utf-8")
    assert mods.state.mode(state_root) == "shadow"

    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    code, payload = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )

    assert code == 0
    assert payload.get("decision") != "block"
    assert has_event(ledger_events(mods, state_root), "would_block")


def test_ca7b_shadow_mode_via_env_var_reads_before_patch_mode(state_root, monkeypatch, tmp_path):
    """CA7 (variante): el modo también se controla con READ_BEFORE_PATCH_MODE=shadow
    (monkeypatch.setenv, sin variables globales sucias) ⇒ mismo comportamiento."""
    mods = load_modules()
    monkeypatch.setenv("READ_BEFORE_PATCH_MODE", "shadow")
    assert mods.state.mode(state_root) == "shadow"

    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    code, payload = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )

    assert code == 0
    assert payload.get("decision") != "block"
    assert has_event(ledger_events(mods, state_root), "would_block")


# ── CA8 ──────────────────────────────────────────────────────────────────────


def test_ca8_enforce_mode_blocks(state_root, monkeypatch, tmp_path):
    mods = load_modules()
    """CA8: modo enforce (archivo MODE='enforce', sin env) bloquea según CA1-CA6 ⇒ exit 2."""
    monkeypatch.delenv("READ_BEFORE_PATCH_MODE", raising=False)
    (state_root / "MODE").write_text("enforce\n", encoding="utf-8")
    assert mods.state.mode(state_root) == "enforce"

    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    code, payload = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )

    assert code == 2
    assert payload["decision"] == "block"


# ── CA9 ──────────────────────────────────────────────────────────────────────


def test_ca9_disabled_kill_switch_allows_everything(state_root, monkeypatch, tmp_path):
    mods = load_modules()
    """CA9: kill switch — un archivo DISABLED en el directorio de estado hace que el hook
    permita todo (aun en enforce y sin lectura previa) y state.disabled() lo refleje."""
    monkeypatch.delenv("READ_BEFORE_PATCH_MODE", raising=False)
    (state_root / "MODE").write_text("enforce\n", encoding="utf-8")
    (state_root / "DISABLED").write_text("", encoding="utf-8")
    assert mods.state.disabled(state_root) is True

    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    code, payload = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )

    assert code == 0
    assert payload.get("decision") != "block"


# ── CA10 ─────────────────────────────────────────────────────────────────────


def test_ca10_internal_exception_never_blocks_and_logs_error(state_root, monkeypatch, enforce, tmp_path):
    mods = load_modules()
    """CA10: una excepción interna del hook jamás tumba la edición (exit 0, sin block)
    y queda registrada en el ledger como evento 'error' (fail_closed: false)."""

    def _boom(*args, **kwargs):
        raise RuntimeError("falla interna simulada")

    # El guard puede acceder a last_seen como atributo del módulo o importándolo
    # directamente; se cubren las dos formas.
    monkeypatch.setattr(mods.state, "last_seen", _boom)
    if hasattr(mods.guard, "last_seen"):
        monkeypatch.setattr(mods.guard, "last_seen", _boom)

    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    code, payload = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )

    assert code == 0
    assert payload.get("decision") != "block"
    assert has_event(ledger_events(mods, state_root), "error")


# ── CA11 ─────────────────────────────────────────────────────────────────────


def _report_callable(module):
    """Superficie mínima asumida para el replay (ver docstring del módulo)."""
    for name in ("report", "build_report", "replay"):
        fn = getattr(module, name, None)
        if callable(fn):
            return fn
    pytest.fail(
        "read_before_patch_report no expone report()/build_report()/replay() — "
        "ajustar este test cuando el módulo de replay aterrice"
    )


def test_ca11_replay_report_counts_would_block_and_path_form_suspects():
    mods = load_modules()
    """CA11: el replay sobre una secuencia reconstruida con las mismas reglas reporta
    cuántos patch habría bloqueado (would_block) y cuántos son sospechosos de falso
    positivo por forma de ruta (path_form_suspects), junto a patch_total/pct."""
    events = [
        # s1: lee /a/x.py y luego patchea la misma ruta → permitido
        {"session_id": "s1", "tool": "read_file", "path": "/a/x.py", "ok": True},
        {"session_id": "s1", "tool": "patch", "path": "/a/x.py", "ok": True},
        # s1: patchea /a/y.py que nunca fue leído ni escrito → would_block
        {"session_id": "s1", "tool": "patch", "path": "/a/y.py", "ok": True},
        # s2: lee y patchea la misma ruta escrita con dos formas distintas
        # (./z.py vs z.py) → mismo archivo; falso positivo por forma de ruta
        {"session_id": "s2", "tool": "read_file", "path": "/b/./z.py", "ok": True},
        {"session_id": "s2", "tool": "patch", "path": "/b/z.py", "ok": True},
    ]

    report = _report_callable(mods.report)(events)

    assert report["patch_total"] == 3
    assert report["would_block"] == 1
    assert report["would_block_pct"] == pytest.approx(100 / 3)
    assert len(report["path_form_suspects"]) == 1


# ── contrato de registro (post_tool_call) y ledger ───────────────────────────


def test_post_tool_call_records_fingerprint_for_editing_tools_and_ignores_others(
    state_root, tmp_path
):
    """post_tool_call de read_file/write_file/patch registra la huella actual del path;
    cualquier otra tool no registra nada en el ledger."""
    mods = load_modules()
    for tool in ("read_file", "write_file", "patch"):
        session = f"{SESSION}-{tool}"
        target = tmp_path / f"{tool}.py"
        target.write_text(f"# {tool}\n", encoding="utf-8")

        code, _payload = mods.guard.handle(
            make_event("post_tool_call", tool, target, tmp_path, session=session),
            root=state_root,
        )

        assert code == 0
        seen = mods.state.last_seen(session, str(target), root=state_root)
        assert seen is not None, f"{tool} debió registrar huella en el ledger"
        st = target.stat()
        assert seen["mtime_ns"] == st.st_mtime_ns
        assert seen["size"] == st.st_size

    # tool ajena a la edición: nada registrado
    other_session = f"{SESSION}-other"
    mods.guard.handle(
        make_event("post_tool_call", "terminal", tmp_path / "x.py", tmp_path,
                   session=other_session),
        root=state_root,
    )
    assert mods.state.last_seen(other_session, str(tmp_path / "x.py"), root=state_root) is None
    assert ledger_events(mods, state_root, session=other_session) == []


def test_state_module_record_and_last_seen_roundtrip(state_root, tmp_path):
    mods = load_modules()
    """Contrato del ledger: record() escribe y last_seen() devuelve la última entrada por
    path con la huella (mtime_ns, size) actual; fingerprint() coincide con el stat."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    assert mods.state.last_seen(SESSION, str(target), root=state_root) is None

    mods.state.record(SESSION, "read_file", str(target), root=state_root)
    seen = mods.state.last_seen(SESSION, str(target), root=state_root)
    st = target.stat()
    assert seen["path"] == str(target)
    assert seen["mtime_ns"] == st.st_mtime_ns
    assert seen["size"] == st.st_size
    assert seen["tool"] == "read_file"
    assert "t" in seen

    # la última entrada por path gana
    mods.state.record(SESSION, "write_file", str(target), root=state_root)
    assert mods.state.last_seen(SESSION, str(target), root=state_root)["tool"] == "write_file"

    assert mods.state.fingerprint(target) == (st.st_mtime_ns, st.st_size)


# ══════════════════════════════════════════════════════════════════════════════
#  Hallazgos de revisores — ronda RED 2
#  (payload status real, flock de lectura, poda oportunista, kill switch entre
#   procesos, cwd vacío, patch sin path, replay sobre state.db)
# ══════════════════════════════════════════════════════════════════════════════


def make_post_event(tool: str, path, cwd, status=None, session: str = SESSION, extra=None) -> dict:
    """Evento post_tool_call con el payload REAL de outcome (agent/tool_executor.py
    emit_post → shell_hooks _payload_fields): los kwargs de resultado aterrizan bajo
    ``extra`` como {'status': 'ok'|'error'|'cancelled'|'blocked', 'error_type',
    'error_message', 'duration_ms'} — SIN clave 'ok'."""
    ev = make_event("post_tool_call", tool, path, cwd, session=session)
    payload: dict = {"duration_ms": 5}
    if status is not None:
        payload["status"] = status
        if status != "ok":
            payload["error_type"] = "simulated"
            payload["error_message"] = "fallo simulado por el test"
    if extra:
        payload.update(extra)
    ev["extra"] = payload
    return ev


# ── H1: el payload real de post_tool_call trae 'status', no 'ok' ─────────────


def test_h1_post_read_file_status_error_does_not_record_and_next_patch_blocks(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """H1: post_tool_call de read_file con status='error' NO registró nada (la lectura
    falló): la ruta no queda como vista y el patch siguiente se bloquea (exit 2)."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    code, _payload = mods.guard.handle(
        make_post_event("read_file", target, tmp_path, status="error"), root=state_root
    )
    assert code == 0
    assert mods.state.last_seen(SESSION, str(target), root=state_root) is None, (
        "un read_file con status='error' no vio contenido: no debe registrar la ruta"
    )

    code2, payload2 = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )
    assert code2 == 2, "el patch tras una lectura fallida debe bloquearse"
    assert payload2["decision"] == "block"


def test_h1_post_read_file_status_cancelled_does_not_record(state_root, tmp_path):
    mods = load_modules()
    """H1: post_tool_call de read_file con status='cancelled' (KeyboardInterrupt a mitad
    de la tool) tampoco vio el contenido: NO registra la ruta."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    code, _payload = mods.guard.handle(
        make_post_event("read_file", target, tmp_path, status="cancelled"), root=state_root
    )
    assert code == 0
    assert mods.state.last_seen(SESSION, str(target), root=state_root) is None, (
        "un read_file cancelado no debe registrar la ruta como vista"
    )


def test_h1_post_read_file_status_ok_records_fingerprint(state_root, tmp_path):
    mods = load_modules()
    """H1: post_tool_call de read_file con status='ok' (payload real, sin clave 'ok')
    SÍ registra la huella actual del archivo."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    code, _payload = mods.guard.handle(
        make_post_event("read_file", target, tmp_path, status="ok"), root=state_root
    )
    assert code == 0
    seen = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert seen is not None, "status='ok' debe registrar la ruta como vista"
    st = target.stat()
    assert (seen["mtime_ns"], seen["size"]) == (st.st_mtime_ns, st.st_size)


def test_h1_post_patch_status_blocked_does_not_record_path_and_retry_still_blocks(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """H1 (el bypass): un patch BLOQUEADO por el guard dispara igual su post_tool_call
    con status='blocked'; como la edición nunca ocurrió, NO debe registrar la ruta como
    vista — si la registrara, el reintento del patch pasaría sin read_file previo."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    code, _payload = mods.guard.handle(
        make_post_event("patch", target, tmp_path, status="blocked"), root=state_root
    )
    assert code == 0
    assert mods.state.last_seen(SESSION, str(target), root=state_root) is None, (
        "un patch con status='blocked' no escribió nada: no debe marcarse la ruta"
    )

    code2, payload2 = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )
    assert code2 == 2, "el reintento sin read_file previo debe seguir bloqueado"
    assert payload2["decision"] == "block"


def test_h1_post_without_status_key_legacy_ok_false_does_not_record(state_root, tmp_path):
    mods = load_modules()
    """H1 (payload viejo, contrato explícito): un evento legacy sin 'status' pero con la
    clave antigua extra={'ok': False} se respeta: NO registra la ruta."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    code, _payload = mods.guard.handle(
        make_post_event("read_file", target, tmp_path, extra={"ok": False}), root=state_root
    )
    assert code == 0
    assert mods.state.last_seen(SESSION, str(target), root=state_root) is None, (
        "payload legacy con ok=False: la ruta no debe quedar como vista"
    )


def test_h1_post_without_status_or_ok_defaults_to_recorded(state_root, tmp_path):
    mods = load_modules()
    """H1 (payload viejo, contrato explícito): un evento sin 'status' ni 'ok' (payload
    mínimo antiguo) se asume exitoso por defecto y SÍ registra la ruta."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    ev = make_post_event("read_file", target, tmp_path)
    ev["extra"] = {}  # sin ninguna marca de outcome
    code, _payload = mods.guard.handle(ev, root=state_root)
    assert code == 0
    assert mods.state.last_seen(SESSION, str(target), root=state_root) is not None, (
        "sin 'status' ni 'ok' el default explícito es tratarlo como exitoso y registrar"
    )


# ── H2: last_seen debe leer bajo flock compartido (LOCK_SH) ──────────────────


def test_h2_last_seen_reads_under_shared_flock_lock_sh(state_root, monkeypatch, tmp_path):
    mods = load_modules()
    """H2: last_seen() debe tomar el ledger con flock COMPARTIDO (LOCK_SH), nunca sin
    lock: un record() concurrente no debe poder dejarlo leyendo un estado a medias."""
    import fcntl as fcntl_mod

    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")
    mods.state.record(SESSION, "read_file", str(target), root=state_root)

    ops = []
    real_flock = mods.state.fcntl.flock

    def spy(fd, operation, *args, **kwargs):
        ops.append(operation)
        return real_flock(fd, operation, *args, **kwargs)

    monkeypatch.setattr(mods.state.fcntl, "flock", spy)

    seen = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert seen is not None
    assert fcntl_mod.LOCK_SH in ops, (
        "last_seen debe tomar flock compartido (LOCK_SH) sobre el ledger; "
        "operaciones observadas: %r" % (ops,)
    )


def test_h2_concurrent_record_writer_and_20_last_seen_readers_never_miss_existing_entry(
    state_root, tmp_path
):
    mods = load_modules()
    """H2 (carrera lectura/poda): un writer hace record() en bucle mientras 20 last_seen()
    leen. Ninguna lectura debe devolver None cuando la entrada ya existía. El patrón se
    repite 3 veces y se exigen 0 fallos (sin flakiness); deadline total de 60s y join
    con timeout de 30s por hilo."""
    target = tmp_path / "race.py"
    target.write_text("value = 1\n", encoding="utf-8")
    REPEATS, READERS = 3, 20
    misses = []
    overall_deadline = time.monotonic() + 60.0

    for rep in range(REPEATS):
        session = "%s-h2-%d" % (SESSION, rep)
        # la entrada YA existe antes de que arranquen los lectores
        mods.state.record(session, "read_file", str(target), root=state_root)

        stop = threading.Event()
        results = [None] * READERS

        def _writer():
            n = 0
            while not stop.is_set() and n < 400:
                mods.state.record(session, "write_file", str(target), root=state_root)
                n += 1

        def _reader(i):
            results[i] = mods.state.last_seen(session, str(target), root=state_root)

        wt = threading.Thread(target=_writer)
        rts = [threading.Thread(target=_reader, args=(i,)) for i in range(READERS)]
        wt.start()
        for t in rts:
            t.start()
        for t in rts:
            t.join(timeout=30)
        stop.set()
        wt.join(timeout=30)
        alive = [t for t in rts + [wt] if t.is_alive()]
        assert not alive, "lectores/escritor no terminaron a tiempo (timeout 30s)"
        assert time.monotonic() < overall_deadline, "el patrón de carrera excedió el deadline de 60s"
        misses.extend((rep, i) for i, r in enumerate(results) if r is None)

    assert misses == [], (
        "last_seen devolvió None con la entrada ya existente en %d lectura(s): %r"
        % (len(misses), misses)
    )


# ── H3: la poda no debe correr en cada invocación ────────────────────────────


def test_h3_record_with_fresh_process_and_small_recent_ledger_does_not_rewrite_file(
    state_root, tmp_path
):
    mods = load_modules()
    """H3: la poda oportunista no debe correr en cada invocación del hook (cada hook es
    un proceso de un solo uso, así que un contador en memoria la dispara SIEMPRE). Se
    simula un proceso fresco (reload del módulo de estado, que reinicia su contador) y
    record() sobre un ledger de 10 líneas con mtime reciente NO debe reescribir el
    archivo. Marcador observable: una línea corrupta sembrada a propósito sobrevive a un
    append puro pero la poda la descarta al reescribir; el mtime_ns cambia por el append
    en ambos casos, así que el contenido (y no solo el mtime) es el discriminante."""
    session = "%s-h3" % SESSION
    ledger = mods.state.ledger_path(session, state_root)
    for i in range(10):
        target = tmp_path / ("f%d.py" % i)
        target.write_text("value = %d\n" % i, encoding="utf-8")
        mods.state.record(session, "read_file", str(target), root=state_root)
    corrupt = "{linea corrupta deliberada\n"
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(corrupt)
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 11

    mtime_before = ledger.stat().st_mtime_ns
    # HX013: sin time.sleep — el mtime del ledger se atrasa 60 s (bien bajo el
    # umbral de poda PRUNE_IDLE_S=3600) para que el append posterior tenga un
    # mtime estrictamente mayor de forma determinista, sin esperar el reloj.
    past_ns = mtime_before - 60_000_000_000  # 60 s atrás
    os.utime(ledger, ns=(past_ns, past_ns))
    mtime_before = ledger.stat().st_mtime_ns
    saved_appends = getattr(mods.state, "_appends", 0)
    try:
        fresh = importlib.reload(mods.state)  # proceso de hook fresco: contador a 0
        new_target = tmp_path / "f_new.py"
        new_target.write_text("value = new\n", encoding="utf-8")
        fresh.record(session, "read_file", str(new_target), root=state_root)
    finally:
        mods.state._appends = saved_appends

    mtime_after = ledger.stat().st_mtime_ns
    assert mtime_after > mtime_before, "record() debió hacer append de la nueva entrada"
    lines_after = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines_after) == 12 and corrupt.rstrip("\n") in lines_after, (
        "record() sobre un ledger de 10 líneas recientes no debe reescribirlo (la poda "
        "oportunista reescribe y descarta la línea corrupta); líneas: %r" % (lines_after,)
    )
    valid = 0
    for line in lines_after:
        try:
            if json.loads(line).get("ev") == "post_tool_call":
                valid += 1
        except (json.JSONDecodeError, ValueError):
            continue
    assert valid == 11, "las 10 entradas originales + la nueva deben seguir intactas"


# ── L1: el kill switch deja UNA línea 'disabled' entre procesos ──────────────


def test_l1_kill_switch_logs_disabled_once_across_separate_processes(state_root, tmp_path):
    mods = load_modules()
    """L1: con DISABLED presente, dos invocaciones en PROCESOS SEPARADOS (el caso real:
    cada hook es un proceso nuevo, el set en memoria no cruza procesos) deben dejar UNA
    sola línea 'disabled' en el ledger, no dos."""
    (state_root / "DISABLED").write_text("", encoding="utf-8")
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    child = tmp_path / "guard_child.py"
    child.write_text(
        "import json, sys\n"
        "sys.path.insert(0, %r)\n"
        "import guard_read_before_patch as guard\n"
        "event = json.load(sys.stdin)\n"
        "code, payload = guard.handle(event, root=%r)\n"
        "print(json.dumps({'code': code, 'payload': payload}))\n"
        % (str(HOOKS_SRC), str(state_root)),
        encoding="utf-8",
    )
    session = "%s-l1" % SESSION
    event = make_event("pre_tool_call", "patch", target, tmp_path, session=session)

    for _ in range(2):
        proc = subprocess.run(
            [sys.executable, str(child)],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, proc.stderr
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        assert out["code"] == 0, out
        assert out["payload"].get("decision") != "block"

    disabled_lines = [
        e for e in ledger_events(mods, state_root, session=session) if e.get("ev") == "disabled"
    ]
    assert len(disabled_lines) == 1, (
        "con DISABLED, N invocaciones en procesos separados deben dejar UNA sola línea "
        "'disabled' en el ledger, no %d" % len(disabled_lines)
    )


# ── L2: evento sin 'cwd' y path relativo ─────────────────────────────────────


@pytest.mark.parametrize("cwd_variant", ["missing", "empty"])
def test_l2_relative_path_without_cwd_records_unknown_cwd_and_allows(
    state_root, enforce, monkeypatch, tmp_path, cwd_variant
):
    mods = load_modules()
    """L2: un evento sin 'cwd' (o con cwd vacío) y path relativo NUNCA debe resolverse
    contra el cwd del proceso: el guard permite y deja evento 'unknown_cwd' en el ledger.
    El chdir al tmp coloca el archivo exactamente donde un resolver buggy lo encontraría
    y bloquearía."""
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    ev = make_event("pre_tool_call", "patch", "app.py", tmp_path)
    if cwd_variant == "missing":
        ev.pop("cwd")
    else:
        ev["cwd"] = ""

    code, payload = mods.guard.handle(ev, root=state_root)

    assert code == 0, payload
    assert payload.get("decision") != "block"
    unknown = [e for e in ledger_events(mods, state_root) if e.get("ev") == "unknown_cwd"]
    assert unknown, (
        "el guard debe dejar evento 'unknown_cwd' en el ledger y permitir; "
        "jamás resolver la ruta relativa contra el cwd del proceso"
    )


# ── L3: patch sin clave 'path' ───────────────────────────────────────────────


def test_l3_patch_without_path_key_allows_but_leaves_no_path_event(state_root, enforce, tmp_path):
    mods = load_modules()
    """L3: patch/edit_file sin clave 'path' en tool_input: permite (exit 0) pero deja
    evento 'no_path' en el ledger — nada de allow silencioso."""
    ev = make_event("pre_tool_call", "patch", tmp_path / "x.py", tmp_path)
    ev["tool_input"] = {}  # sin 'path'

    code, payload = mods.guard.handle(ev, root=state_root)

    assert code == 0
    assert payload.get("decision") != "block"
    assert has_event(ledger_events(mods, state_root), "no_path"), (
        "un patch sin 'path' debe dejar evento 'no_path' en el ledger"
    )


# ── CA11 (regresión del replay): conteos contra una state.db temporal ────────


def test_ca11_replay_over_sqlite_db_treats_prior_write_and_own_patch_as_seen(tmp_path):
    mods = load_modules()
    """CA11: ejecutar el replay de read_before_patch_report.py contra una DB sqlite
    temporal (tabla messages con tool_calls JSON) y verificar patch_total, would_block y
    sessions_affected. El replay debe aplicar la MISMA regla que el guard: una escritura
    previa cuenta como 'visto' — incluida la del propio patch/edit_file exitoso."""
    db = tmp_path / "state.db"
    con = sqlite3.connect(str(db))
    try:
        con.execute(
            "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "session_id TEXT, active INTEGER, tool_calls TEXT)"
        )

        def _call(name, path):
            return {"function": {"name": name, "arguments": json.dumps({"path": path})}}

        rows = [
            # s1: write_file previo → el patch de /a/x.py cuenta como visto
            ("s1", [_call("write_file", "/a/x.py"), _call("patch", "/a/x.py")]),
            # s1: /a/y.py nunca visto → would_block
            ("s1", [_call("patch", "/a/y.py")]),
            # s2: primer patch de /b/p.py → would_block
            ("s2", [_call("patch", "/b/p.py")]),
            # s2: el propio patch ya escribió /b/p.py → el segundo cuenta como visto
            ("s2", [_call("patch", "/b/p.py")]),
            # s3: read_file previo → el edit_file de /c/q.py cuenta como visto
            ("s3", [_call("read_file", "/c/q.py"), _call("edit_file", "/c/q.py")]),
        ]
        for sid, calls in rows:
            con.execute(
                "INSERT INTO messages (session_id, active, tool_calls) VALUES (?, 1, ?)",
                (sid, json.dumps(calls)),
            )
        con.commit()
    finally:
        con.close()

    data = mods.report.replay(str(db))

    assert data["patch_total"] == 5
    assert data["would_block"] == 2, (
        "solo /a/y.py y el primer /b/p.py se bloquean; el segundo /b/p.py cuenta como "
        "visto porque el propio patch ya escribió la ruta (misma regla que el guard): %r"
        % (data,)
    )
    assert data["sessions_affected"] == 2


# ══════════════════════════════════════════════════════════════════════════════
#  Hallazgos de revisores — ronda RED 3
#  V4A: la tool real `patch` acepta mode='patch' con SOLO la clave 'patch'
#  (texto multi-archivo) y SIN 'path' (file_tools.py _PATCH_V4A_PARAMS, ~1253).
#  El guard actual ve tool_input sin 'path', registra 'no_path' y PERMITE:
#  cualquier patch V4A edita archivos existentes a ciegas. El guard debe parsear
#  las cabeceras del parche y aplicar la MISMA regla por archivo que con 'path':
#  Update/Delete de un archivo existente exigen lectura (huella vigente);
#  Add File (creación) no la exige.
# ══════════════════════════════════════════════════════════════════════════════


def make_v4a_event(patch_text: str, cwd, session: str = SESSION, **tool_input_extra) -> dict:
    """Evento pre_tool_call de patch en modo V4A: tool_input con SOLO
    {'mode': 'patch', 'patch': <texto>} — SIN la clave 'path' (la forma real
    que la tool acepta según _PATCH_V4A_PARAMS)."""
    return {
        "hook_event_name": "pre_tool_call",
        "tool_name": "patch",
        "tool_input": {"mode": "patch", "patch": patch_text, **tool_input_extra},
        "session_id": session,
        "cwd": str(cwd),
    }


def _v4a(*lines: str) -> str:
    """Arma un parche V4A mínimo con Begin/End alrededor de las secciones."""
    return "\n".join(["*** Begin Patch", *lines, "*** End Patch"])


def test_v4a_update_file_existing_without_read_is_blocked(state_root, enforce, tmp_path):
    mods = load_modules()
    """V4A (a): mode='patch' sin 'path' con `*** Update File:` de un archivo EXISTENTE
    sin lectura previa ⇒ exit 2 y el reason contiene la ruta EXACTA del archivo."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")
    ev = make_v4a_event(
        _v4a("*** Update File: app.py", "@@ @@", "-value = 1", "+value = 2"),
        tmp_path,
    )

    code, payload = mods.guard.handle(ev, root=state_root)

    assert code == 2, (
        "un patch V4A que actualiza un archivo existente sin lectura previa debe "
        "bloquearse como cualquier patch con 'path'; payload=%r" % (payload,)
    )
    assert payload["decision"] == "block"
    assert str(target) in payload["reason"], payload["reason"]
    assert "read_file" in payload["reason"], payload["reason"]


def test_v4a_update_file_allowed_after_read_file_record(state_root, enforce, tmp_path):
    mods = load_modules()
    """V4A (b): `*** Update File:` tras record() de read_file de esa ruta y sin
    cambios en disco ⇒ permitido (exit 0)."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")
    mods.state.record(SESSION, "read_file", str(target), root=state_root)
    ev = make_v4a_event(
        _v4a("*** Update File: app.py", "@@ @@", "-value = 1", "+value = 2"),
        tmp_path,
    )

    code, payload = mods.guard.handle(ev, root=state_root)

    assert code == 0, payload
    assert payload.get("decision") != "block"


def test_v4a_add_file_only_creation_requires_no_read(state_root, enforce, tmp_path):
    mods = load_modules()
    """V4A (c): solo `*** Add File:` de un archivo NUEVO que no existe ⇒ exit 0
    (crear no requiere lectura previa)."""
    assert not (tmp_path / "nuevo.py").exists()
    ev = make_v4a_event(
        _v4a("*** Add File: nuevo.py", "+contenido nuevo"),
        tmp_path,
    )

    code, payload = mods.guard.handle(ev, root=state_root)

    assert code == 0, payload
    assert payload.get("decision") != "block"


def test_v4a_delete_file_existing_without_read_is_blocked(state_root, enforce, tmp_path):
    mods = load_modules()
    """V4A (d): `*** Delete File:` de un archivo EXISTENTE sin lectura previa ⇒ exit 2
    (borrar a ciegas también es editar a ciegas); el reason nombra la ruta."""
    target = tmp_path / "viejo.py"
    target.write_text("value = 1\n", encoding="utf-8")
    ev = make_v4a_event(_v4a("*** Delete File: viejo.py"), tmp_path)

    code, payload = mods.guard.handle(ev, root=state_root)

    assert code == 2, (
        "borrar un archivo existente sin haberlo leído debe bloquearse; payload=%r"
        % (payload,)
    )
    assert payload["decision"] == "block"
    assert str(target) in payload["reason"], payload["reason"]


def test_v4a_multi_file_block_reason_names_only_the_unread_file(state_root, enforce, tmp_path):
    mods = load_modules()
    """V4A (e): parche multi-archivo con un archivo ya leído y otro sin leer ⇒ exit 2
    y el reason nombra SOLO el no leído (no el leído)."""
    read_target = tmp_path / "leido.py"
    read_target.write_text("value = 1\n", encoding="utf-8")
    unread_target = tmp_path / "no_leido.py"
    unread_target.write_text("value = 1\n", encoding="utf-8")
    mods.state.record(SESSION, "read_file", str(read_target), root=state_root)
    ev = make_v4a_event(
        _v4a(
            "*** Update File: leido.py",
            "@@ @@", "-value = 1", "+value = 2",
            "*** Update File: no_leido.py",
            "@@ @@", "-value = 1", "+value = 3",
        ),
        tmp_path,
    )

    code, payload = mods.guard.handle(ev, root=state_root)

    assert code == 2, payload
    assert payload["decision"] == "block"
    reason = payload["reason"]
    assert str(unread_target) in reason, reason
    assert str(read_target) not in reason, (
        "el reason no debe nombrar el archivo que SÍ fue leído: %r" % (reason,)
    )


def test_v4a_update_file_blocked_when_file_changed_on_disk_after_read(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """V4A (f): `*** Update File:` tras read_file registrado pero el archivo cambió
    en disco después (huella desactualizada) ⇒ exit 2, igual que con 'path' (CA3)."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")
    mods.state.record(SESSION, "read_file", str(target), root=state_root)
    target.write_text("value = 2\n", encoding="utf-8")  # otro proceso escribió
    ev = make_v4a_event(
        _v4a("*** Update File: app.py", "@@ @@", "-value = 1", "+value = 9"),
        tmp_path,
    )

    code, payload = mods.guard.handle(ev, root=state_root)

    assert code == 2, payload
    assert payload["decision"] == "block"
    assert str(target) in payload["reason"], payload["reason"]


def test_v4a_replace_mode_with_path_keeps_existing_behavior(state_root, enforce, tmp_path):
    mods = load_modules()
    """V4A (g, regresión): mode='replace' con path+old_string+new_string sigue la regla
    de siempre — sin lectura previa ⇒ exit 2; tras read_file ⇒ exit 0. El parsing V4A
    no debe romper el modo por defecto de la tool."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    ev = {
        "hook_event_name": "pre_tool_call",
        "tool_name": "patch",
        "tool_input": {
            "mode": "replace",
            "path": str(target),
            "old_string": "value = 1",
            "new_string": "value = 2",
        },
        "session_id": SESSION,
        "cwd": str(tmp_path),
    }
    code, payload = mods.guard.handle(ev, root=state_root)
    assert code == 2, payload
    assert payload["decision"] == "block"
    assert str(target) in payload["reason"]

    mods.state.record(SESSION, "read_file", str(target), root=state_root)
    code2, payload2 = mods.guard.handle(ev, root=state_root)
    assert code2 == 0, payload2
    assert payload2.get("decision") != "block"
