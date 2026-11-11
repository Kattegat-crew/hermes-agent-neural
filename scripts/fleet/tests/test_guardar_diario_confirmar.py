#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas de guardar_diario_confirmar: clasificación paused/fallo/no-ejecutado.

No tocan rutas reales: cada caso escribe un jobs.json en un directorio temporal.
Ejecutar:  python3.12 -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "guardar_diario_confirmar.py"
spec = importlib.util.spec_from_file_location("guardar_diario_confirmar", SCRIPT)
assert spec is not None and spec.loader is not None, f"no puedo cargar {SCRIPT}"
gdc = importlib.util.module_from_spec(spec)
sys.modules["guardar_diario_confirmar"] = gdc
spec.loader.exec_module(gdc)

TZ = datetime.timezone(datetime.timedelta(hours=-5))


def now_fijo(hora: int = 0, minuto: int = 5) -> datetime.datetime:
    return datetime.datetime(2026, 11, 11, hora, minuto, tzinfo=TZ)


def job_ok(**over):
    base = {
        "id": "abc123",
        "name": "guardar-diario-memoria",
        "enabled": True,
        "state": "scheduled",
        "last_status": "ok",
        "last_run_at": "2026-11-10T23:08:58-05:00",
        "last_error": None,
        "paused_reason": None,
        "next_run_at": "2026-11-11T23:00:00-05:00",
    }
    base.update(over)
    return base


class ClasificacionTest(unittest.TestCase):
    def test_ok_reciente_y_en_ventana(self):
        estado, detalle = gdc.clasificar(job_ok(), now_fijo())
        self.assertEqual(estado, "ok", detalle)

    def test_pausado_no_se_reporta_como_fallo(self):
        job = job_ok(
            enabled=False,
            state="paused",
            paused_reason="emergency-stability-pause",
            last_run_at="2026-11-08T23:01:57.578940-05:00",
        )
        estado, detalle = gdc.clasificar(job, now_fijo())
        self.assertEqual(estado, "pausado")
        self.assertIn("emergency-stability-pause", detalle)
        self.assertIn("2026-11-08T23:01:57", detalle)

    def test_pausado_sin_motivo_declara_desconocido(self):
        job = job_ok(enabled=False, state="paused", paused_reason=None)
        estado, detalle = gdc.clasificar(job, now_fijo())
        self.assertEqual(estado, "pausado")
        self.assertIn("sin motivo", detalle)

    def test_error_de_ejecucion_es_fallo(self):
        job = job_ok(last_status="error", last_error="GatewayClientError: boom")
        estado, detalle = gdc.clasificar(job, now_fijo())
        self.assertEqual(estado, "fallo")
        self.assertIn("GatewayClientError", detalle)

    def test_habilitado_ok_pero_viejo_es_no_ejecutado(self):
        job = job_ok(last_run_at="2026-11-09T23:05:00-05:00")
        estado, detalle = gdc.clasificar(job, now_fijo())
        self.assertEqual(estado, "no_ejecutado")
        self.assertIn("2026-11-09T23:05:00", detalle)

    def test_run_fuera_de_venta_nocturna_es_no_ejecutado(self):
        job = job_ok(last_run_at="2026-11-10T09:00:00-05:00")
        estado, detalle = gdc.clasificar(job, now_fijo())
        self.assertEqual(estado, "no_ejecutado")

    def test_last_run_ausente_es_no_ejecutado(self):
        estado, _ = gdc.clasificar(job_ok(last_run_at=None), now_fijo())
        self.assertEqual(estado, "no_ejecutado")

    def test_last_run_ilegible_es_no_ejecutado(self):
        estado, _ = gdc.clasificar(job_ok(last_run_at="no-es-fecha"), now_fijo())
        self.assertEqual(estado, "no_ejecutado")

    def test_status_desconocido_es_fallo(self):
        estado, detalle = gdc.clasificar(job_ok(last_status="blocked_config"), now_fijo())
        self.assertEqual(estado, "fallo")
        self.assertIn("blocked_config", detalle)

    def test_sin_status_es_no_ejecutado(self):
        estado, detalle = gdc.clasificar(job_ok(last_status=None), now_fijo())
        self.assertEqual(estado, "no_ejecutado")
        self.assertIn("sin status registrado", detalle)

    def test_sin_status_ni_corrida_es_nunca_ejecutado(self):
        estado, detalle = gdc.clasificar(job_ok(last_status=None, last_run_at=None), now_fijo())
        self.assertEqual(estado, "no_ejecutado")
        self.assertIn("nunca ejecutado", detalle)

    def test_paused_reason_residual_no_marca_pausado(self):
        """Si el resume dejara el motivo pegado, un job sano no debe salir PAUSADO."""
        job = job_ok(paused_reason="emergency-stability-pause")
        estado, detalle = gdc.clasificar(job, now_fijo())
        self.assertEqual(estado, "ok", detalle)
        self.assertNotIn("PAUSADO", detalle.upper())

    def test_paused_reason_residual_se_anota_en_el_fallo(self):
        job = job_ok(paused_reason="emergency-stability-pause", last_status="error")
        estado, detalle = gdc.clasificar(job, now_fijo())
        self.assertEqual(estado, "fallo")
        self.assertIn("residual", detalle)

    def test_borde_ventana_2245_es_ok(self):
        estado, _ = gdc.clasificar(job_ok(last_run_at="2026-11-10T22:45:00-05:00"), now_fijo())
        self.assertEqual(estado, "ok")

    def test_borde_ventana_2244_no_es_ok(self):
        estado, _ = gdc.clasificar(job_ok(last_run_at="2026-11-10T22:44:59-05:00"), now_fijo())
        self.assertEqual(estado, "no_ejecutado")

    def test_timestamp_sin_zona_asume_la_del_reloj(self):
        estado, detalle = gdc.clasificar(job_ok(last_run_at="2026-11-10T23:08:58"), now_fijo())
        self.assertEqual(estado, "ok", detalle)

    def test_run_tardio_pasada_la_medianoche_sigue_siendo_valido(self):
        """El cron es 0 23 * * *: un tick retrasado a las 00:20 guarda la jornada igual."""
        ahora = datetime.datetime(2026, 11, 11, 0, 25, tzinfo=TZ)
        estado, detalle = gdc.clasificar(job_ok(last_run_at="2026-11-11T00:20:00-05:00"), ahora)
        self.assertEqual(estado, "ok", detalle)

    def test_enabled_como_texto_false_es_pausado(self):
        estado, _ = gdc.clasificar(job_ok(enabled="false", state="scheduled"), now_fijo())
        self.assertEqual(estado, "pausado")

    def test_enabled_como_texto_true_es_ok(self):
        estado, detalle = gdc.clasificar(job_ok(enabled="true"), now_fijo())
        self.assertEqual(estado, "ok", detalle)


class MensajeTest(unittest.TestCase):
    def test_exito_mantiene_la_linea_historica(self):
        res = {p: ("ok", "") for p in ("Ragnar", "Roshi", "Vigía")}
        self.assertEqual(
            gdc.construir_mensaje(res), "✅ Guardado con éxito en los 3 perfiles."
        )

    def test_pausado_se_anuncia_como_pausado(self):
        res = {
            "Ragnar": ("ok", ""),
            "Roshi": ("pausado", "motivo=emergency-stability-pause, último guardado 2026-11-08T23:01"),
            "Vigía": ("fallo", "status=error, err=boom"),
        }
        msg = gdc.construir_mensaje(res)
        self.assertIn("PAUSADO", msg)
        self.assertIn("Roshi", msg)
        self.assertIn("FALLÓ", msg)
        self.assertNotIn("sin confirmar en: Ragnar", msg)

    def test_no_ejecutado_y_ausente_se_distinguen(self):
        res = {
            "Ragnar": ("no_ejecutado", "último guardado 2026-11-09T23:05"),
            "Roshi": ("sin_job", "job no encontrado"),
            "Vigía": ("error_lectura", "json inválido"),
        }
        msg = gdc.construir_mensaje(res)
        self.assertIn("NO EJECUTADO", msg)
        self.assertIn("JOB AUSENTE", msg)
        self.assertIn("ERROR DE LECTURA", msg)

    def test_detalle_multilinea_se_colapsa_a_una_linea(self):
        res = {"Roshi": ("fallo", "traceback:\nlinea1\nlinea2\n" + "x" * 800)}
        msg = gdc.construir_mensaje(res)
        self.assertNotIn("\n", msg)
        self.assertLessEqual(len(msg), 500)

    def test_orden_de_gravedad_en_el_reporte(self):
        res = {
            "A": ("no_ejecutado", "d1"),
            "B": ("fallo", "d2"),
            "C": ("pausado", "d3"),
            "D": ("sin_job", "d4"),
            "E": ("error_lectura", "d5"),
        }
        msg = gdc.construir_mensaje(res)
        orden = [msg.index(f"{k} (") for k in "EDCBA"]
        self.assertEqual(orden, sorted(orden), msg)

    def test_detalle_con_punto_y_coma_no_rompe_la_separacion(self):
        res = {"Roshi": ("fallo", "err=a; b (c)")}
        msg = gdc.construir_mensaje(res)
        self.assertEqual(msg.count("; "), 0)
        self.assertNotIn("(c)", msg)

    def test_sin_perfiles_lo_dice_en_vez_de_cantar_exito(self):
        msg = gdc.construir_mensaje({})
        self.assertIn("no hay perfiles configurados", msg)
        self.assertNotIn("✅", msg)


class MainTest(unittest.TestCase):
    def _perfil(self, tmp: Path, nombre: str, job, roto: bool = False) -> Path:
        carpeta = tmp / nombre.lower()
        (carpeta).mkdir(parents=True, exist_ok=True)
        ruta = carpeta / "jobs.json"
        if roto:
            ruta.write_text("{no es json", encoding="utf-8")
        elif job is None:
            ruta.write_text(json.dumps({"jobs": []}), encoding="utf-8")
        else:
            ruta.write_text(json.dumps({"jobs": [job]}), encoding="utf-8")
        return ruta

    def test_tres_perfiles_ok(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rutas = {
                "Ragnar": self._perfil(tmp, "ragnar", job_ok()),
                "Roshi": self._perfil(tmp, "roshi", job_ok()),
                "Vigía": self._perfil(tmp, "vigia", job_ok()),
            }
            msg = gdc.ejecutar(rutas, now=now_fijo())
            self.assertEqual(msg, "✅ Guardado con éxito en los 3 perfiles.")

    def test_pausado_no_se_confunde_con_fallo(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rutas = {
                "Ragnar": self._perfil(tmp, "ragnar", job_ok()),
                "Roshi": self._perfil(
                    tmp, "roshi", job_ok(enabled=False, state="paused",
                                        paused_reason="emergency-stability-pause")
                ),
                "Vigía": self._perfil(tmp, "vigia", job_ok()),
            }
            msg = gdc.ejecutar(rutas, now=now_fijo())
            self.assertIn("Roshi", msg)
            self.assertIn("PAUSADO", msg)
            self.assertIn("emergency-stability-pause", msg)
            self.assertNotIn("err=n/a", msg)

    def test_json_roto_no_tumba_el_resto(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rutas = {
                "Ragnar": self._perfil(tmp, "ragnar", job_ok()),
                "Roshi": self._perfil(tmp, "roshi", job_ok(), roto=True),
                "Vigía": self._perfil(tmp, "vigia", job_ok()),
            }
            msg = gdc.ejecutar(rutas, now=now_fijo())
            self.assertIn("Roshi", msg)
            self.assertIn("ERROR DE LECTURA", msg)

    def test_job_ausente(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rutas = {"Ragnar": self._perfil(tmp, "ragnar", None)}
            msg = gdc.ejecutar(rutas, now=now_fijo())
            self.assertIn("JOB AUSENTE", msg)

    def test_jobs_json_con_lista_raiz(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            ruta = tmp / "jobs.json"
            ruta.write_text(json.dumps([job_ok()]), encoding="utf-8")
            self.assertIsNotNone(gdc._leer_job(ruta))
            self.assertEqual(gdc.ejecutar({"Ragnar": ruta}, now=now_fijo()),
                             "✅ Guardado con éxito en 1 perfil(es).")

    def test_ruta_inexistente_es_error_de_lectura(self):
        with tempfile.TemporaryDirectory() as td:
            rutas = {"Ragnar": Path(td) / "no-existe.json"}
            msg = gdc.ejecutar(rutas, now=now_fijo())
            self.assertIn("ERROR DE LECTURA", msg)
            self.assertIn("FileNotFoundError", msg)


if __name__ == "__main__":
    unittest.main()
