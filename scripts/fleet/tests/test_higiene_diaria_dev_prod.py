#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas del reporte DEV+PROD del confirmador de higiene diaria.

Cubre lo nuevo del 11-nov-2026: la sonda única a PROD (JSON), la evidencia de reset y la
composición de UNA línea que se entrega al hilo «🔁 Higiene diaria».
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "guardar_diario_confirmar.py"
spec = importlib.util.spec_from_file_location("gdc_prod", SCRIPT)
assert spec is not None and spec.loader is not None, f"no puedo cargar {SCRIPT}"
gdc = importlib.util.module_from_spec(spec)
sys.modules["gdc_prod"] = gdc
spec.loader.exec_module(gdc)

TZ = datetime.timezone(datetime.timedelta(hours=-5))
AHORA = datetime.datetime(2026, 11, 11, 0, 10, tzinfo=TZ)


def job_ok(**over):
    base = {
        "id": "abc", "name": "guardar-diario-memoria", "enabled": True, "state": "scheduled",
        "last_status": "ok", "last_run_at": "2026-11-10T23:08:58-05:00", "last_error": None,
    }
    base.update(over)
    return base


def sonda(perfiles, cerradas=57, sobre=0):
    payload = {"perfiles": perfiles, "reset": {"cerradas_24h": cerradas, "sobre_umbral": sobre}}
    return 0, "@@JSON@@" + json.dumps(payload), ""


class SondaProdTest(unittest.TestCase):
    def test_perfiles_ok_y_reset(self):
        perfiles, reset = gdc.estado_prod(
            AHORA, runner=lambda cmd, timeout=90, entrada=None: sonda({"golden-game": job_ok(), "default": job_ok()})
        )
        self.assertEqual({k: v[0] for k, v in perfiles.items()}, {"golden-game": "ok", "default": "ok"})
        self.assertEqual(reset["cerradas_24h"], 57)

    def test_perfil_sin_job_es_job_ausente(self):
        perfiles, _ = gdc.estado_prod(AHORA, runner=lambda cmd, timeout=90, entrada=None: sonda({"prospectos": None}))
        self.assertEqual(perfiles["prospectos"][0], "sin_job")

    def test_job_pausado_se_detecta(self):
        perfiles, _ = gdc.estado_prod(
            AHORA, runner=lambda cmd, timeout=90, entrada=None: sonda({"golden-game": job_ok(enabled=False, state="paused")})
        )
        self.assertEqual(perfiles["golden-game"][0], "pausado")

    def test_ssh_fallido_no_inventa_perfiles(self):
        perfiles, reset = gdc.estado_prod(AHORA, runner=lambda cmd, timeout=90, entrada=None: (255, "", "connection refused"))
        self.assertEqual(perfiles, {})
        self.assertIn("ssh rc=255", reset["error"])

    def test_salida_sin_json_es_error(self):
        perfiles, reset = gdc.estado_prod(AHORA, runner=lambda cmd, timeout=90, entrada=None: (0, "basura", ""))
        self.assertEqual(perfiles, {})
        self.assertIn("sin JSON", reset["error"])

    def test_json_invalido_es_error(self):
        _, reset = gdc.estado_prod(AHORA, runner=lambda cmd, timeout=90, entrada=None: (0, "@@JSON@@{no json", ""))
        self.assertIn("JSON inválido", reset["error"])


class ProdBugTest(unittest.TestCase):
    def test_la_sonda_viaja_por_stdin(self):
        """`docker exec -i python3 -` lee el script de stdin: sin entrada no hay JSON."""
        visto = {}

        def runner(cmd, timeout=90, entrada=None):
            visto["cmd"] = cmd
            visto["entrada"] = entrada
            return 0, "@@JSON@@" + json.dumps({"perfiles": {}, "reset": {"cerradas_24h": 0, "sobre_umbral": 0}}), ""

        gdc.estado_prod(AHORA, runner=runner)
        self.assertIn("guardar-diario-memoria", visto["entrada"])
        self.assertIn("python3 -", " ".join(visto["cmd"]))

    def test_job_recien_creado_es_pendiente_no_fallo(self):
        job = {"name": "guardar-diario-memoria", "enabled": True, "state": "scheduled",
               "last_status": None, "last_run_at": None, "created_at": "2026-11-11T08:51:37-05:00",
               "next_run_at": "2026-11-11T23:02:00-05:00"}
        estado, detalle = gdc.clasificar(job, AHORA)
        self.assertEqual(estado, "pendiente", detalle)
        self.assertIn("23:02", detalle)

    def test_job_viejo_sin_corrida_sigue_siendo_fallo(self):
        job = {"name": "guardar-diario-memoria", "enabled": True, "state": "scheduled",
               "last_status": None, "last_run_at": None, "created_at": "2026-10-01T08:00:00-05:00"}
        self.assertEqual(gdc.clasificar(job, AHORA)[0], "no_ejecutado")


class ReporteTest(unittest.TestCase):
    def _ok(self, n):
        return {f"p{i}": ("ok", "") for i in range(n)}

    def test_exito_resume_conteos_y_reset(self):
        msg = gdc.construir_reporte(self._ok(11), self._ok(14), {"cerradas_24h": 57, "sobre_umbral": 0}, AHORA)
        self.assertTrue(msg.startswith("✅ Higiene"), msg)
        self.assertIn("DEV 11/11", msg)
        self.assertIn("PROD 14/14", msg)
        self.assertIn("57 cerradas/24h", msg)
        self.assertIn("0 sobre 300k", msg)

    def test_fallos_llevan_prefijo_de_flota(self):
        dev = {"bragi": ("pausado", "motivo=x")}
        prod = {"golden-game": ("fallo", "status=error")}
        msg = gdc.construir_reporte(dev, prod, {"cerradas_24h": 3, "sobre_umbral": 2}, AHORA)
        self.assertTrue(msg.startswith("❌ Higiene"), msg)
        self.assertIn("DEV bragi (PAUSADO", msg)
        self.assertIn("PROD golden-game (FALLÓ", msg)
        self.assertIn("2 sobre 300k", msg)

    def test_recorta_lista_larga(self):
        dev = {f"perfil{i}": ("fallo", "x") for i in range(9)}
        msg = gdc.construir_reporte(dev, {}, {}, AHORA, max_fallos=6)
        self.assertIn("+3 más", msg)

    def test_respeta_limite_de_discord(self):
        dev = {f"perfil-con-nombre-largo-{i}": ("fallo", "detalle " * 40) for i in range(40)}
        msg = gdc.construir_reporte(dev, {}, {}, AHORA, max_fallos=40)
        self.assertLessEqual(len(msg), 2000)

    def test_reset_sin_datos_se_dice(self):
        msg = gdc.construir_reporte(self._ok(11), {}, {"error": "ssh rc=255"}, AHORA)
        self.assertIn("reset sin datos", msg)

    def test_exito_informa_pendientes(self):
        dev = self._ok(10)
        dev["bragi"] = ("pendiente", "primera corrida programada 2026-11-11T23:02:00-05:00")
        msg = gdc.construir_reporte(dev, self._ok(14), {"cerradas_24h": 0, "sobre_umbral": 0}, AHORA)
        self.assertTrue(msg.startswith("✅"), msg)
        self.assertIn("1 pendiente", msg)

    def test_una_sola_linea(self):
        dev = {"bragi": ("fallo", "linea1\nlinea2")}
        msg = gdc.construir_reporte(dev, {}, {"cerradas_24h": 1, "sobre_umbral": 0}, AHORA)
        self.assertNotIn("\n", msg)


class EjecutarTest(unittest.TestCase):
    def test_con_prod_false_no_llama_ssh(self):
        def runner(cmd, timeout=90, entrada=None):
            raise AssertionError("no debe llamarse ssh")
        msg = gdc.ejecutar(now=AHORA, prod_runner=runner, con_prod=False)
        self.assertIn("❌", msg)  # DEV real puede tener huecos; lo que importa es que no tocó ssh

    def test_rutas_explicitas_mantienen_contrato_heredado(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rutas = {}
            for nombre in ("Ragnar", "Roshi", "Vigía"):
                d = tmp / nombre.lower()
                d.mkdir()
                (d / "jobs.json").write_text(json.dumps({"jobs": [job_ok()]}), encoding="utf-8")
                rutas[nombre] = d / "jobs.json"
            msg = gdc.ejecutar(rutas, now=AHORA)
            self.assertEqual(msg, "✅ Guardado con éxito en los 3 perfiles.")


if __name__ == "__main__":
    unittest.main()
