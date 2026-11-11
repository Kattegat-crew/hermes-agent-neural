#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas de fleet_daily_memory_audit: fixtures en directorios temporales.

Ejecutar:  python3.12 -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "fleet_daily_memory_audit.py"
spec = importlib.util.spec_from_file_location("fleet_daily_memory_audit", SCRIPT)
assert spec is not None and spec.loader is not None, f"no puedo cargar {SCRIPT}"
fma = importlib.util.module_from_spec(spec)
sys.modules["fleet_daily_memory_audit"] = fma
spec.loader.exec_module(fma)

CONFIG_OK = """\
model:
  default: deepseek-v4-flash
plugins:
  disabled: []
  enabled:
    - hermes-session-reset-policy
    - typesafe-skill-router
  entries: {}
session_reset:
  at_hour: 6
  idle_minutes: 120
  mode: both
"""

CONFIG_SIN_PLUGIN = CONFIG_OK.replace("    - hermes-session-reset-policy\n", "")
CONFIG_SIN_RESET = CONFIG_OK.split("session_reset:")[0]


def job(ok=True, enabled=True, status: str | None = "ok"):
    return {
        "name": "guardar-diario-memoria",
        "enabled": enabled,
        "last_status": status,
        "last_run_at": "2026-11-10T23:08:00-05:00",
    }


class ParserTest(unittest.TestCase):
    def test_lee_bloque_session_reset(self):
        bloque = fma._bloque_session_reset(CONFIG_OK)
        self.assertEqual(bloque["mode"], "both")
        self.assertEqual(bloque["idle_minutes"], "120")

    def test_bloque_comentado_no_cuenta(self):
        texto = "# session_reset:\n#   mode: both\nmodel:\n  default: x\n"
        self.assertEqual(fma._bloque_session_reset(texto), {})

    def test_detecta_plugin_en_lista_enabled(self):
        self.assertTrue(fma.plugin_habilitado(CONFIG_OK))

    def test_plugin_fuera_de_la_lista_no_cuenta(self):
        self.assertFalse(fma.plugin_habilitado(CONFIG_SIN_PLUGIN))

    def test_plugin_solo_mencionado_en_comentario_no_cuenta(self):
        texto = CONFIG_SIN_PLUGIN.replace(
            "  entries:", "  # hermes-session-reset-policy pendiente\n  entries:"
        )
        self.assertFalse(fma.plugin_habilitado(texto))

    def test_plugin_tras_entries_no_cuenta(self):
        texto = CONFIG_OK.replace(
            "  entries: {}", "  entries:\n    x:\n      enabled: true"
        ).replace("    - hermes-session-reset-policy\n", "")
        texto += "    - hermes-session-reset-policy\n"
        self.assertFalse(fma.plugin_habilitado(texto))

    def test_mode_anidado_no_cuenta_como_mode_real(self):
        """Un ``mode:`` dentro de un sub-bloque no es el modo del session_reset."""
        texto = (
            "session_reset:\n"
            "  notify:\n"
            "    mode: both\n"
            "  idle_minutes: 120\n"
        )
        bloque = fma._bloque_session_reset(texto)
        self.assertNotIn("mode", bloque)
        self.assertEqual(bloque["idle_minutes"], "120")

    def test_valores_entre_comillas_simples_se_aceptan(self):
        texto = "session_reset:\n  mode: 'both'\n  idle_minutes: \"120\"\n"
        self.assertEqual(fma._bloque_session_reset(texto)["mode"], "both")

    def test_item_de_plugin_entre_comillas_simples_cuenta(self):
        texto = CONFIG_OK.replace(
            "    - hermes-session-reset-policy", "    - 'hermes-session-reset-policy'"
        )
        self.assertTrue(fma.plugin_habilitado(texto))

    def test_forma_inline_se_reporta_como_no_soportada(self):
        texto = "session_reset: {mode: both}\nplugins:\n  enabled:\n    - hermes-session-reset-policy\n"
        self.assertEqual(fma._bloque_session_reset(texto)["_forma"], "{mode: both}")


class AuditoriaTest(unittest.TestCase):
    def _perfil(self, tmp: Path, nombre: str, config: str, jobdict=None):
        base = tmp / nombre
        (base / "cron").mkdir(parents=True)
        (base / "config.yaml").write_text(config, encoding="utf-8")
        if jobdict is not None:
            (base / "cron" / "jobs.json").write_text(
                json.dumps({"jobs": [jobdict]}), encoding="utf-8"
            )

    def test_perfil_completo_es_ok(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._perfil(tmp, "bragi", CONFIG_OK, job())
            r = fma.auditar_perfil(tmp, "bragi")
            self.assertTrue(r["ok"], r["faltantes"])
            self.assertEqual(r["reset_mode"], "both")

    def test_sin_plugin_se_reporta(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._perfil(tmp, "freyja", CONFIG_SIN_PLUGIN, job())
            r = fma.auditar_perfil(tmp, "freyja")
            self.assertFalse(r["ok"])
            self.assertIn("plugin de reset apagado", r["faltantes"])

    def test_sin_session_reset_se_reporta(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._perfil(tmp, "ullr", CONFIG_SIN_RESET, job())
            r = fma.auditar_perfil(tmp, "ullr")
            self.assertFalse(r["ok"])
            self.assertIn("session_reset ausente o inerte", r["faltantes"])

    def test_sin_job_se_reporta(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._perfil(tmp, "vili", CONFIG_OK, None)
            r = fma.auditar_perfil(tmp, "vili")
            self.assertFalse(r["ok"])
            self.assertIn("job de memoria ausente", r["faltantes"])

    def test_job_pausado_se_reporta(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._perfil(tmp, "sindri", CONFIG_OK, job(enabled=False))
            r = fma.auditar_perfil(tmp, "sindri")
            self.assertIn("job de memoria pausado", r["faltantes"])

    def test_job_con_error_se_reporta(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._perfil(tmp, "hermodr", CONFIG_OK, job(status="error"))
            r = fma.auditar_perfil(tmp, "hermodr")
            self.assertIn("última corrida error", r["faltantes"])

    def test_job_nunca_ejecutado_no_es_hueco(self):
        """``last_status=None`` es recién creado, no un fallo: no debe marcar hueco."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._perfil(tmp, "brokkr", CONFIG_OK, job(status=None))
            self.assertTrue(fma.auditar_perfil(tmp, "brokkr")["ok"])

    def test_perfiles_excluye_default_y_tests(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            for n in ("default", "neural-admin-test", "test-onboarding-01", "bragi", "ullr"):
                self._perfil(tmp, n, CONFIG_OK, job())
            self.assertEqual(fma.perfiles(tmp), ["bragi", "ullr"])

    def test_main_exit_1_con_huecos(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._perfil(tmp, "bragi", CONFIG_OK, job())
            self._perfil(tmp, "vili", CONFIG_SIN_PLUGIN, job())
            self.assertEqual(fma.main(["--root", str(tmp)]), 1)

    def test_main_exit_0_sin_huecos(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._perfil(tmp, "bragi", CONFIG_OK, job())
            self.assertEqual(fma.main(["--root", str(tmp)]), 0)

    def test_flota_vacia_no_canta_exito(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(fma.main(["--root", str(Path(td) / "no-existe")]), 2)

    def test_forma_inline_marca_hueco_explicito(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._perfil(
                tmp, "bragi",
                "session_reset: {mode: both}\n"
                "plugins:\n  enabled:\n    - hermes-session-reset-policy\n",
                job(),
            )
            r = fma.auditar_perfil(tmp, "bragi")
            self.assertFalse(r["ok"])
            self.assertTrue(any("forma no soportada" in f for f in r["faltantes"]), r["faltantes"])


if __name__ == "__main__":
    unittest.main()
