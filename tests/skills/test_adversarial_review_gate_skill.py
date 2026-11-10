"""Tests for the adversarial-review-gate skill.

The gate is the only thing standing between a buggy diff and a commit, so its
failure modes are tested by behaviour, not by mocking the thing under test: the
reviewer is stubbed (it is another process), git is real (a throwaway repo), and
the receipt store is a tmp dir.

Regression coverage is aimed at the bugs this gate shipped and then had to fix:
fail-open on a missing verdict, a cache hit that bypassed required tests, and
flag injection through --range.
"""
import json
import importlib.machinery
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "software-development"
    / "adversarial-review-gate"
)
GATE = SKILL_DIR / "scripts" / "review_gate.py"


def load_gate():
    loader = importlib.machinery.SourceFileLoader("review_gate_mod", str(GATE))
    spec = importlib.util.spec_from_loader("review_gate_mod", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture()
def gate(tmp_path, monkeypatch):
    module = load_gate()
    monkeypatch.setattr(module, "STATE", tmp_path / "state")
    monkeypatch.setattr(module, "SCHEMA_PATH", tmp_path / "schema.json")
    return module


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test")
    (repo / "base.py").write_text("x = 1\n")
    git("add", "-A")
    git("commit", "-m", "base")
    return repo


def run(gate, monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["review_gate", *argv])
    return gate.main()


def diff_lines(*added: str, path: str = "mod.py") -> str:
    head = f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -0,0 +1,{len(added)} @@\n"
    return head + "".join(f"+{line}\n" for line in added)


class TestStaticScan:
    def test_detects_command_injection(self, gate):
        found = gate.static_findings(diff_lines("    subprocess.run(cmd, shell=True)"))  # review-gate:ignore)
        assert [f["rule"] for f in found] == ["shell-true"]
        assert found[0]["severity"] == "critical"

    def test_detects_interpolated_sql(self, gate):
        source = "    cur.execute(\"SELECT * FROM t WHERE id = '%s'\" % uid)"  # review-gate:ignore
        assert "sql-percent" in [f["rule"] for f in gate.static_findings(diff_lines(source))]

    def test_detects_hardcoded_secret(self, gate):
        source = "api_key = 'sk_live_abc123456789'"  # review-gate:ignore
        assert "secret-literal" in [f["rule"] for f in gate.static_findings(diff_lines(source))]

    def test_detects_swallowed_exception_on_one_line(self, gate):
        found = gate.static_findings(diff_lines("    except Exception: pass"))
        assert [f["rule"] for f in found] == ["except-swallow"]

    def test_multiline_shell_true_is_detected(self, gate):
        lines = ("    subprocess.run(", "        args,", "        shell=True,", "    )")  # review-gate:ignore
        rules = [f["rule"] for f in gate.static_findings(diff_lines(*lines))]
        assert "shell-true" in rules

    def test_python_octal_permissions_are_detected(self, gate):
        rules = [f["rule"] for f in gate.static_findings(diff_lines("    os.chmod(path, 0o777)"))]  # review-gate:ignore
        assert "chmod-777" in rules

    def test_pattern_tables_do_not_flag_themselves(self, gate):
        rule_row = '    ("os-system", r"\\bos\\.system\\s*\\(", "high", "msg"),'
        assert gate.static_findings(diff_lines(rule_row)) == []

    def test_non_ascii_paths_are_still_scanned(self, gate):
        found = gate.static_findings(diff_lines("    subprocess.run(c, shell=True)", path="a/\u00f1andu.py"))  # review-gate:ignore
        assert [f["rule"] for f in found] == ["shell-true"]

    def test_documentation_is_never_scanned(self, gate):
        doc_line = "Configura el flag TLS fino solo si confias en el endpoint."  # review-gate:ignore
        doc = diff_lines(doc_line, path="SKILL.md")
        assert gate.static_findings(doc) == []
        assert not gate.scannable("SKILL.md")
        assert gate.scannable("mod.py")

    def test_inline_suppression_is_honoured(self, gate):
        line = "    subprocess.run(cmd, shell=True)  # review-gate:ignore"
        assert gate.static_findings(diff_lines(line)) == []

    def test_removed_and_context_lines_are_ignored(self, gate):
        diff = "--- a/m.py\n+++ b/m.py\n@@ -1,2 +1,1 @@\n-old = f(shell=True)\n keep = 1\n"  # review-gate:ignore
        assert gate.static_findings(diff) == []


class TestClassification:
    @pytest.mark.parametrize("path", ["app.py", "src/main.ts", "deploy/x.yml", "bin/run"])
    def test_code_paths(self, gate, path):
        assert gate.is_code([path])

    @pytest.mark.parametrize("path", ["README.md", "docs/x.txt", ".gitignore", "LICENSE"])
    def test_non_code_paths(self, gate, path):
        assert not gate.is_code([path])

    def test_sensitive_path_escalates(self, gate):
        hot, why = gate.blast_radius(["app/auth/login.py"], "+x\n")
        assert hot and "sensibles" in why

    def test_large_diff_escalates(self, gate):
        hot, why = gate.blast_radius(["app/util.py"], "+x\n" * 500)
        assert hot and "grande" in why

    def test_small_plain_diff_does_not_escalate(self, gate):
        hot, _ = gate.blast_radius(["app/util.py"], "+x\n" * 10)
        assert not hot

    def test_fingerprint_ignores_line_numbers(self, gate):
        a = gate.fingerprint({"severity": "high", "issue": "falla en linea 42 del parser"})
        b = gate.fingerprint({"severity": "high", "issue": "falla en linea 99 del parser"})
        assert a == b


class TestRangeValidation:
    @pytest.mark.parametrize("rng", ["main..HEAD", "abc123", "origin/main..feature/x"])
    def test_accepts_refs(self, gate, rng):
        assert gate.RANGE_RE.match(rng)

    @pytest.mark.parametrize("rng", ["--output=/etc/passwd", "-o x", "main..HEAD --exec=x"])
    def test_rejects_flag_injection(self, gate, rng):
        assert not (gate.RANGE_RE.match(rng) and not rng.startswith("-"))


class TestVerdictPath:
    """The gate must never say yes on its own."""

    def test_static_finding_blocks_without_calling_the_reviewer(self, gate, tmp_path, monkeypatch):
        repo = make_repo(tmp_path)
        bad = "import subprocess\nsubprocess.run(c, shell=True)\n"  # review-gate:ignore
        (repo / "bad.py").write_text(bad)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)

        def explode(*_a, **_k):
            raise AssertionError("the reviewer must not run when static scanning already blocks")

        monkeypatch.setattr(gate, "call_reviewer", explode)
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged"]) == 2

    def test_missing_verdict_is_fail_closed(self, gate, tmp_path, monkeypatch):
        repo = make_repo(tmp_path)
        (repo / "ok.py").write_text("def add(a, b):\n    return a + b\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        monkeypatch.setattr(
            gate, "call_reviewer", lambda *_a, **_k: (None, {"model": "x", "seconds": 0.1, "error": "429"})
        )
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged"]) == 2

    def test_degraded_can_be_waived_explicitly(self, gate, tmp_path, monkeypatch):
        repo = make_repo(tmp_path)
        (repo / "ok.py").write_text("def add(a, b):\n    return a + b\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        monkeypatch.setattr(
            gate, "call_reviewer", lambda *_a, **_k: (None, {"model": "x", "seconds": 0.1, "error": "429"})
        )
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged", "--allow-degraded"]) == 0

    def test_a_low_finding_must_not_suppress_the_reviewer(self, gate, tmp_path, monkeypatch):
        """Un print de depuracion no puede sustituir la revision del diff."""
        repo = make_repo(tmp_path)
        (repo / "ok.py").write_text('def f():\n    print("debug: hola")\n')
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        called = {"n": 0}

        def reviewer(*_a, **_k):
            called["n"] += 1
            return ({"passed": True, "blocking": [], "summary": "ok"}, {"model": "fake", "seconds": 0.1})

        monkeypatch.setattr(gate, "call_reviewer", reviewer)
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged"]) == 0
        assert called["n"] == 1, "un hallazgo low no puede saltarse la revision adversarial"

    def test_docs_only_diff_skips_everything(self, gate, tmp_path, monkeypatch):
        repo = make_repo(tmp_path)
        (repo / "NOTES.md").write_text("hola\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)

        def explode(*_a, **_k):
            raise AssertionError("a docs-only diff must not reach the reviewer")

        monkeypatch.setattr(gate, "call_reviewer", explode)
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged"]) == 0


class TestStopOnPolicy:
    """--stop-on decide que severidades bloquean sin hacer desaparecer el resto."""

    def test_downgraded_severities_are_kept_as_advisories(self, gate, tmp_path, monkeypatch):
        repo = make_repo(tmp_path)
        (repo / "ok.py").write_text("def add(a, b):\n    return a + b\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        verdict = {
            "passed": True,
            "blocking": [{"severity": "high", "file": "ok.py", "line": 1, "issue": "x", "fix": "y"}],
            "non_blocking": [],
            "tests_adequate": True,
            "summary": "ok",
        }
        monkeypatch.setattr(
            gate, "call_reviewer",
            lambda *_a, **_k: (verdict, {"engine": "fake", "model": "fake", "seconds": 0.1}),
        )
        assert run(gate, monkeypatch,
                   ["--repo", str(repo), "--staged", "--stop-on", "critical"]) == 0
        latest = sorted(gate.STATE.glob("*/latest.json"))[-1]
        receipt = json.loads(latest.read_text())
        assert receipt["decision"] == "pass"
        assert len(receipt["non_blocking"]) == 1, "lo degradado debe seguir en el receipt"

    def test_invalid_stop_on_is_a_usage_error(self, gate, tmp_path, monkeypatch):
        repo = make_repo(tmp_path)
        with pytest.raises(SystemExit) as exc:
            run(gate, monkeypatch, ["--repo", str(repo), "--staged", "--stop-on", "urgente"])
        assert exc.value.code == 4, "un --stop-on invalido no puede confundirse con un bloqueo (2)"


class TestReviewerVerdictIsAuthoritative:
    """A rejection without an itemised reason is still a rejection."""

    def _repo_with_clean_change(self, tmp_path):
        repo = make_repo(tmp_path)
        (repo / "ok.py").write_text("def add(a, b):\n    return a + b\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        return repo

    def test_passed_false_without_findings_blocks(self, gate, tmp_path, monkeypatch):
        repo = self._repo_with_clean_change(tmp_path)
        verdict = {"passed": False, "blocking": [], "summary": "no me convence"}
        monkeypatch.setattr(
            gate, "call_reviewer", lambda *_a, **_k: (verdict, {"model": "fake", "seconds": 0.1})
        )
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged"]) == 2

    def test_inadequate_tests_are_advisory_not_veto(self, gate, tmp_path, monkeypatch):
        """El reviewer opina sin nombrar qué falta: bloquear sobre eso cierra un bucle."""
        repo = self._repo_with_clean_change(tmp_path)
        verdict = {"passed": True, "blocking": [], "tests_adequate": False, "summary": "ok"}
        monkeypatch.setattr(
            gate, "call_reviewer", lambda *_a, **_k: (verdict, {"model": "fake", "seconds": 0.1})
        )
        assert run(
            gate, monkeypatch,
            ["--repo", str(repo), "--staged", "--test-cmd", "true", "--require-tests"],
        ) == 0


class TestWorkModeWithoutCommits:
    def test_work_mode_survives_an_unborn_branch(self, gate, tmp_path, monkeypatch):
        repo = tmp_path / "fresh"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        (repo / "bad.py").write_text("import subprocess\nsubprocess.run(c, shell=True)\n")  # review-gate:ignore
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)

        def explode(*_a, **_k):
            raise AssertionError("static findings must block before the reviewer")

        monkeypatch.setattr(gate, "call_reviewer", explode)
        assert run(gate, monkeypatch, ["--repo", str(repo), "--work"]) == 2


class TestStateRobustness:
    """El estado en disco nunca puede tumbar el gate ni bloquear un diff para siempre."""

    def test_corrupt_receipt_is_a_cache_miss(self, gate, tmp_path):
        bad = tmp_path / "receipt.json"
        bad.write_text("{ esto no es json")
        assert gate.load_receipt(bad) is None
        missing = tmp_path / "no-existe.json"
        assert gate.load_receipt(missing) is None

    def test_receipt_write_is_atomic(self, gate, tmp_path):
        target = tmp_path / "r.json"
        gate.write_atomic(target, {"decision": "pass"})
        assert gate.load_receipt(target) == {"decision": "pass"}
        assert not [p for p in tmp_path.iterdir() if ".tmp" in p.name], "no debe quedar temporal"

    def test_review_id_varies_with_model(self, gate, tmp_path, monkeypatch):
        repo = make_repo(tmp_path)
        (repo / "ok.py").write_text("def add(a, b):\n    return a + b\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        called = {"n": 0}

        def reviewer(*_a, **_k):
            called["n"] += 1
            return ({"passed": True, "blocking": [], "summary": "ok"}, {"model": "fake", "seconds": 0.1})

        monkeypatch.setattr(gate, "call_reviewer", reviewer)
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged", "--model", "m-a"]) == 0
        # mismo diff, otro modelo: el veredicto anterior no puede acreditarlo
        run(gate, monkeypatch, ["--repo", str(repo), "--staged", "--model", "m-b"])
        assert called["n"] == 2


class TestEngineRouting:
    """Elegir motor y modelo es parte del veredicto: cambia quién juzga."""

    def test_engine_spec_parsing(self, gate):
        eng = gate.review_engines
        assert eng.parse_engine_spec("codex:gpt-6-astra") == ("codex", "gpt-6-astra", None)
        assert eng.parse_engine_spec("agy") == ("agy", None, None)
        assert eng.parse_engine_spec("opencode:opencode/x-free:opencode") == (
            "opencode", "opencode/x-free", "opencode")

    def test_resolve_engine_defaults_and_auto(self, gate):
        class A:
            engine = None
            model = None
            provider = None
            no_escalate = False

        a = A()
        assert gate.resolve_engine(a, hot=False, why="")[0] == "agy"  # compatibilidad

        a.engine = "codex"
        a.model = "gpt-6-astra"
        assert gate.resolve_engine(a, hot=True, why="auth") == ("codex", "gpt-6-astra", None)

        a.engine = "auto"
        a.model = None
        hot_engine, hot_model, _ = gate.resolve_engine(a, hot=True, why="rutas sensibles")
        calm_engine, _, _ = gate.resolve_engine(a, hot=False, why="")
        assert hot_engine == "agy" and hot_model == "claude-opus-5-5-high"
        assert calm_engine == "codex"

        a.no_escalate = True
        assert gate.resolve_engine(a, hot=True, why="auth")[0] == "codex"

    def test_fallback_chain_is_parsed(self, gate):
        chain = gate.parse_fallbacks("codex:gpt-6-astra,opencode:opencode/x-free")
        assert chain == [("codex", "gpt-6-astra", None), ("opencode", "opencode/x-free", None)]

    def test_unknown_engine_is_an_error_not_a_crash(self, gate):
        verdict, meta = gate.review_engines.run_engine(
            "gemini-cli", Path("."), "prompt", Path("schema.json"))
        assert verdict is None
        assert "motor desconocido" in meta["error"]

    def test_fallback_is_used_when_the_first_engine_fails(self, gate, tmp_path, monkeypatch):
        repo = make_repo(tmp_path)
        (repo / "ok.py").write_text("def add(a, b):\n    return a + b\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)

        calls = []

        def fake_engine(engine, repo_, prompt, schema, model=None, provider=None, timeout=900):
            calls.append(engine)
            if engine == "agy":
                return None, {"engine": "agy", "model": model, "error": "429 quota"}
            return ({"passed": True, "blocking": [], "summary": "ok"},
                    {"engine": engine, "model": model, "seconds": 0.1})

        monkeypatch.setattr(gate.review_engines, "run_engine", fake_engine)
        rc = run(gate, monkeypatch, ["--repo", str(repo), "--staged",
                                     "--engine", "agy",
                                     "--fallback", "codex:gpt-6-astra"])
        assert rc == 0
        assert calls == ["agy", "codex"]


class TestVerdictCannotBeFabricated:
    """Un veredicto incompleto no puede convertirse en una aprobacion."""

    def test_empty_object_is_not_a_pass(self, gate):
        assert gate.review_engines.normalize_verdict({}) is None

    def test_missing_passed_is_not_a_pass(self, gate):
        assert gate.review_engines.normalize_verdict({"blocking": []}) is None

    def test_dropped_structure_does_not_become_a_pass(self, gate):
        # `blocking` con datos raros: antes se descartaban y quedaba passed=true
        v = gate.review_engines.normalize_verdict({"passed": True, "blocking": [123, None, ""]})
        assert v is not None and v["passed"] is False
        assert len(v["blocking"]) == 3, "ningun hallazgo, ni el invalido, puede desaparecer"

    def test_non_blocking_wrong_type_does_not_raise(self, gate):
        for bad in (1, True, "texto", {"a": 1}):
            v = gate.review_engines.normalize_verdict(
                {"passed": True, "blocking": [], "non_blocking": bad})
            assert v is not None and v["non_blocking"] == []

    def test_finding_without_text_is_not_discarded(self, gate):
        v = gate.review_engines.normalize_verdict(
            {"passed": False, "blocking": [{"severity": "high", "description": "inyeccion"}]})
        assert len(v["blocking"]) == 1
        assert "inyeccion" in v["blocking"][0]["issue"]

    def test_passed_true_with_blocking_is_downgraded(self, gate):
        v = gate.review_engines.normalize_verdict(
            {"passed": True, "blocking": [{"severity": "medium", "issue": "x", "fix": "y"}]})
        assert v["passed"] is False, "un veredicto incoherente no puede aprobar"

    def test_opencode_stream_with_non_object_events(self, gate, tmp_path, monkeypatch):
        eng = gate.review_engines
        stream = "\n".join([
            "null", "[]", "42",
            '{"type":"text","part":"error"}',
            '{"type":"text","part":{"type":"text","text":"{\\"passed\\": true, \\"blocking\\": [], \\"summary\\": \\"ok\\"}"}}',
        ])
        monkeypatch.setattr(eng, "_sh", lambda *a, **k: (0, stream, ""))
        verdict, meta = eng.run_opencode(tmp_path, "p", "opencode/x-free", None, 60)
        assert verdict is not None and verdict["passed"] is True

    def test_agy_still_escalates_without_engine_flag(self, gate):
        class A:
            engine = None
            model = None
            provider = None
            no_escalate = False

        a = A()
        _, model, _ = gate.resolve_engine(a, hot=True, why="auth")
        assert model == gate.ESCALATED_MODEL, "sin --engine, agy debe seguir escalando"
        a.no_escalate = True
        assert gate.resolve_engine(a, hot=True, why="auth")[1] is None

    def test_string_findings_keep_their_signal(self, gate):
        v = gate.review_engines.normalize_verdict(
            {"passed": False, "blocking": ["CRITICAL: inyeccion de comandos"]})
        assert v["blocking"][0]["severity"] == "critical"


class TestFallbackBudget:
    def test_chain_shares_one_deadline(self, gate, monkeypatch):
        """El presupuesto es de la cadena: ningun intento recibe mas que el tiempo restante."""
        clock = {"t": 1000.0}
        seen = []

        def fake_engine(engine, repo, prompt, schema, model=None, provider=None, timeout=900):
            seen.append(timeout)
            clock["t"] += 20  # este motor consume 20s
            return None, {"engine": engine, "model": model, "error": "cuota"}

        monkeypatch.setattr(gate.time, "monotonic", lambda: clock["t"])
        monkeypatch.setattr(gate.review_engines, "run_engine", fake_engine)
        gate.ACTIVE.update({"engine": "agy", "model": None, "provider": None,
                            "fallbacks": [("codex", None, None), ("opencode", None, None)]})
        gate.call_reviewer(Path("."), "p", timeout=50)

        assert len(seen) == 2, f"debieron caber 2 intentos de 20s en 50s: {seen}"
        assert seen[1] <= 30, f"el segundo intento no heredo el presupuesto: {seen}"


class TestCodexAdapter:
    """codex corre como root en el host: jamas sin sandbox de solo lectura."""

    def test_codex_command_is_read_only_and_never_bypasses_approvals(self, gate, tmp_path, monkeypatch):
        eng = gate.review_engines
        repo = tmp_path / "r"
        repo.mkdir()
        schema = tmp_path / "s.json"
        schema.write_text("{}")
        seen = {}

        def fake_sh(cmd, cwd=None, timeout=120, env=None, input_text=None):
            seen["cmd"] = cmd
            # el adaptador espera encontrar el fichero de salida que codex escribe
            for arg in cmd:
                if "-o" in arg:
                    continue
            remote = cmd[-1]
            import re as _re
            m = _re.search(r"-o (\S+)", remote)
            if m:
                Path(m.group(1)).write_text('{"passed": true, "blocking": [], "non_blocking": [], "tests_adequate": true, "summary": "ok"}')
            return 0, "", ""

        monkeypatch.setattr(eng, "_sh", fake_sh)
        monkeypatch.setattr(eng, "SHARED_TMP", tmp_path / "shared")
        verdict, meta = eng.run_codex(repo, "prompt", schema, "gpt-6-astra", 60)

        remote = seen["cmd"][-1]
        assert "-s read-only" in remote
        assert "dangerously-bypass" not in remote
        assert "--output-schema" in remote
        assert verdict["passed"] is True
        assert meta["engine"] == "codex"

    def test_codex_missing_output_is_an_error(self, gate, tmp_path, monkeypatch):
        eng = gate.review_engines
        repo = tmp_path / "r"; repo.mkdir()
        schema = tmp_path / "s.json"; schema.write_text("{}")
        monkeypatch.setattr(eng, "_sh", lambda *a, **k: (0, "", ""))
        monkeypatch.setattr(eng, "SHARED_TMP", tmp_path / "shared")
        verdict, meta = eng.run_codex(repo, "p", schema, "gpt-6-astra", 30)
        assert verdict is None
        assert "no produjo mensaje final" in meta["error"]


class TestOpencodeAdapter:
    def test_stream_text_events_are_joined_and_parsed(self, gate, tmp_path, monkeypatch):
        eng = gate.review_engines
        verdict_json = '{"passed": false, "blocking": [], "summary": "mal"}'
        half = len(verdict_json) // 2
        events = [
            {"type": "step_start", "part": {"type": "step-start"}},
            {"type": "text", "part": {"type": "text", "text": verdict_json[:half]}},
            {"type": "text", "part": {"type": "text", "text": verdict_json[half:]}},
            {"type": "step_finish", "part": {"type": "step-finish"}},
        ]
        stream = "\n".join(json.dumps(e) for e in events)
        monkeypatch.setattr(eng, "_sh", lambda *a, **k: (0, stream, ""))
        verdict, meta = eng.run_opencode(tmp_path, "p", "opencode/x-free", None, 60)
        assert verdict["passed"] is False
        assert verdict["summary"] == "mal"
        assert meta["engine"] == "opencode"

    def test_invalid_json_in_the_stream_is_an_error(self, gate, tmp_path, monkeypatch):
        eng = gate.review_engines
        monkeypatch.setattr(eng, "_sh", lambda *a, **k: (0, '{"type":"text","part":{"type":"text","text":"no pienso responder json"}}', ""))
        verdict, meta = eng.run_opencode(tmp_path, "p", "opencode/x-free", None, 60)
        assert verdict is None
        assert "sin veredicto JSON" in meta["error"]

    def test_reviewer_that_writes_invalidates_its_verdict(self, gate, tmp_path, monkeypatch):
        """Si el reviewer toca el arbol, su veredicto no vale aunque diga que pasa."""
        eng = gate.review_engines
        state = {"n": 0}

        def fake_sh(cmd, cwd=None, timeout=120, env=None, input_text=None):
            if "status" in cmd:
                state["n"] += 1
                return 0, ("M app.py" if state["n"] > 1 else ""), ""
            return 0, '{"type":"text","part":{"type":"text","text":"{\\"passed\\": true, \\"blocking\\": [], \\"summary\\": \\"ok\\"}"}}', ""

        monkeypatch.setattr(eng, "_sh", fake_sh)
        verdict, meta = eng.run_opencode(tmp_path, "p", "opencode/x-free", None, 60)
        assert verdict is None
        assert "modifico el arbol" in meta["error"]

    def test_agent_is_passed_and_home_isolated(self, gate, tmp_path, monkeypatch):
        eng = gate.review_engines
        seen = {}

        def fake_sh(cmd, cwd=None, timeout=120, env=None, input_text=None):
            if "status" in cmd:
                return 0, "", ""
            seen["cmd"] = cmd
            seen["env"] = env or {}
            return 0, '{"type":"text","part":{"type":"text","text":"{\\"passed\\": true, \\"blocking\\": [], \\"summary\\": \\"ok\\"}"}}', ""

        monkeypatch.setattr(eng, "_sh", fake_sh)
        home = tmp_path / "home"
        (home / ".config/opencode").mkdir(parents=True)
        (home / ".config/opencode/opencode.json").write_text(
            '{"permission": {"edit": "deny", "bash": "deny"}}')
        monkeypatch.setattr(eng, "OPENCODE_HOME", home)
        eng.run_opencode(tmp_path, "p", "opencode/x-free", None, 60)
        assert "--agent" in seen["cmd"], "el agente restringido es obligatorio"
        assert seen["env"].get("HOME") == str(home)

    def test_empty_isolation_config_is_not_accredited(self, gate, tmp_path, monkeypatch):
        """Un opencode.json vacio existe pero no deniega nada."""
        eng = gate.review_engines
        called = {"sh": 0}

        def fake_sh(*a, **k):
            called["sh"] += 1
            return 0, "", ""

        monkeypatch.setattr(eng, "_sh", fake_sh)
        home = tmp_path / "home"
        (home / ".config/opencode").mkdir(parents=True)
        (home / ".config/opencode/opencode.json").write_text("{}")
        monkeypatch.setattr(eng, "OPENCODE_HOME", home)
        verdict, meta = eng.run_opencode(tmp_path, "p", "opencode/x-free", None, 60)
        assert verdict is None and "no acreditado" in meta["error"]
        assert called["sh"] == 0

    def test_blocking_with_empty_entries_cannot_pass(self, gate):
        v = gate.review_engines.normalize_verdict({"passed": True, "blocking": [None, ""]})
        assert v is not None and v["passed"] is False
        assert len(v["blocking"]) == 2

    def test_missing_isolation_config_refuses_to_run(self, gate, tmp_path, monkeypatch):
        """Sin la config que deniega escritura, no se ejecuta: fail-closed."""
        eng = gate.review_engines
        called = {"sh": 0}

        def fake_sh(*a, **k):
            called["sh"] += 1
            return 0, "", ""

        monkeypatch.setattr(eng, "_sh", fake_sh)
        monkeypatch.setattr(eng, "OPENCODE_HOME", tmp_path / "vacio")
        verdict, meta = eng.run_opencode(tmp_path, "p", "opencode/x-free", None, 60)
        assert verdict is None
        assert "no acreditado" in meta["error"]
        assert called["sh"] == 0, "no debe ni lanzar el proceso"

    def test_provider_is_prefixed_when_model_has_no_slash(self, gate, tmp_path, monkeypatch):
        eng = gate.review_engines
        seen = {}

        def fake_sh(cmd, cwd=None, timeout=120, env=None, input_text=None):
            if "status" in cmd:
                return 0, "", ""
            seen["cmd"] = cmd
            return 0, '{"type":"text","part":{"type":"text","text":"{}"}}', ""

        monkeypatch.setattr(eng, "_sh", fake_sh)
        eng.run_opencode(tmp_path, "p", "glm-5.3-flash-free", "opencode", 30)
        assert "opencode/glm-5.3-flash-free" in seen["cmd"]


class TestReceiptCache:
    """A cache hit may not grant more than the receipt actually proved."""

    def test_cache_hit_short_circuits_when_tests_were_proven(self, gate, tmp_path, monkeypatch):
        repo = make_repo(tmp_path)
        (repo / "ok.py").write_text("def add(a, b):\n    return a + b\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        called = {"n": 0}

        def reviewer(*_a, **_k):
            called["n"] += 1
            return ({"passed": True, "blocking": [], "summary": "ok"}, {"model": "fake", "seconds": 0.1})

        monkeypatch.setattr(gate, "call_reviewer", reviewer)
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged"]) == 0
        assert called["n"] == 1

        # same diff again: the receipt must satisfy the run without a second review
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged"]) == 0
        assert called["n"] == 1

    def test_skip_static_run_does_not_poison_the_cache(self, gate, tmp_path, monkeypatch):
        repo = make_repo(tmp_path)
        (repo / "bad.py").write_text("import subprocess\nsubprocess.run(c, shell=True)\n")  # review-gate:ignore
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        monkeypatch.setattr(
            gate, "call_reviewer",
            lambda *_a, **_k: ({"passed": True, "blocking": [], "summary": "ok"}, {"model": "fake", "seconds": 0.1}),
        )
        # un run que se salta el estatico no puede dejar un pase reutilizable
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged", "--skip-static"]) == 0
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged"]) == 2

    def test_cache_hit_requires_the_same_test_command(self, gate, tmp_path, monkeypatch):
        repo = make_repo(tmp_path)
        (repo / "ok.py").write_text("def add(a, b):\n    return a + b\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        called = {"n": 0}

        def reviewer(*_a, **_k):
            called["n"] += 1
            return ({"passed": True, "blocking": [], "summary": "ok"}, {"model": "fake", "seconds": 0.1})

        monkeypatch.setattr(gate, "call_reviewer", reviewer)
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged", "--test-cmd", "true"]) == 0
        # mismo diff, otra suite: el receipt anterior no puede acreditarla
        run(gate, monkeypatch, ["--repo", str(repo), "--staged", "--test-cmd", "exit 0"])
        assert called["n"] == 2

    def test_cached_pass_without_tests_does_not_satisfy_require_tests(
        self, gate, tmp_path, monkeypatch
    ):
        repo = make_repo(tmp_path)
        (repo / "ok.py").write_text("def add(a, b):\n    return a + b\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        called = {"n": 0}

        def reviewer(*_a, **_k):
            called["n"] += 1
            return ({"passed": True, "blocking": [], "summary": "ok"}, {"model": "fake", "seconds": 0.1})

        monkeypatch.setattr(gate, "call_reviewer", reviewer)
        # first pass: no tests requested, so the receipt records tests_verified=False
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged"]) == 0

        # now demand tests for the identical diff: the cached receipt must not be reused,
        # so the run blocks on missing test evidence instead of returning pass-cached,
        # and it does that before spending a second review.
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged", "--require-tests"]) == 2
        assert called["n"] == 1
