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


# ══════════════════════════════════════════════════════════════════════════════
#  Hallazgos de revisores — ronda RED 4 (codex)
#
#  H1 (high) TOCTOU de la huella: la huella se toma DESPUÉS de correr la tool,
#    no de lo que el agente vio. Un write externo entre la tool read_file y el
#    post_tool_call registra la versión NUEVA como "vista" → patch a ciegas.
#  H2 (high) Registro de V4A: el post_tool_call de un patch V4A exitoso
#    (tool_input={'mode':'patch','patch':...}, sin 'path') no registra NADA:
#    las rutas de las cabeceras deben quedar con su huella.
#  M1 (medium) Replay sin correlación de resultados: el replay solo puede ver
#    lo que hay en la DB, pero hoy ignora las filas role='tool': una read_file
#    fallida (o sin resultado) marca el path como visto, un patch V4A sin
#    'path' no cuenta y un patch bloqueado deja la ruta como vista.
#  M2 (medium) Retención: la poda de 7 días solo corre si el ledger está
#    inactivo (>1 h); el pre debe ignorar entradas fuera de la ventana de
#    retención aunque el ledger tenga actividad reciente.
# ══════════════════════════════════════════════════════════════════════════════


def _post_event(tool: str, tool_input: dict, cwd, session: str = SESSION) -> dict:
    """Evento post_tool_call del contrato shell_hooks con extra.status='ok'."""
    return {
        "hook_event_name": "post_tool_call",
        "tool_name": tool,
        "tool_input": tool_input,
        "session_id": session,
        "cwd": str(cwd),
        "extra": {"status": "ok"},
    }


# ── R4-H1: TOCTOU de la huella ────────────────────────────────────────────────


def test_r4_h1_toctou_post_read_registers_fingerprint_agent_saw_not_disk_now(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """R4-H1 (codex, high): la huella registrada por el post de una lectura debe ser
    la del contenido que el agente VIO (pre-modificación), no la de disco al llegar
    el post. Si otro proceso escribe el archivo entre la tool read_file y el
    post_tool_call (status='ok'), hoy se registra la versión NUEVA como vista y un
    patch a ciegas sobre el contenido nuevo queda permitido."""
    target = tmp_path / "app.py"
    target.write_text("valor = 1\n", encoding="utf-8")
    visto = target.stat()  # lo que el agente está a punto de ver

    # pre de la lectura: hoy el guard ignora read_file en pre (no es tool de
    # edición); una implementación correcta puede tomar aquí la instantánea.
    code, _ = mods.guard.handle(
        make_event("pre_tool_call", "read_file", target, tmp_path), root=state_root
    )
    assert code == 0

    # TOCTOU: otro proceso modifica el archivo ANTES de que llegue el post.
    target.write_text("valor = 11  # escrito por otro proceso\n", encoding="utf-8")

    # post_tool_call de ESA lectura, con resultado ok.
    code, _ = mods.guard.handle(
        _post_event("read_file", {"path": str(target)}, tmp_path), root=state_root
    )
    assert code == 0

    last = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert last is not None, "la lectura con status ok debe quedar registrada"
    assert (last["mtime_ns"], last["size"]) == (visto.st_mtime_ns, visto.st_size), (
        "la huella registrada debe ser la del contenido que el agente vio "
        "(pre-modificación), no la de disco al llegar el post: %r" % (last,)
    )

    # y el patch a ciegas sobre el contenido que NUNCA vio debe bloquearse.
    code, payload = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )
    assert code == 2, (
        "el patch sobre contenido que el agente nunca vio debe bloquearse: "
        "exit=%s payload=%r" % (code, payload)
    )
    assert payload["decision"] == "block"


# ── R4-H2: registro del patch V4A exitoso ────────────────────────────────────


def test_r4_h2_post_v4a_patch_ok_registers_header_path_and_second_patch_passes(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """R4-H2 (codex, high): el post_tool_call de un patch V4A exitoso (status='ok')
    debe registrar las rutas de las cabeceras Update File con su huella. Hoy el
    _post exige la clave 'path' y descarta el evento: tras read_file + V4A patch,
    un SEGUNDO V4A patch sobre el mismo archivo se bloquea injustificadamente."""
    target = tmp_path / "app.py"
    target.write_text("a = 1\n", encoding="utf-8")

    # 1) lectura previa (post ok; el archivo no cambió: lo que registra es correcto)
    code, _ = mods.guard.handle(
        _post_event("read_file", {"path": str(target)}, tmp_path), root=state_root
    )
    assert code == 0

    patch1 = _v4a("*** Update File: app.py", "@@", "-a = 1", "+a = 22")
    # 2) el primer V4A patch está permitido (huella vigente)
    code, payload = mods.guard.handle(make_v4a_event(patch1, tmp_path), root=state_root)
    assert code == 0, payload

    # 3) la tool aplicó el parche (simulado) y llega el post_tool_call ok
    target.write_text("a = 22\n", encoding="utf-8")
    code, _ = mods.guard.handle(
        _post_event("patch", {"mode": "patch", "patch": patch1}, tmp_path),
        root=state_root,
    )
    assert code == 0

    # 4) la ruta de la cabecera debe quedar registrada con la huella POST-parche
    last = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert last is not None, (
        "el post de un patch V4A ok debe registrar la ruta de la cabecera Update File"
    )
    st = target.stat()
    assert (last["mtime_ns"], last["size"]) == (st.st_mtime_ns, st.st_size), (
        "debe registrar la huella del contenido que el propio patch escribió: %r"
        % (last,)
    )
    assert last["tool"] == "patch", last

    # 5) el segundo V4A patch sobre el mismo archivo NO se bloquea
    patch2 = _v4a("*** Update File: app.py", "@@", "-a = 22", "+a = 333")
    code, payload = mods.guard.handle(make_v4a_event(patch2, tmp_path), root=state_root)
    assert code == 0, (
        "el segundo V4A patch tras un V4A exitoso no debe bloquearse (la escritura "
        "del propio patch ya dejó la huella registrada): exit=%s payload=%r"
        % (code, payload)
    )


def test_r4_h2_post_v4a_multi_file_ok_registers_every_update_file_header(
    state_root, tmp_path
):
    mods = load_modules()
    """R4-H2 multi-archivo: el post de un patch V4A ok con DOS cabeceras Update File
    debe registrar LAS DOS rutas (resueltas contra el cwd del payload) con su huella."""
    f1 = tmp_path / "one.py"
    f1.write_text("uno = 1\n", encoding="utf-8")
    f2 = tmp_path / "two.py"
    f2.write_text("dos = 2\n", encoding="utf-8")
    patch = _v4a(
        "*** Update File: one.py",
        "@@",
        "-uno = 1",
        "+uno = 11",
        "*** Update File: two.py",
        "@@",
        "-dos = 2",
        "+dos = 22",
    )
    code, _ = mods.guard.handle(
        _post_event("patch", {"mode": "patch", "patch": patch}, tmp_path),
        root=state_root,
    )
    assert code == 0
    for f in (f1, f2):
        last = mods.state.last_seen(SESSION, str(f), root=state_root)
        st = f.stat()
        assert last is not None, "falta registrar la cabecera de %s" % f.name
        assert (last["mtime_ns"], last["size"]) == (st.st_mtime_ns, st.st_size), (
            "huella incorrecta para %s: %r" % (f.name, last)
        )


# ── R4-M1: replay con correlación de resultados (solo ve lo que hay en la DB) ─


def _m1_db(tmp_path: Path):
    """DB sqlite temporal con el esquema mínimo (formato real de state.db.messages)."""
    db = tmp_path / "state.db"
    con = sqlite3.connect(str(db))
    con.execute(
        "CREATE TABLE messages ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " session_id TEXT NOT NULL,"
        " role TEXT NOT NULL,"
        " content TEXT,"
        " tool_call_id TEXT,"
        " tool_calls TEXT,"
        " tool_name TEXT,"
        " active INTEGER NOT NULL DEFAULT 1,"
        " timestamp REAL NOT NULL DEFAULT 0)"
    )
    return db, con


def _m1_call(call_id: str, name: str, **arguments) -> dict:
    """tool_call con id (la DB real enlaza resultados vía tool_call_id)."""
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def _m1_assistant(con, sid: str, calls: list) -> None:
    con.execute(
        "INSERT INTO messages (session_id, role, tool_calls, active, timestamp)"
        " VALUES (?, 'assistant', ?, 1, 1)",
        (sid, json.dumps(calls)),
    )


def _m1_tool_result(con, sid: str, call_id: str, tool: str, content: str) -> None:
    con.execute(
        "INSERT INTO messages (session_id, role, content, tool_call_id, tool_name,"
        " active, timestamp) VALUES (?, 'tool', ?, ?, ?, 1, 1)",
        (sid, content, call_id, tool),
    )


def test_r4_m1_replay_failed_read_error_result_does_not_mark_seen_db_only_view(
    tmp_path,
):
    mods = load_modules()
    """R4-M1 (codex, medium): el replay solo puede ver lo que hay en la DB. Una
    read_file cuyo role='tool' trae un resultado con error (formato real:
    {"error": "File not found: ..."}) NO marca el path como visto, así que el
    patch posterior de esa ruta cuenta como would_block."""
    db, con = _m1_db(tmp_path)
    try:
        _m1_assistant(con, "s-r4-m1", [_m1_call("call_r1", "read_file", path="/a/a.py")])
        _m1_tool_result(
            con, "s-r4-m1", "call_r1", "read_file",
            json.dumps({"error": "File not found: /a/a.py"}),
        )
        _m1_assistant(
            con, "s-r4-m1",
            [_m1_call("call_p1", "patch", path="/a/a.py", old_string="x", new_string="y")],
        )
        _m1_tool_result(
            con, "s-r4-m1", "call_p1", "patch",
            json.dumps({"success": True, "diff": "--- a/a.py\n+++ b/a.py"}),
        )
        con.commit()
    finally:
        con.close()

    data = mods.report.replay(str(db))
    assert data["patch_total"] == 1, data
    assert data["would_block"] == 1, (
        "la read_file con resultado de error no marca /a/a.py como visto, así que "
        "el patch posterior es would_block: %r" % (data,)
    )


def test_r4_m1_replay_missing_tool_result_does_not_mark_seen_db_only_view(tmp_path):
    mods = load_modules()
    """R4-M1: el replay solo puede ver lo que hay en la DB. Un tool_call cuyo
    resultado NO existe (sin fila role='tool' con su tool_call_id) no prueba que
    el agente viera el contenido: NO marca el path como visto. La DB de este test
    SÍ tiene filas de resultado para otra llamada (formato actual de state.db);
    el caso legacy sin ninguna fila de resultado lo cubre el test CA11 de sqlite
    ya existente en esta suite."""
    db, con = _m1_db(tmp_path)
    try:
        _m1_assistant(con, "s-r4-m1", [_m1_call("call_r1", "read_file", path="/b/b.py")])
        _m1_tool_result(
            con, "s-r4-m1", "call_r1", "read_file",
            json.dumps({"content": "1|hola\n", "total_lines": 1, "file_size": 5}),
        )
        # /b/missing.py: la llamada existe pero SU resultado no está en la DB
        _m1_assistant(con, "s-r4-m1", [_m1_call("call_r2", "read_file", path="/b/missing.py")])
        _m1_assistant(
            con, "s-r4-m1",
            [_m1_call("call_p2", "patch", path="/b/missing.py", old_string="x", new_string="y")],
        )
        _m1_tool_result(
            con, "s-r4-m1", "call_p2", "patch",
            json.dumps({"success": True, "diff": "--- b/missing.py\n+++ b/missing.py"}),
        )
        con.commit()
    finally:
        con.close()

    data = mods.report.replay(str(db))
    assert data["patch_total"] == 1, data
    assert data["would_block"] == 1, (
        "la read_file de /b/missing.py no tiene resultado en la DB, así que no "
        "marca el path como visto y su patch es would_block: %r" % (data,)
    )
    assert data["sessions_affected"] == 1, data


def test_r4_m1_replay_counts_v4a_patch_without_path_key_db_only_view(tmp_path):
    mods = load_modules()
    """R4-M1: el replay solo puede ver lo que hay en la DB. Un patch V4A sin la
    clave 'path' (tool_input={'mode':'patch','patch':...}) debe CONTAR en
    patch_total. Reglas idénticas al guard: la cabecera Update File apunta a
    /c/c.py, que fue leída con éxito antes (resultado sin error), así que NO es
    would_block — contarla como bloqueada inflaría el reporte."""
    db, con = _m1_db(tmp_path)
    try:
        _m1_assistant(con, "s-r4-m1", [_m1_call("call_r3", "read_file", path="/c/c.py")])
        _m1_tool_result(
            con, "s-r4-m1", "call_r3", "read_file",
            json.dumps({"content": "1|hola\n", "total_lines": 1, "file_size": 5}),
        )
        v4a = "*** Begin Patch\n*** Update File: /c/c.py\n@@\n-hola\n+chau\n*** End Patch"
        _m1_assistant(
            con, "s-r4-m1",
            [_m1_call("call_p3", "patch", mode="patch", patch=v4a)],
        )
        _m1_tool_result(
            con, "s-r4-m1", "call_p3", "patch",
            json.dumps({"success": True, "diff": "--- c/c.py\n+++ c/c.py"}),
        )
        con.commit()
    finally:
        con.close()

    data = mods.report.replay(str(db))
    assert data["patch_total"] == 1, (
        "un patch V4A sin 'path' debe contar en patch_total: %r" % (data,)
    )
    assert data["would_block"] == 0, (
        "la cabecera apunta a /c/c.py, leído con éxito antes (reglas idénticas al "
        "guard), así que NO es would_block: %r" % (data,)
    )


def test_r4_m1_replay_blocked_patch_does_not_mark_seen_db_only_view(tmp_path):
    mods = load_modules()
    """R4-M1: el replay solo puede ver lo que hay en la DB. Un patch que fue
    bloqueado (resultado con success=false y el reason del guard) NO dejó la ruta
    como vista: el reintento idéntico cuenta OTRO would_block (hoy el primer patch
    marca la ruta él mismo y el reintento sale gratis)."""
    db, con = _m1_db(tmp_path)
    try:
        bloqueado = json.dumps(
            {
                "success": False,
                "error": "Ejecuta read_file /d/d.py antes de editarlo: cambió desde "
                "la última lectura (o no la hubo en esta sesión).",
            }
        )
        _m1_assistant(
            con, "s-r4-m1",
            [_m1_call("call_p4", "patch", path="/d/d.py", old_string="x", new_string="y")],
        )
        _m1_tool_result(con, "s-r4-m1", "call_p4", "patch", bloqueado)
        _m1_assistant(
            con, "s-r4-m1",
            [_m1_call("call_p5", "patch", path="/d/d.py", old_string="x", new_string="y")],
        )
        _m1_tool_result(
            con, "s-r4-m1", "call_p5", "patch",
            json.dumps({"success": True, "diff": "--- d/d.py\n+++ d/d.py"}),
        )
        con.commit()
    finally:
        con.close()

    data = mods.report.replay(str(db))
    assert data["patch_total"] == 2, data
    assert data["would_block"] == 2, (
        "el patch bloqueado nunca escribió /d/d.py, así que el reintento idéntico "
        "también habría sido bloqueado: %r" % (data,)
    )
    assert data["sessions_affected"] == 1, data


# ── R4-M2: retención de 7 días aunque el ledger esté activo ──────────────────


def test_r4_m2_pre_ignores_entry_older_than_retention_even_with_recent_ledger(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """R4-M2 (codex, medium): la poda por retención (7 días) solo corre si el
    ledger está inactivo (>1 h de mtime), así que en un ledger con actividad
    reciente una entrada vieja sobrevive y hoy el pre la acepta como "visto".
    El pre debe IGNORAR entradas con ts anterior a la ventana de retención,
    aunque el ledger tenga actividad reciente y aunque haya entradas nuevas
    detrás de la vieja."""
    target = tmp_path / "auth.py"
    target.write_text("token = 'v1'\n", encoding="utf-8")
    st = target.stat()
    other = tmp_path / "otro.py"
    other.write_text("x = 1\n", encoding="utf-8")
    ost = other.stat()

    now = time.time()
    old_ts = now - (mods.state.RETENTION_DAYS + 1) * 86400  # hace 8 días
    old_entry = {
        "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(old_ts)),
        "ts": old_ts,
        "ev": "post_tool_call",
        "tool": "read_file",
        "path": str(target),
        "mtime_ns": st.st_mtime_ns,
        "size": st.st_size,
        "ok": True,
    }
    new_entry = {
        "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "ts": now,
        "ev": "post_tool_call",
        "tool": "write_file",
        "path": str(other),
        "mtime_ns": ost.st_mtime_ns,
        "size": ost.st_size,
        "ok": True,
    }
    ledger = mods.state.ledger_path(SESSION, state_root)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        json.dumps(old_entry) + "\n" + json.dumps(new_entry) + "\n", encoding="utf-8"
    )

    # la entrada vieja NO autoriza el patch sobre target (la poda oportunista no
    # corrió: el ledger acaba de tocarse — el pre debe filtrar por edad igual).
    code, payload = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )
    assert code == 2, (
        "la entrada de hace >RETENTION_DAYS no autoriza el patch aunque el ledger "
        "tenga actividad reciente (exit=%s payload=%r)" % (code, payload)
    )
    assert payload["decision"] == "block"

    # y la entrada RECIENTE sigue autorizando (el pre no descarta el ledger entero)
    code2, payload2 = mods.guard.handle(
        make_event("pre_tool_call", "patch", other, tmp_path), root=state_root
    )
    assert code2 == 0, (
        "la entrada reciente de otro.py sigue autorizando su patch: "
        "exit=%s payload=%r" % (code2, payload2)
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Hallazgos de revisores — ronda RED 5 (juez codex, ronda 4)
#
#  R5-H1 (high): el bloque yaml de config de 02-design.md §3 propone un matcher
#    de pre_tool_call `^(patch|edit_file)$` SIN read_file: _pre_read nunca corre
#    y el TOCTOU de la lectura (ronda 4) cae siempre al fallback de disco.
#  R5-H2 (high): tras write_file/patch/edit_file ok, el post registra la huella
#    del disco de ESE instante: si otro proceso escribe entre la tool y el post,
#    se certifica contenido que el agente no escribió.
#  R5-M3 (medium): writes_total y sessions_with_writes del replay (CA11) no
#    cuentan write_file (sale por el continue de MARK_TOOLS antes de contar).
# ══════════════════════════════════════════════════════════════════════════════


def _design_hooks_yaml() -> dict:
    """Parsea el bloque ```yaml del §3 de 02-design.md (la config REAL que se
    copia a config.yaml: si el doc y el código divergen, el doc manda el bug)."""
    import re as re_mod

    try:
        import yaml as yaml_mod
    except ImportError:  # pragma: no cover
        pytest.fail("PyYAML no disponible: el test no puede parsear el bloque yaml del diseño")

    design = REPO / ".specs" / "read-before-patch-guard" / "02-design.md"
    text = design.read_text(encoding="utf-8")
    blocks = re_mod.findall(r"```yaml\n(.*?)```", text, re_mod.DOTALL)
    with_hooks = [b for b in blocks if "hooks:" in b and "matcher" in b]
    assert with_hooks, "02-design.md debe traer el bloque yaml de registro en config (§3)"
    data = yaml_mod.safe_load(with_hooks[0])
    assert isinstance(data, dict) and isinstance(data.get("hooks"), dict), (
        "el bloque yaml del diseño no parsea a un mapping hooks: %r" % (data,)
    )
    return data["hooks"]


def _matcher_of(entries, event_key):
    """matcher de la única entrada del evento dado (mismo contrato que config.yaml)."""
    lst = entries.get(event_key)
    assert isinstance(lst, list) and len(lst) == 1, (
        "02-design.md §3 declara UNA sola entrada por evento (§3 'una sola entrada, no "
        "dos'): %r" % (entries,)
    )
    matcher = lst[0].get("matcher")
    assert isinstance(matcher, str) and matcher, "entrada %s sin matcher: %r" % (event_key, lst)
    return matcher


def test_r5_h1_design_yaml_pre_matcher_matches_read_file_patch_edit_file():
    mods = load_modules()
    """R5-H1 (juez codex, high): el matcher del pre en el bloque yaml de
    02-design.md §3 debe matchear read_file|patch|edit_file con re.fullmatch —
    el MISMO algoritmo que _ToolMatcherMixin.matches_tool (agent/shell_hooks.py).
    Con el yaml viejo (`^(patch|edit_file)$`) _pre_read jamás corre: el post de
    read_file cae al fallback de huella de disco y el TOCTOU (ronda 4 / H1)
    queda sin cobertura. El post debe matchear read_file|write_file|patch|edit_file."""
    import re as re_mod

    hooks = _design_hooks_yaml()
    pre_matcher = _matcher_of(hooks, "pre_tool_call")
    post_matcher = _matcher_of(hooks, "post_tool_call")

    # el pre debe compilar (config inválida = matcher literal, peor aún)
    pre_re = re_mod.compile(pre_matcher)
    post_re = re_mod.compile(post_matcher)

    for tool in ("read_file", "patch", "edit_file"):
        assert pre_re.fullmatch(tool) is not None, (
            "el matcher del PRE en 02-design.md §3 (%r) no matchea %r con fullmatch "
            "(mismo algoritmo que _ToolMatcherMixin.matches_tool): el pre de esa tool "
            "nunca corre" % (pre_matcher, tool)
        )
    for tool in ("read_file", "write_file", "patch", "edit_file"):
        assert post_re.fullmatch(tool) is not None, (
            "el matcher del POST en 02-design.md §3 (%r) no matchea %r con fullmatch: "
            "el post de esa tool nunca registra huella" % (post_matcher, tool)
        )

    # coherencia con el guard: toda tool que el post registra existe en el matcher
    for tool in sorted(mods.guard.RECORD_TOOLS):
        assert post_re.fullmatch(tool) is not None, (
            "guard.RECORD_TOOLS tiene %r pero el matcher del POST del diseño no la "
            "matchea: el despliegue real no registraría esa tool" % (tool,)
        )


# ── R5-H2: certificación de lo escrito (write_file por intención, patch por resultado) ──


def _post_event_with_result(tool: str, tool_input: dict, cwd, result, session: str = SESSION,
                            status: str = "ok") -> dict:
    """Evento post_tool_call con el payload REAL: extra.result es el JSON string
    del WriteResult/PatchResult (tools/file_operations_common.py to_dict) que el
    runner aterriza bajo extra (shell_hooks._payload_fields)."""
    ev = _post_event(tool, tool_input, cwd, session=session)
    ev["extra"] = {"status": status, "result": result if isinstance(result, str) else json.dumps(result)}
    return ev


def test_r5_h2_write_file_intent_matches_disk_records_intent_sha_and_patch_passes(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """R5-H2 (juez codex, high): el post de write_file reconstruye la INTENCIÓN
    desde tool_input['content'] y solo certifica si el sha256 de la intención
    coincide con el sha256 del disco al llegar el post: la entrada queda con el
    sha256 del contenido que el agente escribió y un patch posterior pasa."""
    import hashlib as hashlib_mod

    target = tmp_path / "app.py"
    intent = "value = 1\n"
    target.write_text(intent, encoding="utf-8")  # la tool escribió exactamente esto

    ev = _post_event_with_result(
        "write_file", {"path": str(target), "content": intent}, tmp_path,
        result={"bytes_written": len(intent), "verified": True},
    )
    code, _ = mods.guard.handle(ev, root=state_root)
    assert code == 0

    seen = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert seen is not None, "write_file con intención == disco debe registrar la huella"
    assert seen["sha256"] == hashlib_mod.sha256(intent.encode("utf-8")).hexdigest(), (
        "la entrada debe llevar el sha256 del contenido que el agente escribió: %r" % (seen,)
    )
    st = target.stat()
    assert (seen["mtime_ns"], seen["size"]) == (st.st_mtime_ns, st.st_size), seen

    code2, payload2 = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )
    assert code2 == 0, payload2  # CA4 se mantiene con la certificación por intención


def test_r5_h2_write_file_race_disk_differs_from_intent_not_recorded_and_patch_blocks(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """R5-H2 (juez codex, high) — carrera determinista: otro proceso escribe el
    archivo ENTRE la escritura de la tool y el post hook (aquí: se sobreescribe
    antes de llamar handle con el post). El contenido en disco NO es lo que el
    agente escribió: NO se registra nada, el ledger anota 'write_concurrent'
    (fail-closed: mejor falso bloqueo que falso permiso) y un pre patch posterior
    se bloquea (exit 2) en vez de editar a ciegas."""
    target = tmp_path / "app.py"
    intent = "value = 1\n"
    # la tool escribió 'intent'; OTRO proceso lo pisa antes de que llegue el post
    target.write_text("OTRO = 999\n", encoding="utf-8")

    ev = _post_event_with_result(
        "write_file", {"path": str(target), "content": intent}, tmp_path,
        result={"bytes_written": len(intent), "verified": True},
    )
    code, _ = mods.guard.handle(ev, root=state_root)
    assert code == 0

    assert mods.state.last_seen(SESSION, str(target), root=state_root) is None, (
        "la huella del disco al llegar el post certifica contenido que el agente "
        "NUNCA escribió: no debe registrarse"
    )
    events = ledger_events(mods, state_root)
    assert has_event(events, "write_concurrent"), (
        "la carrera write_file debe anotarse como 'write_concurrent' en el ledger: %r"
        % (events,)
    )

    code2, payload2 = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )
    assert code2 == 2, (
        "sin certificación de la escritura, el patch sobre contenido no visto debe "
        "bloquearse: exit=%s payload=%r" % (code2, payload2)
    )
    assert payload2["decision"] == "block"


def test_r5_h2_patch_result_success_false_does_not_record_and_retry_blocks(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """R5-H2: el post de patch/edit_file parsea extra.result (JSON string del
    PatchResult): con success=false / error presente NO registra nada aunque el
    status llegue 'ok', así que el reintento del patch sigue bloqueado."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    ev = _post_event_with_result(
        "patch", {"path": str(target), "old_string": "a", "new_string": "b"}, tmp_path,
        result={"success": False, "error": "old_string not found"},
    )
    code, _ = mods.guard.handle(ev, root=state_root)
    assert code == 0
    assert mods.state.last_seen(SESSION, str(target), root=state_root) is None, (
        "un patch con success=false no escribió nada: no debe registrar la ruta"
    )

    code2, payload2 = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )
    assert code2 == 2, payload2
    assert payload2["decision"] == "block"


@pytest.mark.parametrize("tool", ["patch", "edit_file"])
def test_r5_h2_patch_result_success_true_records_observed_fingerprint(
    state_root, enforce, tmp_path, tool
):
    mods = load_modules()
    """R5-H2: con success=true en extra.result, el post registra la huella
    observada (comportamiento previo preservado) y su sha256; el patch/edit_file
    siguiente sobre la misma ruta pasa sin nueva lectura."""
    import hashlib as hashlib_mod

    target = tmp_path / "app.py"
    target.write_text("value = 2\n", encoding="utf-8")  # la tool ya aplicó el cambio

    ev = _post_event_with_result(
        tool, {"path": str(target), "old_string": "a", "new_string": "b"}, tmp_path,
        result={"success": True, "diff": "--- a/app.py\n+++ b/app.py"},
    )
    code, _ = mods.guard.handle(ev, root=state_root)
    assert code == 0

    seen = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert seen is not None, "success=true debe registrar la huella observada"
    st = target.stat()
    assert (seen["mtime_ns"], seen["size"]) == (st.st_mtime_ns, st.st_size), seen
    assert seen.get("sha256") == hashlib_mod.sha256(b"value = 2\n").hexdigest(), seen

    code2, payload2 = mods.guard.handle(
        make_event("pre_tool_call", tool, target, tmp_path), root=state_root
    )
    assert code2 == 0, payload2


def test_r5_h2_v4a_patch_result_success_false_registers_nothing(state_root, enforce, tmp_path):
    mods = load_modules()
    """R5-H2: lo mismo para el post del patch V4A (mode='patch', sin 'path'): con
    success=false en extra.result NO se registra ninguna cabecera del parche."""
    target = tmp_path / "app.py"
    target.write_text("a = 1\n", encoding="utf-8")
    patch = _v4a("*** Update File: app.py", "@@", "-a = 1", "+a = 2")

    ev = _post_event_with_result(
        "patch", {"mode": "patch", "patch": patch}, tmp_path,
        result={"success": False, "error": "apply failed"},
    )
    code, _ = mods.guard.handle(ev, root=state_root)
    assert code == 0
    assert mods.state.last_seen(SESSION, str(target), root=state_root) is None, (
        "un V4A con success=false no escribió nada: ninguna cabecera debe registrarse"
    )


def test_r5_h2_write_file_without_content_key_legacy_payload_still_records(
    state_root, tmp_path
):
    mods = load_modules()
    """R5-H2 (payload legacy): un post de write_file sin 'content' en tool_input
    (payload antiguo) no puede reconstruir la intención: conserva el comportamiento
    de antes (registra la huella de disco) para no dejar de registrar escrituras
    legítimas. Con 'content' presente la certificación por intención es obligatoria."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    ev = _post_event("write_file", {"path": str(target)}, tmp_path)  # sin result ni content
    code, _ = mods.guard.handle(ev, root=state_root)
    assert code == 0
    assert mods.state.last_seen(SESSION, str(target), root=state_root) is not None


# ── R5-M3: write_file cuenta en writes_total / sessions_with_writes del replay ──


def test_r5_m3_replay_counts_write_file_in_writes_total_and_sessions(tmp_path):
    mods = load_modules()
    """R5-M3 (juez codex, medium): writes_total y sessions_with_writes del replay
    (CA11) deben contar write_file ANTES del continue de MARK_TOOLS; sin eso,
    would_block_pct de CA11 sale mal. Sesión que SOLO escribe write_file ⇒
    writes_total>=1 y sessions_with_writes>=1; sesión mixta ⇒ conteo exacto
    (writes_total = write_file + patch + edit_file)."""
    db, con = _m1_db(tmp_path)
    try:
        _m1_assistant(con, "s-r5-solo", [_m1_call("w1", "write_file", path="/a/x.py")])
        _m1_tool_result(
            con, "s-r5-solo", "w1", "write_file",
            json.dumps({"bytes_written": 10, "verified": True}),
        )
        _m1_assistant(
            con, "s-r5-mix",
            [
                _m1_call("w2", "write_file", path="/b/x.py"),
                _m1_call("p1", "patch", path="/b/x.py", old_string="a", new_string="b"),
                _m1_call("p2", "patch", path="/b/never.py", old_string="a", new_string="b"),
            ],
        )
        _m1_tool_result(
            con, "s-r5-mix", "w2", "write_file",
            json.dumps({"bytes_written": 10, "verified": True}),
        )
        _m1_tool_result(
            con, "s-r5-mix", "p1", "patch",
            json.dumps({"success": True, "diff": "--- b/x.py\n+++ b/x.py"}),
        )
        _m1_tool_result(
            con, "s-r5-mix", "p2", "patch",
            json.dumps({"success": True, "diff": "--- b/never.py\n+++ b/never.py"}),
        )
        con.commit()
    finally:
        con.close()

    data = mods.report.replay(str(db))

    assert data["writes_total"] == 4, (
        "writes_total = write_file (solo) + write_file + patch + patch (mix): %r"
        % (data,)
    )
    assert data["sessions_with_writes"] == 2, (
        "la sesión que SOLO hace write_file debe contar en sessions_with_writes: %r"
        % (data,)
    )
    assert data["patch_total"] == 2, data
    assert data["would_block"] == 1, data  # solo /b/never.py
    assert data["would_block_pct"] == pytest.approx(25.0), (
        "would_block_pct de CA11 se calcula sobre writes_total (1/4): %r" % (data,)
    )
    assert data["sessions_affected"] == 1, data


# ══════════════════════════════════════════════════════════════════════════════
#  Hallazgos de revisores — ronda RED 6
#
#  B1 (high, read_before_patch_state.py:315): las pendientes de lectura se
#    identifican solo por (session_id, path). Dos lecturas intercaladas del
#    mismo path con cambio de archivo entre ellas hacen que el post de la
#    primera promueva la huella de la segunda. Fix: call_id en la pendiente
#    (extra.tool_call_id o derivado del payload pre) y empareje por call_id;
#    fallback (session,path) SOLO con exactamente una pendiente viva y sin
#    call_id útil. Post tardío sin call_id con dos pendientes: no promueve.
#  B2 (high, guard_read_before_patch.py:355): tras patch exitoso se certifica
#    lo que haya en disco al llegar el post. Fix: snapshot del contenido previo
#    en el PRE (write_pending) y reconstrucción del contenido ESPERADO desde
#    tool_input en el POST (str_replace / hunks V4A / Add File); iguales ->
#    registrar con ese sha256; distintos -> NO registrar + 'write_concurrent'.
#    Sin snapshot utilizable -> fallback legacy.
#  B3 (medium, read_before_patch_report.py:104): _load_tool_results devuelve
#    True con 0 filas: replay degrada en DB con esquema actual pero vacía.
#  B4 (medium, read_before_patch_report.py:278): would_block del replay suma
#    una ruta por archivo en V4A multi-archivo; debe contar LLAMADAS (1 por
#    patch); patch_total sigue por ruta.
# ══════════════════════════════════════════════════════════════════════════════


def _event_with_call_id(base_event: dict, call_id: str) -> dict:
    """Añade extra={'tool_call_id': ...} al evento (contrato shell_hooks)."""
    extra = base_event.get("extra")
    ev_extra = dict(extra) if isinstance(extra, dict) else {}
    ev_extra["tool_call_id"] = call_id
    base_event["extra"] = ev_extra
    return base_event


def test_b1_interleaved_reads_post_of_first_promotes_first_fingerprint(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """B1 (high): dos lecturas intercaladas del mismo path con cambio de archivo
    entre ellas. El post de la PRIMERA (con su call_id) debe promover la huella
    que capturó el pre de la PRIMERA, no la de la segunda."""
    target = tmp_path / "app.py"
    target.write_text("valor = 1\n", encoding="utf-8")
    fp1 = (target.stat().st_mtime_ns, target.stat().st_size)

    pre1 = _event_with_call_id(
        make_event("pre_tool_call", "read_file", target, tmp_path), "call-1"
    )
    code, _ = mods.guard.handle(pre1, root=state_root)
    assert code == 0

    # otro proceso escribe entre las dos lecturas
    target.write_text("valor = 22\n", encoding="utf-8")
    fp2 = (target.stat().st_mtime_ns, target.stat().st_size)
    assert fp2 != fp1

    pre2 = _event_with_call_id(
        make_event("pre_tool_call", "read_file", target, tmp_path), "call-2"
    )
    code, _ = mods.guard.handle(pre2, root=state_root)
    assert code == 0

    # llega el post de la LECTURA #1 (intercalado: el post de #2 aún no llegó)
    post1 = _event_with_call_id(
        _post_event("read_file", {"path": str(target)}, tmp_path), "call-1"
    )
    code, _ = mods.guard.handle(post1, root=state_root)
    assert code == 0

    last = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert last is not None, "el post de la lectura #1 debe registrar la huella"
    assert (last["mtime_ns"], last["size"]) == fp1, (
        "el post de la lectura #1 debe promover la huella que capturó el pre #1 "
        "(lo que el agente vio), no la huella pendiente de la lectura #2: %r" % (last,)
    )


def test_b1_late_post_without_call_id_with_two_pendings_promotes_nothing(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """B1 (high, fail-closed): post tardío de read_file SIN call_id cuando hay DOS
    pendientes vivas del mismo path: no se puede saber cuál corresponde -> no
    promueve ninguna huella (last_seen queda sin entrada de esa lectura)."""
    target = tmp_path / "app.py"
    target.write_text("valor = 1\n", encoding="utf-8")
    code, _ = mods.guard.handle(
        make_event("pre_tool_call", "read_file", target, tmp_path), root=state_root
    )
    assert code == 0
    target.write_text("valor = 22\n", encoding="utf-8")
    code, _ = mods.guard.handle(
        make_event("pre_tool_call", "read_file", target, tmp_path), root=state_root
    )
    assert code == 0

    post = _post_event("read_file", {"path": str(target)}, tmp_path)  # sin call_id
    code, _ = mods.guard.handle(post, root=state_root)
    assert code == 0

    assert mods.state.last_seen(SESSION, str(target), root=state_root) is None, (
        "con dos pendientes ambiguas y sin call_id, el post no debe promover "
        "ninguna huella (fail-closed): %r"
        % (mods.state.last_seen(SESSION, str(target), root=state_root),)
    )


def _b2_read_seen(mods, state_root, tmp_path, target):
    """Deja la ruta como vista (post de read_file ok) y devuelve su huella."""
    target.write_text("a = 1\n", encoding="utf-8")
    code, _ = mods.guard.handle(
        _post_event("read_file", {"path": str(target)}, tmp_path), root=state_root
    )
    assert code == 0
    seen = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert seen is not None
    return (seen["mtime_ns"], seen["size"])


def test_b2_str_replace_clean_post_certifies_reconstructed_content(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """B2: patch mode='replace' limpio. El post debe certificar el contenido
    ESPERADO reconstruido desde tool_input (old->new sobre el snapshot del pre);
    la entrada lleva ese sha256 y el patch siguiente de la misma ruta pasa."""
    import hashlib as hashlib_mod

    target = tmp_path / "app.py"
    _b2_read_seen(mods, state_root, tmp_path, target)

    pre = {
        "hook_event_name": "pre_tool_call",
        "tool_name": "patch",
        "tool_input": {
            "mode": "replace",
            "path": str(target),
            "old_string": "a = 1",
            "new_string": "a = 2",
        },
        "session_id": SESSION,
        "cwd": str(tmp_path),
    }
    code, payload = mods.guard.handle(pre, root=state_root)
    assert code == 0, payload

    # la tool aplicó el reemplazo; llega el post ok con resultado exitoso
    target.write_text("a = 2\n", encoding="utf-8")
    post = _post_event_with_result(
        "patch",
        {"mode": "replace", "path": str(target), "old_string": "a = 1", "new_string": "a = 2"},
        tmp_path,
        result={"success": True, "diff": "--- a/app.py\n+++ b/app.py"},
    )
    code, _ = mods.guard.handle(post, root=state_root)
    assert code == 0

    seen = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert seen is not None, "patch str_replace limpio debe registrar la ruta"
    assert seen.get("sha256") == hashlib_mod.sha256(b"a = 2\n").hexdigest(), seen

    code2, payload2 = mods.guard.handle(pre, root=state_root)  # nuevo contenido ya visto
    assert code2 == 0, payload2


def test_b2_v4a_race_third_party_overwrite_not_recorded_and_next_pre_blocks(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """B2 (carrera determinista): un V4A exitoso escribe, pero un TERCERO
    sobrescribe el archivo antes del post. El post NO debe registrar (el
    contenido esperado reconstruido difiere del disco), debe anotar
    'write_concurrent' y el pre posterior debe bloquear (exit 2)."""
    target = tmp_path / "app.py"
    seen_fp = _b2_read_seen(mods, state_root, tmp_path, target)  # huella de la lectura

    patch_text = _v4a("*** Update File: app.py", "@@", "-a = 1", "+a = 22")
    code, payload = mods.guard.handle(make_v4a_event(patch_text, tmp_path), root=state_root)
    assert code == 0, payload  # el pre permite (huella vigente) y captura snapshot

    # la tool aplicó el parche y A CONTINUACIÓN un tercero pisó el archivo
    target.write_text("TERCERO = 999\n", encoding="utf-8")

    post = _post_event_with_result(
        "patch", {"mode": "patch", "patch": patch_text}, tmp_path,
        result={"success": True, "diff": "--- a/app.py\n+++ b/app.py"},
    )
    code, _ = mods.guard.handle(post, root=state_root)
    assert code == 0

    last = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert last is None or (last["mtime_ns"], last["size"]) == seen_fp, (
        "la carrera con tercero no debe certificar el contenido ajeno del disco: "
        "el último registro debe seguir siendo el de la lectura, no %r" % (last,)
    )
    assert has_event(ledger_events(mods, state_root), "write_concurrent"), (
        "la carrera debe anotarse como 'write_concurrent': %r"
        % (ledger_events(mods, state_root),)
    )

    code2, payload2 = mods.guard.handle(
        make_v4a_event(
            _v4a("*** Update File: app.py", "@@", "-TERCERO = 999", "+x = 1"), tmp_path
        ),
        root=state_root,
    )
    assert code2 == 2, (
        "sin certificación de la escritura, el siguiente patch debe bloquearse: "
        "exit=%s payload=%r" % (code2, payload2)
    )
    assert payload2["decision"] == "block"


def test_b2_v4a_clean_consecutive_patches_exit_0(state_root, enforce, tmp_path):
    mods = load_modules()
    """B2 (camino limpio V4A): read_file -> V4A patch #1 (pre+post) -> V4A patch
    #2 sobre la misma ruta: ambos pasan (exit 0), la certificación por
    reconstrucción no rompe los V4A consecutivos."""
    target = tmp_path / "app.py"
    _b2_read_seen(mods, state_root, tmp_path, target)

    patch1 = _v4a("*** Update File: app.py", "@@", "-a = 1", "+a = 22")
    code, payload = mods.guard.handle(make_v4a_event(patch1, tmp_path), root=state_root)
    assert code == 0, payload
    target.write_text("a = 22\n", encoding="utf-8")  # la tool aplicó el parche
    code, _ = mods.guard.handle(
        _post_event_with_result(
            "patch", {"mode": "patch", "patch": patch1}, tmp_path,
            result={"success": True, "diff": "--- a/app.py\n+++ b/app.py"},
        ),
        root=state_root,
    )
    assert code == 0
    assert mods.state.last_seen(SESSION, str(target), root=state_root) is not None

    patch2 = _v4a("*** Update File: app.py", "@@", "-a = 22", "+a = 333")
    code, payload2 = mods.guard.handle(make_v4a_event(patch2, tmp_path), root=state_root)
    assert code == 0, (
        "el segundo V4A tras uno exitoso y certificado no debe bloquearse: "
        "exit=%s payload=%r" % (code, payload2)
    )


def test_b3_replay_current_schema_with_empty_tool_results_keeps_calls_ok(tmp_path):
    mods = load_modules()
    """B3 (medium): DB con el esquema ACTUAL (columnas role/tool_call_id) pero
    CERO filas role='tool': _load_tool_results debe distinguir 'sin tabla' de
    'tabla existe y 0 filas'; con 0 filas no hay correlación -> por llamada se
    trata como legacy (exitoso), no degradando todo a fallido."""
    db, con = _m1_db(tmp_path)
    try:
        _m1_assistant(con, "s-b3", [_m1_call("call_r", "read_file", path="/b3/x.py")])
        _m1_assistant(
            con, "s-b3",
            [_m1_call("call_p", "patch", path="/b3/x.py", old_string="a", new_string="b")],
        )
        # CERO filas role='tool' (la tabla/consulta existe, no hay resultados)
        con.commit()
        n = con.execute("SELECT COUNT(*) FROM messages WHERE role='tool'").fetchone()[0]
        assert n == 0
    finally:
        con.close()

    data = mods.report.replay(str(db))
    assert data["patch_total"] == 1, data
    assert data["would_block"] == 0, (
        "con esquema actual y 0 resultados, cada llamada se trata como legacy "
        "(exitosa): la lectura marca la ruta y el patch NO es would_block: %r"
        % (data,)
    )


def test_b4_replay_v4a_multi_file_unseen_counts_one_block_per_call(tmp_path):
    mods = load_modules()
    """B4 (medium): un patch V4A con 3 archivos nunca vistos produce UN bloqueo
    por LLAMADA (el guard devuelve un único bloqueo por patch), no 3 por ruta.
    patch_total sigue contando la llamada."""
    v4a = _v4a(
        "*** Update File: /b4/uno.py", "@@", "-a\n+b",
        "*** Update File: /b4/dos.py", "@@", "-c\n+d",
        "*** Update File: /b4/tres.py", "@@", "-e\n+f",
    )
    db, con = _m1_db(tmp_path)
    try:
        _m1_assistant(con, "s-b4", [_m1_call("call_p", "patch", mode="patch", patch=v4a)])
        con.commit()
    finally:
        con.close()

    data = mods.report.replay(str(db))
    assert data["patch_total"] == 1, data
    assert data["would_block"] == 1, (
        "would_block debe contar LLAMADAS de patch bloqueadas (1), no rutas (3): %r"
        % (data,)
    )
    assert data["sessions_affected"] == 1, data


# ══════════════════════════════════════════════════════════════════════════════
#  Hallazgos de revisores — ronda RED 7
#
#  H-A (high, guard_read_before_patch.py:256): el snapshot previo del pre de
#    patch/edit_file guardaba el CONTENIDO COMPLETO del archivo dentro del
#    ledger JSONL persistente (retención 7 días): duplica secretos en claro y
#    contradice 02-design §4 ('solo huellas'). Fix: el ledger JSONL deja de
#    contener JAMÁS contenido de archivo; el snapshot va a un archivo efímero
#    fuera del ledger: <root>/snapshots/<session>/<call_id>.snap con
#    directorio 0700 y archivo 0600, borrado en el post que lo consume y
#    barrido por TTL corto (SNAP_TTL_S = 10 min) en la poda existente. Si el
#    snapshot no se puede escribir (permisos/ENOSPC), el post cae fail-closed
#    (no certificar) en vez de certificar la huella de disco.
#  H-B (high, guard_read_before_patch.py:535): cuando la reconstrucción del
#    contenido esperado falla DESPUÉS de un patch que reportó éxito, el post
#    caía al fallback legacy (huella de disco actual) y certificaba una
#    versión potencialmente ajena; un hunk V4A que no empieza en la primera
#    línea activaba ese camino. Fix: fail-closed real — con tool_input
#    utilizable y reconstrucción/verificación fallida (hunk no aplicable, sha
#    distinto, snapshot ausente para ese path, pendiente ambigua) NO se
#    registra nada y se anota 'write_unverifiable' en el ledger; el fallback
#    legacy queda SOLO para payload sin pendiente (post sin pre, imposible en
#    producción).
# ══════════════════════════════════════════════════════════════════════════════

SECRETO_R7 = "sk-live-SECRETO-ABC123"


def _h7_read_and_pre(mods, state_root, tmp_path, target, patch_text):
    """Deja la ruta vista (post de read_file ok) y corre el pre V4A (que debe
    capturar el snapshot). Devuelve la huella que la lectura registró."""
    code, _ = mods.guard.handle(
        _post_event("read_file", {"path": str(target)}, tmp_path), root=state_root
    )
    assert code == 0
    seen = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert seen is not None
    code, payload = mods.guard.handle(
        make_v4a_event(patch_text, tmp_path), root=state_root
    )
    assert code == 0, payload
    return (seen["mtime_ns"], seen["size"])


def _h7_v4a_post_ok(mods, state_root, tmp_path, patch_text):
    """Post_tool_call ok de un patch V4A con resultado estructurado exitoso."""
    return mods.guard.handle(
        _post_event_with_result(
            "patch", {"mode": "patch", "patch": patch_text}, tmp_path,
            result={"success": True, "diff": "--- a/x.py\n+++ b/x.py"},
        ),
        root=state_root,
    )


# ── H-A: el snapshot previo vive FUERA del ledger (efímero, privado) ─────────


def test_ha1_pre_post_patch_ledger_never_stores_file_content_and_snap_is_private(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """H-A: tras pre+post de un patch sobre un archivo con un secreto, el JSONL
    del ledger NO contiene el secreto (solo huellas); el contenido previo vive
    SOLO en el snapshot efímero fuera del ledger, con archivo 0600 y
    directorio 0700."""
    target = tmp_path / "secrets.py"
    target.write_text("API_TOKEN = '%s'\n" % SECRETO_R7, encoding="utf-8")
    patch_text = _v4a(
        "*** Update File: secrets.py",
        "@@",
        "-API_TOKEN = '%s'" % SECRETO_R7,
        "+API_TOKEN = 'rotado'",
    )

    code, _ = mods.guard.handle(
        _post_event("read_file", {"path": str(target)}, tmp_path), root=state_root
    )
    assert code == 0
    code, payload = mods.guard.handle(
        make_v4a_event(patch_text, tmp_path), root=state_root
    )
    assert code == 0, payload

    # tras el PRE: el snapshot existe, fuera del ledger y con permisos privados
    snaps = list((state_root / "snapshots").rglob("*.snap"))
    assert len(snaps) == 1, (
        "el pre debe dejar exactamente un snapshot efímero: %r" % (snaps,)
    )
    assert (snaps[0].stat().st_mode & 0o777) == 0o600, (
        "el archivo de snapshot debe ser 0600: %o"
        % (snaps[0].stat().st_mode & 0o777,)
    )
    assert (snaps[0].parent.stat().st_mode & 0o777) == 0o700, (
        "el directorio de snapshots de la sesión debe ser 0700: %o"
        % (snaps[0].parent.stat().st_mode & 0o777,)
    )
    assert SECRETO_R7 in snaps[0].read_text(encoding="utf-8", errors="replace"), (
        "el contenido previo debe vivir SOLO en el snapshot efímero"
    )

    # la tool aplicó el parche; llega el post ok
    target.write_text("API_TOKEN = 'rotado'\n", encoding="utf-8")
    code, _ = _h7_v4a_post_ok(mods, state_root, tmp_path, patch_text)
    assert code == 0
    assert mods.state.last_seen(SESSION, str(target), root=state_root) is not None

    # tras pre+post: el JSONL del ledger NO contiene el secreto sembrado
    ledgers = list(state_root.glob("*.jsonl"))
    assert ledgers, "la sesión debe haber escrito su ledger"
    for ledger in ledgers:
        assert SECRETO_R7 not in ledger.read_text(encoding="utf-8", errors="replace"), (
            "el ledger JSONL persistente (retención 7 días) jamás debe contener "
            "contenido de archivo: %s" % ledger.name
        )


def test_ha2_snap_file_removed_after_consuming_post(state_root, enforce, tmp_path):
    mods = load_modules()
    """H-A: el post que consume el snapshot (certificación del patch) DEBE
    borrar el archivo .snap: no quedan residuos de contenido en disco."""
    target = tmp_path / "app.py"
    target.write_text("a = 1\n", encoding="utf-8")
    patch_text = _v4a("*** Update File: app.py", "@@", "-a = 1", "+a = 22")

    _h7_read_and_pre(mods, state_root, tmp_path, target, patch_text)
    assert list((state_root / "snapshots").rglob("*.snap")), (
        "el pre debe dejar el snapshot efímero antes del post"
    )

    target.write_text("a = 22\n", encoding="utf-8")  # la tool aplicó el parche
    code, _ = _h7_v4a_post_ok(mods, state_root, tmp_path, patch_text)
    assert code == 0
    assert mods.state.last_seen(SESSION, str(target), root=state_root) is not None

    assert list((state_root / "snapshots").rglob("*.snap")) == [], (
        "el post que consume el snapshot debe borrar el .snap"
    )


def test_ha3_prune_sweeps_orphan_snap_older_than_ttl(state_root, tmp_path):
    mods = load_modules()
    """H-A: un .snap huérfano (crash antes del post) con mtime anterior al TTL
    corto (SNAP_TTL_S) lo elimina la poda existente; los snapshots dentro del
    TTL sobreviven."""
    target = tmp_path / "app.py"
    target.write_text("a = 1\n", encoding="utf-8")
    snap_dir = mods.state.snapshots_dir(SESSION, state_root)
    snap_dir.mkdir(parents=True, exist_ok=True)
    fresh = snap_dir / "fresco.snap"
    fresh.write_text("nuevo\n", encoding="utf-8")
    orphan = snap_dir / "huerfano.snap"
    orphan.write_text("viejo\n", encoding="utf-8")
    past = time.time() - (mods.state.SNAP_TTL_S + 60)
    ost = orphan.stat()
    os.utime(orphan, ns=(int(past * 1e9), int(past * 1e9)))
    assert orphan.stat().st_mtime < fresh.stat().st_mtime

    # la poda oportunista solo dispara si el ledger lleva > PRUNE_IDLE_S sin
    # tocar: se envejece el mtime del ledger como hace el test H3.
    mods.state.record(SESSION, "read_file", str(target), root=state_root)
    ledger = mods.state.ledger_path(SESSION, state_root)
    past_ledger = time.time() - (mods.state.PRUNE_IDLE_S + 60)
    os.utime(ledger, ns=(int(past_ledger * 1e9), int(past_ledger * 1e9)))

    mods.state.record(SESSION, "write_file", str(target), root=state_root)

    assert not orphan.exists(), (
        "la poda debe barrer el .snap huérfano con mtime anterior a SNAP_TTL_S"
    )
    assert fresh.exists(), (
        "el snapshot dentro del TTL no debe ser barrido"
    )


# ── H-B: fail-closed real cuando la reconstrucción no es verificable ─────────


def test_hb1_v4a_hunk_not_at_start_with_third_party_overwrite_fails_closed(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """H-B: patch V4A válido cuyo hunk NO empieza en la primera línea del
    archivo (reconstrucción no determinista) + un tercero sobrescribe antes
    del post: el post NO registra nada (anota 'write_unverifiable') y el pre
    posterior se bloquea (exit 2) en vez de dejar pasar la edición a ciegas."""
    target = tmp_path / "app.py"
    target.write_text("a = 1\nb = 2\n", encoding="utf-8")
    patch_text = _v4a("*** Update File: app.py", "@@", " b = 2", "+b = 22")
    seen_fp = _h7_read_and_pre(mods, state_root, tmp_path, target, patch_text)

    # la tool reportó éxito, PERO un tercero pisó el archivo antes del post
    target.write_text("TERCERO = 999\n", encoding="utf-8")
    code, _ = _h7_v4a_post_ok(mods, state_root, tmp_path, patch_text)
    assert code == 0

    last = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert last is None or (last["mtime_ns"], last["size"]) == seen_fp, (
        "la reconstrucción no verificable NO debe certificar la huella de disco "
        "(potencialmente ajena): %r" % (last,)
    )
    assert has_event(ledger_events(mods, state_root), "write_unverifiable"), (
        "la reconstrucción fallida debe anotarse como 'write_unverifiable': %r"
        % (ledger_events(mods, state_root),)
    )

    code2, payload2 = mods.guard.handle(
        make_v4a_event(
            _v4a("*** Update File: app.py", "@@", "-TERCERO = 999", "+x = 1"),
            tmp_path,
        ),
        root=state_root,
    )
    assert code2 == 2, (
        "sin certificación de la escritura, el patch sobre contenido no visto "
        "debe bloquearse: exit=%s payload=%r" % (code2, payload2)
    )
    assert payload2["decision"] == "block"


def test_hb2_snapshot_missing_at_post_fails_closed(state_root, enforce, tmp_path):
    mods = load_modules()
    """H-B: pendiente viva del pre PERO snapshot ausente para ese path al
    llegar el post (borrado a mano): fail-closed — no registra nada, anota
    'write_unverifiable' y el pre posterior se bloquea."""
    target = tmp_path / "app.py"
    target.write_text("a = 1\n", encoding="utf-8")
    patch_text = _v4a("*** Update File: app.py", "@@", "-a = 1", "+a = 22")
    seen_fp = _h7_read_and_pre(mods, state_root, tmp_path, target, patch_text)

    for snap in (state_root / "snapshots").rglob("*.snap"):
        snap.unlink()

    target.write_text("a = 22\n", encoding="utf-8")  # la tool aplicó el parche
    code, _ = _h7_v4a_post_ok(mods, state_root, tmp_path, patch_text)
    assert code == 0

    last = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert last is None or (last["mtime_ns"], last["size"]) == seen_fp, (
        "snapshot ausente para el path: no debe certificar la huella de disco: %r"
        % (last,)
    )
    assert has_event(ledger_events(mods, state_root), "write_unverifiable")

    code2, payload2 = mods.guard.handle(
        make_v4a_event(
            _v4a("*** Update File: app.py", "@@", "-a = 22", "+a = 333"), tmp_path
        ),
        root=state_root,
    )
    assert code2 == 2, payload2
    assert payload2["decision"] == "block"


def test_hb3_snapshot_unwritable_pre_makes_post_fail_closed(
    state_root, enforce, tmp_path, monkeypatch
):
    mods = load_modules()
    """H-A/H-B: si el snapshot no se puede escribir en el pre (permisos/ENOSPC,
    simulado), el post cae fail-closed: NO certifica la huella de disco, anota
    'write_unverifiable' y el pre posterior se bloquea."""
    monkeypatch.setattr(
        mods.state, "snapshot_write", lambda *a, **k: None, raising=False
    )
    target = tmp_path / "app.py"
    target.write_text("a = 1\n", encoding="utf-8")
    patch_text = _v4a("*** Update File: app.py", "@@", "-a = 1", "+a = 22")
    seen_fp = _h7_read_and_pre(mods, state_root, tmp_path, target, patch_text)

    target.write_text("a = 22\n", encoding="utf-8")  # la tool aplicó el parche
    code, _ = _h7_v4a_post_ok(mods, state_root, tmp_path, patch_text)
    assert code == 0

    last = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert last is None or (last["mtime_ns"], last["size"]) == seen_fp, (
        "sin snapshot el post no puede verificar: no debe certificar nada: %r"
        % (last,)
    )
    assert has_event(ledger_events(mods, state_root), "write_unverifiable")

    code2, payload2 = mods.guard.handle(
        make_v4a_event(
            _v4a("*** Update File: app.py", "@@", "-a = 22", "+a = 333"), tmp_path
        ),
        root=state_root,
    )
    assert code2 == 2, payload2
    assert payload2["decision"] == "block"


def test_hb4_replace_mode_unreconstructable_post_fails_closed(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """H-B (mode='replace'): con pendiente viva del pre pero old_string ajeno
    al snapshot (reconstrucción imposible) y disco pisado por un tercero, el
    post NO registra la huella de disco y el pre posterior se bloquea."""
    target = tmp_path / "app.py"
    target.write_text("a = 1\n", encoding="utf-8")
    code, _ = mods.guard.handle(
        _post_event("read_file", {"path": str(target)}, tmp_path), root=state_root
    )
    assert code == 0
    seen_fp = mods.state.last_seen(SESSION, str(target), root=state_root)
    seen_fp = (seen_fp["mtime_ns"], seen_fp["size"])

    pre = {
        "hook_event_name": "pre_tool_call",
        "tool_name": "patch",
        "tool_input": {
            "mode": "replace",
            "path": str(target),
            "old_string": "zzz = 0",  # ajeno al contenido del snapshot
            "new_string": "a = 2",
        },
        "session_id": SESSION,
        "cwd": str(tmp_path),
    }
    code, payload = mods.guard.handle(pre, root=state_root)
    assert code == 0, payload  # el pre permite (huella vigente)

    # la tool 'reportó éxito' pero un tercero pisó el archivo antes del post
    target.write_text("TERCERO = 1\n", encoding="utf-8")
    post = _post_event_with_result(
        "patch",
        {"mode": "replace", "path": str(target), "old_string": "zzz = 0",
         "new_string": "a = 2"},
        tmp_path,
        result={"success": True, "diff": "--- a/app.py\n+++ b/app.py"},
    )
    code, _ = mods.guard.handle(post, root=state_root)
    assert code == 0

    last = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert last is None or (last["mtime_ns"], last["size"]) == seen_fp, (
        "reconstrucción imposible con pendiente viva: no certificar el disco: %r"
        % (last,)
    )
    assert has_event(ledger_events(mods, state_root), "write_unverifiable")

    code2, payload2 = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )
    assert code2 == 2, payload2
    assert payload2["decision"] == "block"


# ══════════════════════════════════════════════════════════════════════════════
#  RONDA 9 — G1 (high): pendientes de TODAS las rutas V4A antes del retorno en
#  shadow; G2 (high): validación del resultado REAL de read_file antes de
#  promover la lectura.
# ══════════════════════════════════════════════════════════════════════════════


def _g1_three_files(tmp_path) -> dict:
    """Tres archivos existentes para un patch V4A multi-archivo."""
    files = {}
    for name, body in (
        ("a.py", "uno = 1\n"),
        ("b.py", "dos = 2\n"),
        ("c.py", "tres = 3\n"),
    ):
        p = tmp_path / name
        p.write_text(body, encoding="utf-8")
        files[name] = p
    return files


_G1_PATCH = _v4a(
    "*** Update File: a.py", "@@", "-uno = 1", "+uno = 11",
    "*** Update File: b.py", "@@", "-dos = 2", "+dos = 22",
    "*** Update File: c.py", "@@", "-tres = 3", "+tres = 33",
)


def _g1_read_only_first(mods, state_root, tmp_path, files):
    """El agente solo leyó a.py (el post ok registra su huella)."""
    code, _ = mods.guard.handle(
        _post_event("read_file", {"path": str(files["a.py"])}, tmp_path),
        root=state_root,
    )
    assert code == 0


def _g1_apply_patch(files):
    """La tool aplica el parche a las 3 rutas."""
    files["a.py"].write_text("uno = 11\n", encoding="utf-8")
    files["b.py"].write_text("dos = 22\n", encoding="utf-8")
    files["c.py"].write_text("tres = 33\n", encoding="utf-8")


def _g1_pre_v4a(mods, state_root, tmp_path, patch_text):
    return mods.guard.handle(
        {
            "hook_event_name": "pre_tool_call",
            "tool_name": "patch",
            "tool_input": {"mode": "patch", "patch": patch_text},
            "session_id": SESSION,
            "cwd": str(tmp_path),
        },
        root=state_root,
    )


def _g1_assert_first_certified(mods, state_root, files):
    """El primero (con pendiente y sha coincidente) SÍ queda registrado con la
    huella del disco pos-patch (reconstrucción verificada, no huella ciega)."""
    import hashlib as hashlib_mod

    seen_a = mods.state.last_seen(SESSION, str(files["a.py"]), root=state_root)
    assert seen_a is not None, (
        "la primera ruta (leída, pendiente viva, disco pos-patch coincidente) "
        "debe quedar certificada: %r" % (seen_a,)
    )
    st_a = files["a.py"].stat()
    assert (seen_a["mtime_ns"], seen_a["size"]) == (st_a.st_mtime_ns, st_a.st_size)
    assert seen_a.get("sha256") == hashlib_mod.sha256(
        files["a.py"].read_bytes()
    ).hexdigest()


def test_g1_shadow_v4a_race_on_path_without_pending_not_certified_and_blocks(
    state_root, monkeypatch, tmp_path
):
    mods = load_modules()
    """G1 (codex, high): en shadow, el pre de un patch V4A multi-archivo captura
    snapshot/pendiente de TODAS las rutas ANTES de decidir el retorno en la
    primera ruta no leída. Sin eso, la tercera ruta (sin pendiente) cae en el
    post al fallback legacy y certifica la huella de disco tal como esté en ese
    instante, aunque un tercero la haya sobrescrito tras el patch: al cambiar a
    enforce, el pre patch dejaría editar contenido que el agente nunca vio."""
    files = _g1_three_files(tmp_path)
    _g1_read_only_first(mods, state_root, tmp_path, files)

    code, _ = _g1_pre_v4a(mods, state_root, tmp_path, _G1_PATCH)
    assert code == 0  # shadow: no bloquea

    _g1_apply_patch(files)
    # carrera: un tercero sobrescribe c.py antes del post
    files["c.py"].write_text("TRES = SOBRESCRITO\n", encoding="utf-8")

    code, _ = mods.guard.handle(
        _post_event("patch", {"mode": "patch", "patch": _G1_PATCH}, tmp_path),
        root=state_root,
    )
    assert code == 0

    _g1_assert_first_certified(mods, state_root, files)
    # c.py NO queda registrado (fail-closed, jamás fallback legacy)
    assert mods.state.last_seen(SESSION, str(files["c.py"]), root=state_root) is None, (
        "la ruta sin pendiente con disco sobrescrito por un tercero NO debe "
        "certificarse por el fallback legacy: %r"
        % (mods.state.last_seen(SESSION, str(files["c.py"]), root=state_root),)
    )

    # cambio a enforce: el pre patch sobre c.py da exit 2 (la huella ajena
    # nunca entró al ledger) y sobre a.py sigue pasando (huella vigente)
    monkeypatch.setenv("READ_BEFORE_PATCH_MODE", "enforce")
    ev_c = _v4a("*** Update File: c.py", "@@", "-TRES = SOBRESCRITO", "+X = 1")
    code_c, payload_c = _g1_pre_v4a(mods, state_root, tmp_path, ev_c)
    assert code_c == 2, payload_c
    assert payload_c["decision"] == "block"
    ev_a = _v4a("*** Update File: a.py", "@@", "-uno = 11", "+uno = 111")
    code_a, payload_a = _g1_pre_v4a(mods, state_root, tmp_path, ev_a)
    assert code_a == 0, payload_a


def test_g1_shadow_v4a_race_on_second_file_not_registered_and_next_enforce_blocks(
    state_root, monkeypatch, tmp_path
):
    mods = load_modules()
    """G1 (escenario nominal de la ronda 8): shadow con 3 archivos, solo el
    primero leído, patch V4A exito, un tercero sobrescribe el SEGUNDO archivo
    antes del post -> el segundo NO queda registrado y tras cambiar a enforce
    el pre patch da exit 2; el primero (pendiente y sha coincidente) sí queda
    registrado."""
    files = _g1_three_files(tmp_path)
    _g1_read_only_first(mods, state_root, tmp_path, files)

    code, _ = _g1_pre_v4a(mods, state_root, tmp_path, _G1_PATCH)
    assert code == 0

    _g1_apply_patch(files)
    # carrera: un tercero sobrescribe el SEGUNDO archivo antes del post
    files["b.py"].write_text("B = SOBRESCRITO\n", encoding="utf-8")

    code, _ = mods.guard.handle(
        _post_event("patch", {"mode": "patch", "patch": _G1_PATCH}, tmp_path),
        root=state_root,
    )
    assert code == 0

    _g1_assert_first_certified(mods, state_root, files)
    assert mods.state.last_seen(SESSION, str(files["b.py"]), root=state_root) is None, (
        "el segundo archivo (disco sobrescrito por un tercero tras el patch) no "
        "debe quedar registrado: %r"
        % (mods.state.last_seen(SESSION, str(files["b.py"]), root=state_root),)
    )

    monkeypatch.setenv("READ_BEFORE_PATCH_MODE", "enforce")
    ev_b = _v4a("*** Update File: b.py", "@@", "-B = SOBRESCRITO", "+X = 1")
    code_b, payload_b = _g1_pre_v4a(mods, state_root, tmp_path, ev_b)
    assert code_b == 2, payload_b
    assert payload_b["decision"] == "block"


def test_g1_post_v4a_orphan_path_without_pending_fails_closed(
    state_root, monkeypatch, tmp_path
):
    mods = load_modules()
    """G1 fix (b): en el post V4A, 'sin pendiente por payload legacy' (cero
    pendientes de ESTA llamada) se distingue de 'sin pendiente por
    procesamiento incompleto' (la llamada trae 2+ rutas y hay pendientes para
    algunas pero no para todas): las huérfanas NO se certifican por el fallback
    legacy; se anota 'write_unverifiable' (fail-closed)."""
    p1 = tmp_path / "uno.py"
    p2 = tmp_path / "dos.py"
    p1.write_text("uno = 1\n", encoding="utf-8")
    p2.write_text("dos = 2\n", encoding="utf-8")

    # pre SIMULADO incompleto: solo p1 obtuvo snapshot/pendiente (el pre fue
    # interrumpido tras la primera ruta del parche multi-archivo)
    call_id = "call-g1-orphan"
    mtime_ns, size = mods.state.fingerprint(str(p1))
    snap = mods.state.snapshot_write(SESSION, str(p1), root=state_root, call_id=call_id)
    assert snap
    fields = {
        "path": str(p1),
        "mtime_ns": mtime_ns,
        "size": size,
        "snap": snap,
        "call_id": call_id,
    }
    pre_sha = mods.state.file_digest(str(p1))
    if pre_sha:
        fields["pre_sha256"] = pre_sha
    mods.state.log_event(SESSION, "write_pending", root=state_root, **fields)

    patch = _v4a(
        "*** Update File: uno.py", "@@", "-uno = 1", "+uno = 11",
        "*** Update File: dos.py", "@@", "-dos = 2", "+dos = 22",
    )
    # la tool aplica el parche a ambas rutas
    p1.write_text("uno = 11\n", encoding="utf-8")
    p2.write_text("dos = 22\n", encoding="utf-8")

    post = _event_with_call_id(
        _post_event("patch", {"mode": "patch", "patch": patch}, tmp_path), call_id
    )
    code, _ = mods.guard.handle(post, root=state_root)
    assert code == 0

    seen1 = mods.state.last_seen(SESSION, str(p1), root=state_root)
    assert seen1 is not None, (
        "la ruta CON pendiente y disco coincidente debe certificarse: %r" % (seen1,)
    )
    assert mods.state.last_seen(SESSION, str(p2), root=state_root) is None, (
        "la ruta huérfana (sin pendiente pero dentro de una llamada con otras "
        "pendientes) NO debe certificarse por el fallback legacy: %r"
        % (mods.state.last_seen(SESSION, str(p2), root=state_root),)
    )
    assert has_event(ledger_events(mods, state_root), "write_unverifiable")

    monkeypatch.setenv("READ_BEFORE_PATCH_MODE", "enforce")
    ev_p2 = _v4a("*** Update File: dos.py", "@@", "-dos = 22", "+X = 1")
    code_p2, payload_p2 = _g1_pre_v4a(mods, state_root, tmp_path, ev_p2)
    assert code_p2 == 2, payload_p2
    assert payload_p2["decision"] == "block"


def _g2_read_post(mods, state_root, tmp_path, target, result):
    """Pre de read_file + post con status 'ok' y extra.result dado (JSON dict)."""
    code, _ = mods.guard.handle(
        make_event("pre_tool_call", "read_file", target, tmp_path), root=state_root
    )
    assert code == 0
    post = _post_event("read_file", {"path": str(target)}, tmp_path)
    post["extra"] = {"status": "ok", "result": json.dumps(result)}
    code, _ = mods.guard.handle(post, root=state_root)
    assert code == 0


def test_g2_post_read_file_result_error_discards_pending_and_next_patch_blocks(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """G2 (codex, high): el post de read_file con status 'ok' pero resultado
    real con error NO promueve la pendiente: la descarta (state.pending_discard),
    no registra nada y el patch posterior da exit 2. El reintento de lectura
    idéntico SÍ registra (la pendiente viciada ya no ensucia el empareje)."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    _g2_read_post(mods, state_root, tmp_path, target, {"error": "boom"})

    assert mods.state.last_seen(SESSION, str(target), root=state_root) is None, (
        "una lectura que devolvió error no entregó contenido: no debe registrar "
        "la ruta: %r"
        % (mods.state.last_seen(SESSION, str(target), root=state_root),)
    )

    code2, payload2 = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )
    assert code2 == 2, payload2
    assert payload2["decision"] == "block"

    # reintento de lectura idéntico (mismo payload -> mismo call_id derivado):
    # el post ok con contenido real SÍ registra, porque la pendiente viciada
    # fue descartada (sin discard habría DOS pendientes con el mismo call_id y
    # el empareje sería ambiguo)
    target.write_text("value = 2\n", encoding="utf-8")
    _g2_read_post(
        mods, state_root, tmp_path, target, {"content": "value = 2\n", "total_lines": 1}
    )
    seen = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert seen is not None, (
        "el reintento exitoso debe registrar la huella (pendiente viciada ya "
        "descartada): %r" % (seen,)
    )


def test_g2_post_read_file_result_not_found_discards_pending_and_next_patch_blocks(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """G2: post de read_file status 'ok' con resultado real not_found=True
    (ReadResult.to_dict de una ruta ausente) tampoco promueve la pendiente: no
    registra y el patch posterior se bloquea (exit 2)."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    _g2_read_post(mods, state_root, tmp_path, target, {"not_found": True})

    assert mods.state.last_seen(SESSION, str(target), root=state_root) is None, (
        "una lectura not_found no vio contenido: no debe registrar la ruta: %r"
        % (mods.state.last_seen(SESSION, str(target), root=state_root),)
    )

    code2, payload2 = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )
    assert code2 == 2, payload2
    assert payload2["decision"] == "block"


def test_g2_post_read_file_result_content_registers_and_patch_allowed(
    state_root, enforce, tmp_path
):
    mods = load_modules()
    """G2 (no romper CA2): post de read_file status 'ok' con resultado real
    normal {'content': ...} promueve la pendiente como siempre y el patch
    posterior pasa (exit 0)."""
    target = tmp_path / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    _g2_read_post(
        mods, state_root, tmp_path, target, {"content": "value = 1\n", "total_lines": 1}
    )

    seen = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert seen is not None, "una lectura exitosa debe registrar la ruta"
    st = target.stat()
    assert (seen["mtime_ns"], seen["size"]) == (st.st_mtime_ns, st.st_size)

    code, payload = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )
    assert code == 0, payload
    assert payload.get("decision") != "block"


# ── Ronda 10: resultado real de write_file + digest de la lectura promovida ──


def test_h1_write_file_result_error_not_recorded_and_patch_blocks(state_root, enforce, tmp_path):
    """Ronda 10 / H1 (codex, high): post de write_file status 'ok' con
    WriteResult {'error': ...} NO registra aunque el contenido en disco coincida
    con tool_input['content']: la tool no escribió; un patch posterior se bloquea."""
    mods = load_modules()
    target = tmp_path / "app.py"
    intent = "value = 1\n"
    target.write_text(intent, encoding="utf-8")

    ev = _post_event_with_result(
        "write_file", {"path": str(target), "content": intent}, tmp_path,
        result={"bytes_written": 0, "error": "permission denied"},
    )
    code, _ = mods.guard.handle(ev, root=state_root)
    assert code == 0

    assert mods.state.last_seen(SESSION, str(target), root=state_root) is None, (
        "una escritura con error no vio/escribió contenido: no debe registrar: %r"
        % (mods.state.last_seen(SESSION, str(target), root=state_root),)
    )
    code2, payload2 = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )
    assert code2 == 2, payload2
    assert payload2["decision"] == "block"


def test_h1_write_file_result_verified_none_still_records(state_root, enforce, tmp_path):
    """Ronda 10 / H1 (no romper CA4): WriteResult sin 'success' (verified omitido
    porque el backend no pudo verificar) sigue certificando por intención."""
    mods = load_modules()
    target = tmp_path / "app.py"
    intent = "value = 1\n"
    target.write_text(intent, encoding="utf-8")

    ev = _post_event_with_result(
        "write_file", {"path": str(target), "content": intent}, tmp_path,
        result={"bytes_written": len(intent)},
    )
    code, _ = mods.guard.handle(ev, root=state_root)
    assert code == 0
    assert mods.state.last_seen(SESSION, str(target), root=state_root) is not None

    code2, payload2 = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )
    assert code2 == 0, payload2


def test_h2_read_post_digest_same_fingerprint_still_blocks_edit(state_root, enforce, tmp_path):
    """Ronda 10 / H2 (codex, high): el archivo cambia entre la lectura y el post
    conservando size y mtime (utime restaurado). El post promueve la huella DEL
    PRE (TOCTOU) y AHORA también el digest de lo leído; el pre de la edición
    desempata por digest y bloquea aunque (mtime,size) coincidan."""
    import hashlib as hashlib_mod
    import os as os_mod

    mods = load_modules()
    target = tmp_path / "app.py"
    read_text = "value = 1\n"
    target.write_text(read_text, encoding="utf-8")
    st = target.stat()

    code, _ = mods.guard.handle(
        make_event("pre_tool_call", "read_file", target, tmp_path), root=state_root
    )
    assert code == 0

    target.write_text("valuE = 1\n", encoding="utf-8")  # mismo tamaño, otro contenido
    os_mod.utime(str(target), ns=(st.st_atime_ns, st.st_mtime_ns))
    st2 = target.stat()
    assert (st2.st_size, st2.st_mtime_ns) == (st.st_size, st.st_mtime_ns), (
        "el escenario exige huella (size, mtime_ns) IDÉNTICA"
    )

    post = _post_event("read_file", {"path": str(target)}, tmp_path)
    post["extra"] = {"status": "ok", "result": json.dumps({"content": read_text})}
    code, _ = mods.guard.handle(post, root=state_root)
    assert code == 0

    seen = mods.state.last_seen(SESSION, str(target), root=state_root)
    assert seen is not None, "el post debe promover la huella del pre (TOCTOU intacto)"
    assert seen["sha256"] == hashlib_mod.sha256(read_text.encode("utf-8")).hexdigest(), (
        "la entrada debe llevar el digest de lo LEÍDO, no el del disco actual: %r" % (seen,)
    )
    assert (seen["mtime_ns"], seen["size"]) == (st.st_mtime_ns, st.st_size), seen

    code2, payload2 = mods.guard.handle(
        make_event("pre_tool_call", "patch", target, tmp_path), root=state_root
    )
    assert code2 == 2, payload2
    assert payload2["decision"] == "block"
