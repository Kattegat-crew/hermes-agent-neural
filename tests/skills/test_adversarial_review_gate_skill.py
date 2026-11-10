"""Tests for the adversarial-review-gate skill.

The gate is the only thing standing between a buggy diff and a commit, so its
failure modes are tested by behaviour, not by mocking the thing under test: the
reviewer is stubbed (it is another process), git is real (a throwaway repo), and
the receipt store is a tmp dir.

Regression coverage is aimed at the bugs this gate shipped and then had to fix:
fail-open on a missing verdict, a cache hit that bypassed required tests, and
flag injection through --range.
"""
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

        monkeypatch.setattr(gate, "call_agy", explode)
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged"]) == 2

    def test_missing_verdict_is_fail_closed(self, gate, tmp_path, monkeypatch):
        repo = make_repo(tmp_path)
        (repo / "ok.py").write_text("def add(a, b):\n    return a + b\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        monkeypatch.setattr(
            gate, "call_agy", lambda *_a, **_k: (None, {"model": "x", "seconds": 0.1, "error": "429"})
        )
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged"]) == 2

    def test_degraded_can_be_waived_explicitly(self, gate, tmp_path, monkeypatch):
        repo = make_repo(tmp_path)
        (repo / "ok.py").write_text("def add(a, b):\n    return a + b\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        monkeypatch.setattr(
            gate, "call_agy", lambda *_a, **_k: (None, {"model": "x", "seconds": 0.1, "error": "429"})
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

        monkeypatch.setattr(gate, "call_agy", reviewer)
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged"]) == 0
        assert called["n"] == 1, "un hallazgo low no puede saltarse la revision adversarial"

    def test_docs_only_diff_skips_everything(self, gate, tmp_path, monkeypatch):
        repo = make_repo(tmp_path)
        (repo / "NOTES.md").write_text("hola\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)

        def explode(*_a, **_k):
            raise AssertionError("a docs-only diff must not reach the reviewer")

        monkeypatch.setattr(gate, "call_agy", explode)
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged"]) == 0


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
            gate, "call_agy", lambda *_a, **_k: (verdict, {"model": "fake", "seconds": 0.1})
        )
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged"]) == 2

    def test_inadequate_tests_are_advisory_not_veto(self, gate, tmp_path, monkeypatch):
        """El reviewer opina sin nombrar qué falta: bloquear sobre eso cierra un bucle."""
        repo = self._repo_with_clean_change(tmp_path)
        verdict = {"passed": True, "blocking": [], "tests_adequate": False, "summary": "ok"}
        monkeypatch.setattr(
            gate, "call_agy", lambda *_a, **_k: (verdict, {"model": "fake", "seconds": 0.1})
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

        monkeypatch.setattr(gate, "call_agy", explode)
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

        monkeypatch.setattr(gate, "call_agy", reviewer)
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged", "--model", "m-a"]) == 0
        # mismo diff, otro modelo: el veredicto anterior no puede acreditarlo
        run(gate, monkeypatch, ["--repo", str(repo), "--staged", "--model", "m-b"])
        assert called["n"] == 2


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

        monkeypatch.setattr(gate, "call_agy", reviewer)
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
            gate, "call_agy",
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

        monkeypatch.setattr(gate, "call_agy", reviewer)
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

        monkeypatch.setattr(gate, "call_agy", reviewer)
        # first pass: no tests requested, so the receipt records tests_verified=False
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged"]) == 0

        # now demand tests for the identical diff: the cached receipt must not be reused,
        # so the run blocks on missing test evidence instead of returning pass-cached,
        # and it does that before spending a second review.
        assert run(gate, monkeypatch, ["--repo", str(repo), "--staged", "--require-tests"]) == 2
        assert called["n"] == 1
