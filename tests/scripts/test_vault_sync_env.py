"""TDD tests — Política de Secretos, Fase 1: sync-env.py con merge preservativo.

Verifier canónico:
    env -u PYTHONPATH python3 -m unittest -v tests/scripts/test_vault_sync_env.py

Todo el contenido es ficticio: cero secretos reales (regla 02-vps-guardrails §2).
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "vault-timer", "sync-env.py")

if not os.path.exists(SCRIPT):
    raise FileNotFoundError(f"Fase 1 (RED): {SCRIPT} todavia no existe")

_spec = importlib.util.spec_from_file_location("vault_sync_env", SCRIPT)
assert _spec is not None and _spec.loader is not None, f"no se pudo cargar {SCRIPT}"
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)


# ---------------------------------------------------------------- fixtures
def login_item(name, password="fake-password-1", username="bot-user", fields=None):
    return {
        "name": name,
        "type": 1,
        "login": {"username": username, "password": password},
        "fields": fields or [],
    }


def note_item(name, notes, fields=None):
    return {"name": name, "type": 2, "notes": notes, "fields": fields or []}


BASE_ENV = (
    "# generado a mano por Plon\n"
    "\n"
    "FOREIGN_KEY=keep-me\n"
    "MAPPED=vault-old\n"
    "OTHER=1\n"
)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sync-env-test-")
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def path(self, name=".env"):
        return os.path.join(self.tmp, name)

    def write(self, text, name=".env", mode="0600"):
        p = self.path(name)
        with open(p, "w") as f:
            f.write(text)
        os.chmod(p, int(mode, 8))
        return p

    def read(self, name=".env"):
        with open(self.path(name)) as f:
            return f.read()


# ---------------------------------------------------------------- RF-1..RF-4
class MergeTextTests(Base):
    def test_ac1_preserves_comments_blanks_and_foreign_keys(self):
        merged = sync.merge_env_text(BASE_ENV, {"MAPPED": "vault-new"})
        lines = merged.splitlines(keepends=True)
        self.assertEqual(lines[0], "# generado a mano por Plon\n")
        self.assertEqual(lines[1], "\n")
        self.assertEqual(lines[2], "FOREIGN_KEY=keep-me\n")
        self.assertEqual(lines[4], "OTHER=1\n")
        self.assertIn("MAPPED=vault-new\n", lines)
        self.assertNotIn("MAPPED=vault-old", merged)

    def test_ac2_appends_missing_key_with_final_newline(self):
        merged = sync.merge_env_text(BASE_ENV, {"NEW_KEY": "x"})
        self.assertTrue(merged.endswith("NEW_KEY=x\n"))
        # el cuerpo original queda intacto
        self.assertTrue(merged.startswith(BASE_ENV))

    def test_ac2_file_without_trailing_newline(self):
        merged = sync.merge_env_text("A=1", {"B": "2"})
        self.assertEqual(merged, "A=1\nB=2\n")

    def test_empty_file_only_updates(self):
        self.assertEqual(sync.merge_env_text("", {"A": "1"}), "A=1\n")

    def test_inline_comment_and_export_prefix_preserved(self):
        text = "export MAPPED=old # rotar cada trimestre\n"
        merged = sync.merge_env_text(text, {"MAPPED": "new"})
        self.assertEqual(merged, "export MAPPED=new # rotar cada trimestre\n")

    def test_hash_inside_quotes_is_not_a_comment(self):
        text = 'MAPPED="old # value"\n'
        merged = sync.merge_env_text(text, {"MAPPED": "new"})
        # el '#' estaba entre comillas -> no es comentario; el valor nuevo se
        # escribe SIN heredar las comillas viejas (el vault es la autoridad)
        self.assertEqual(merged, "MAPPED=new\n")
        self.assertNotIn("value", merged)

    def test_special_characters_roundtrip(self):
        value = 'a=b c"d$e{f}#g'
        merged = sync.merge_env_text("A=1\n", {"MAPPED": value})
        body = merged.splitlines()[-1]
        key, _, rest = body.partition("=")
        self.assertEqual(key, "MAPPED")
        self.assertEqual(rest, value)

    def test_ac6_duplicate_keys_all_updated(self):
        text = "MAPPED=old\nX=1\nMAPPED=old\n"
        merged = sync.merge_env_text(text, {"MAPPED": "new"})
        self.assertNotIn("old", merged)
        self.assertEqual(merged.count("MAPPED=new"), 2)

    def test_crlf_preserved_per_line(self):
        text = "A=1\r\nMAPPED=old\r\n"
        merged = sync.merge_env_text(text, {"MAPPED": "new"})
        self.assertEqual(merged, "A=1\r\nMAPPED=new\r\n")

    def test_bom_preserved_on_update(self):
        raw = b"\xef\xbb\xbf# con BOM\nMAPPED=old\n"
        p = self.path()
        with open(p, "wb") as f:
            f.write(raw)
        with open(p, "rb") as f:
            before = f.read()
        merged = sync.merge_env_text(before.decode("utf-8-sig"), {"MAPPED": "new"})
        self.assertTrue(merged.startswith("# con BOM\n"))
        self.assertNotIn("old", merged)

    def test_read_text_strips_bom_and_missing_file_is_empty(self):
        p = self.path()
        with open(p, "wb") as f:
            f.write(b"\xef\xbb\xbfA=1\n")
        self.assertEqual(sync.read_text(p), "A=1\n")
        self.assertEqual(sync.read_text(self.path("absent.env")), "")
        # politica del repo: escrituras en utf-8 puro, sin BOM emitido
        self.assertFalse(sync.read_text(p).startswith("\ufeff"))

    def test_blank_and_comment_only_file(self):
        text = "# only a comment\n\n"
        self.assertEqual(sync.merge_env_text(text, {}), text)


# ---------------------------------------------------------------- RF-5 helpers
class FieldExtractionTests(Base):
    def test_login_password_and_username(self):
        item = login_item("X", password="p1", username="u1")
        self.assertEqual(sync.extract_field_value(item, "password"), "p1")
        self.assertEqual(sync.extract_field_value(item, "username"), "u1")

    def test_custom_field(self):
        item = login_item("X", fields=[{"name": "API_KEY", "value": "v-123"}])
        self.assertEqual(sync.extract_field_value(item, "API_KEY"), "v-123")

    def test_notes_field_and_env_fallback(self):
        item = note_item("N", "OTHER_KEY=fallback\n")
        self.assertEqual(sync.extract_field_value(item, "OTHER_KEY"), "fallback")
        self.assertIsNone(sync.extract_field_value(item, "MISSING"))

    def test_missing_item_returns_none(self):
        warnings = []
        updates = sync.build_updates(
            {"mappings": [{"item": "nope", "field": "password", "env": "K"}]},
            {},
            warnings.append,
        )
        self.assertEqual(updates, {})
        self.assertTrue(any("not found in vault" in w for w in warnings))


# ---------------------------------------------------------------- RF-5/RF-6 target
class SyncTargetTests(Base):
    def target(self, file=None, mappings=None, **extra):
        t = {
            "file": file or self.path(),
            "mode": "0600",
            "mappings": mappings or [{"item": "Item A", "field": "password", "env": "MAPPED"}],
        }
        t.update(extra)
        return t

    def run_target(self, target, items, restart_fn=None):
        warns = []
        outs = []
        outcome = sync.sync_target(
            target,
            items,
            warn=warns.append,
            out=outs.append,
            restart_fn=restart_fn or (lambda cmd: None),
        )
        return outcome, "\n".join(warns), "\n".join(outs)

    def test_ac3_missing_parent_is_skipped(self):
        target = self.target(file=os.path.join(self.tmp, "gone", ".env"))
        outcome, warns, _ = self.run_target(target, {"Item A": login_item("Item A")})
        self.assertEqual(outcome, "skipped")
        self.assertIn("SKIPPED: parent dir does not exist", warns)

    def test_ac1_end_to_end_merge_on_disk(self):
        self.write(BASE_ENV)
        outcome, _, _ = self.run_target(self.target(), {"Item A": login_item("Item A", password="new-1")})
        self.assertEqual(outcome, "ok")
        text = self.read()
        self.assertIn("# generado a mano por Plon\n", text)
        self.assertIn("FOREIGN_KEY=keep-me\n", text)
        self.assertIn("MAPPED=new-1\n", text)
        self.assertNotIn("MAPPED=vault-old", text)

    def test_ac4_write_failure_leaves_original_intact(self):
        self.write(BASE_ENV)
        target = self.target()
        with mock.patch.object(sync.os, "replace", side_effect=OSError("disk full")):
            outcome, warns, _ = self.run_target(target, {"Item A": login_item("Item A", password="new-1")})
        self.assertEqual(outcome, "failed")
        self.assertIn("FAILED:", warns)
        self.assertEqual(self.read(), BASE_ENV)
        leftovers = [n for n in os.listdir(self.tmp) if n.startswith(".env-sync-")]
        self.assertEqual(leftovers, [])

    def test_ac5_restart_only_when_content_changes(self):
        self.write(BASE_ENV)
        items = {"Item A": login_item("Item A", password="new-1")}
        calls = []
        target = self.target(restart="systemctl restart foo")
        first, _, _ = self.run_target(target, items, restart_fn=calls.append)
        second, _, _ = self.run_target(target, items, restart_fn=calls.append)
        self.assertEqual([first, second], ["ok", "ok"])
        self.assertEqual(calls, ["systemctl restart foo"])

    def test_mode_applied(self):
        self.write(BASE_ENV, mode="0600")
        self.run_target(self.target(mode="0644"), {"Item A": login_item("Item A", password="v")})
        mode = stat.S_IMODE(os.stat(self.path()).st_mode)
        self.assertEqual(mode, 0o644)

    def test_h1_target_directory_is_failed_not_fatal(self):
        d = self.path("esdir")
        os.mkdir(d)
        outcome, warns, _ = self.run_target(self.target(file=d), {"Item A": login_item("Item A")})
        self.assertEqual(outcome, "failed")
        self.assertIn("IsADirectoryError", warns)

    def test_h1_invalid_utf8_env_fails_without_touching_bytes(self):
        p = self.path()
        raw = b"K=old\nBIN=\xff\xfe\n"
        with open(p, "wb") as f:
            f.write(raw)
        outcome, warns, _ = self.run_target(self.target(), {"Item A": login_item("Item A")})
        self.assertEqual(outcome, "failed")
        self.assertIn("UnicodeDecodeError", warns)
        with open(p, "rb") as f:
            self.assertEqual(f.read(), raw)

    def test_h1_malformed_item_does_not_raise(self):
        self.write(BASE_ENV)
        # item que no es dict -> AttributeError dentro de build_updates
        outcome, warns, _ = self.run_target(self.target(), {"Item A": "no-dict"})
        self.assertEqual(outcome, "failed")
        self.assertIn("FAILED", warns)

    def test_h2_symlink_env_is_written_through(self):
        real = os.path.join(self.tmp, "real.env")
        with open(real, "w") as f:
            f.write("MAPPED=old\n")
        link = self.path("link.env")
        os.symlink(real, link)
        outcome, _, _ = self.run_target(self.target(file=link), {"Item A": login_item("Item A", password="new-1")})
        self.assertEqual(outcome, "ok")
        self.assertTrue(os.path.islink(link), "el symlink debe sobrevivir")
        with open(real) as f:
            self.assertIn("MAPPED=new-1", f.read())

    def test_h3_leading_bom_does_not_duplicate_key(self):
        merged = sync.merge_env_text("\ufeffMAPPED=old\nOTHER=1\n", {"MAPPED": "new"})
        self.assertEqual(merged, "MAPPED=new\nOTHER=1\n")

    def test_h4_missing_file_with_no_updates_is_not_created(self):
        target = self.target(file=self.path("nuevo.env"), restart="svc restart")
        calls = []
        outcome, warns, _ = self.run_target(
            target, {}, restart_fn=calls.append
        )
        self.assertEqual(outcome, "ok")
        self.assertFalse(os.path.exists(target["file"]))
        self.assertEqual(calls, [])

    def test_h5_failed_restart_is_warned(self):
        self.write(BASE_ENV)
        target = self.target(restart="svc restart")
        calls = []
        outcome, warns, _ = self.run_target(
            target, {"Item A": login_item("Item A", password="new-1")},
            restart_fn=lambda cmd: calls.append(cmd) or 3,
        )
        self.assertEqual(outcome, "ok")
        self.assertEqual(calls, ["svc restart"])
        self.assertIn("restart exited with 3", warns)

    def test_h6_append_inherits_crlf(self):
        # la clave mapeada se reemplaza en sitio conservando su terminador
        self.assertEqual(
            sync.merge_env_text("A=1\r\nMAPPED=old\r\n", {"MAPPED": "new"}),
            "A=1\r\nMAPPED=new\r\n",
        )
        # la clave ausente hereda el EOL del archivo (RF-3), no un \n fijo
        self.assertEqual(
            sync.merge_env_text("A=1\r\n", {"K": "new"}),
            "A=1\r\nK=new\r\n",
        )

    def test_h9_fetch_items_warns_on_duplicate_names(self):
        import types

        payload = json.dumps([
            {"name": "dup", "type": 1, "login": {"password": "v1"}},
            {"name": "dup", "type": 1, "login": {"password": "v2"}},
        ])
        runner = lambda *a, **k: types.SimpleNamespace(returncode=0, stdout=payload, stderr="")
        warns = []
        items = sync.fetch_items("SESS", runner=runner, warn=warns.append)
        self.assertEqual(set(items), {"dup"})
        self.assertTrue(any("duplicate vault item name" in w for w in warns))

    def test_missing_owner_warns_but_writes(self):
        self.write(BASE_ENV)
        warns = []
        with mock.patch("pwd.getpwnam", side_effect=KeyError("nope")):  # import local en atomic_write:
            sync.sync_target(
                self.target(owner="ghost"),
                {"Item A": login_item("Item A", password="v")},
                warn=warns.append,
                out=lambda m: None,
                restart_fn=lambda c: None,
            )
        self.assertIn("ownership unchanged", "\n".join(warns))
        self.assertIn("MAPPED=v", self.read())


# ---------------------------------------------------------------- main / RF-7 / RF-8
class MainTests(Base):
    def mapfile(self, targets):
        p = os.path.join(self.tmp, "map.json")
        with open(p, "w") as f:
            json.dump({"version": 1, "targets": targets}, f)
        return p

    def items(self):
        return {"Item A": login_item("Item A", password="fresh")}

    def call_main(self, targets, fetch=None, restart_fn=None):
        err = io.StringIO()
        out = io.StringIO()
        code = sync.main(
            ["SESSION"],
            mapfile=self.mapfile(targets),
            fetch=fetch or (lambda session: self.items()),
            err=err,
            out=out,
            restart_fn=restart_fn or (lambda c: None),
        )
        return code, err.getvalue(), out.getvalue()

    def target(self, file, **extra):
        t = {
            "file": file,
            "mode": "0600",
            "mappings": [{"item": "Item A", "field": "password", "env": "MAPPED"}],
        }
        t.update(extra)
        return t

    def test_ac3_summary_contract_and_queue_continues(self):
        dead = self.target(os.path.join(self.tmp, "gone", ".env"))
        alive = self.target(os.path.join(self.tmp, "live.env"))
        code, err, _ = self.call_main([dead, alive])
        self.assertEqual(code, 0)
        self.assertIn("SUMMARY: ok=1 skipped=1 failed=0", err)
        self.assertTrue(os.path.exists(alive["file"]))

    def test_ac5_second_run_no_restart(self):
        target = self.target(os.path.join(self.tmp, "live.env"), restart="svc restart")
        self.write(BASE_ENV, name="live.env")
        calls = []
        first_code, first_err, _ = self.call_main([target], restart_fn=calls.append)
        second_code, second_err, _ = self.call_main([target], restart_fn=calls.append)
        self.assertEqual([first_code, second_code], [0, 0])
        self.assertEqual(len(calls), 1)
        self.assertIn("Changed, restarting:", first_err)
        self.assertNotIn("Changed, restarting:", second_err)

    def test_fetch_failure_exits_1_without_writing(self):
        def bad_fetch(session):
            raise sync.VaultFetchError("bw list items failed: boom")

        target = self.target(os.path.join(self.tmp, "live.env"))
        code, err, _ = self.call_main([target], fetch=bad_fetch)
        self.assertEqual(code, 1)
        self.assertIn("ERROR:", err)
        self.assertFalse(os.path.exists(target["file"]))

    def test_exit_code_1_when_failures_and_no_success(self):
        target = self.target(os.path.join(self.tmp, "live.env"))
        with mock.patch.object(sync.os, "replace", side_effect=OSError("io error")):
            code, err, _ = self.call_main([target])
        self.assertEqual(code, 1)
        self.assertIn("SUMMARY: ok=0 skipped=0 failed=1", err)

    def test_exit_code_0_when_everything_skipped(self):
        dead = self.target(os.path.join(self.tmp, "gone", ".env"))
        code, err, _ = self.call_main([dead])
        self.assertEqual(code, 0)
        self.assertIn("SUMMARY: ok=0 skipped=1 failed=0", err)

    def test_n1_non_dict_target_does_not_kill_summary(self):
        # un target que no es objeto en el mapa: failed+SUMMARY, no traceback
        bad = "esto-no-es-un-objeto"
        good = self.target(os.path.join(self.tmp, "live.env"))
        code, err, _ = self.call_main([bad, good])
        self.assertEqual(code, 0)
        self.assertIn("SUMMARY: ok=1 skipped=0 failed=1", err)
        self.assertIn("<invalid target: str>", err)
        self.assertNotIn("Traceback", err)
        self.assertTrue(os.path.exists(good["file"]))

    def test_n1_all_invalid_targets_exit_1_with_summary(self):
        code, err, _ = self.call_main([None, "x"])
        self.assertEqual(code, 1)
        self.assertIn("SUMMARY: ok=0 skipped=0 failed=2", err)

    def test_usage_error_returns_1(self):
        err = io.StringIO()
        self.assertEqual(sync.main([], mapfile="/nonexistent", err=err), 1)
        self.assertIn("Usage", err.getvalue())


if __name__ == "__main__":
    unittest.main()
