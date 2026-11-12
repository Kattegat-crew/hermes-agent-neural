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
import sys
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
