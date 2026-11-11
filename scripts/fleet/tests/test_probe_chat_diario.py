#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas de la prueba funcional diaria del chat web."""
from __future__ import annotations

import datetime
import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "probe_chat_diario.py"
spec = importlib.util.spec_from_file_location("pcd", SCRIPT)
pcd = importlib.util.module_from_spec(spec)
sys.modules["pcd"] = pcd
spec.loader.exec_module(pcd)


class PayloadTest(unittest.TestCase):
    def test_session_id_unico_por_corrida(self):
        a = pcd.construir_payload(datetime.datetime(2026, 11, 11, 8, 15, 0))
        b = pcd.construir_payload(datetime.datetime(2026, 11, 12, 8, 15, 0))
        self.assertNotEqual(a["session_id"], b["session_id"], "una sesión eterna es justo lo que se quiere evitar")
        self.assertTrue(a["session_id"].startswith("probe-20261111"))

    def test_no_arrastra_historial(self):
        self.assertEqual(pcd.construir_payload()["history"], [])


class EvaluarTest(unittest.TestCase):
    def test_respuesta_valida(self):
        ok, motivo = pcd.evaluar("Nuestros horarios son de lunes a domingo, 24 horas.")
        self.assertTrue(ok, motivo)

    def test_vacia_falla(self):
        self.assertFalse(pcd.evaluar("")[0])
        self.assertFalse(pcd.evaluar(None)[0])

    def test_fallback_de_error_no_pasa(self):
        ok, motivo = pcd.evaluar("En este momento tengo una dificultad técnica. Por favor intenta de nuevo en un momento.")
        self.assertFalse(ok)
        self.assertIn("fallback", motivo)

    def test_respuesta_fuera_de_tema_falla(self):
        ok, motivo = pcd.evaluar("Soy Goldie y te ayudo con bonos.")
        self.assertFalse(ok)
        self.assertIn("sin marcador", motivo)


class MainTest(unittest.TestCase):
    def test_dry_run_no_hace_red(self):
        self.assertEqual(pcd.main(["--dry-run"]), 0)

    def test_error_de_red_devuelve_1(self):
        def explota(*a, **k):
            raise ValueError("sin red")
        original = pcd._post
        pcd._post = explota
        try:
            self.assertEqual(pcd.main(["--url", "https://ejemplo.invalid"]), 1)
        finally:
            pcd._post = original

    def test_respuesta_ok_devuelve_0(self):
        original = pcd._post
        pcd._post = lambda *a, **k: {"reply": "Atendemos 24 horas, todos los días."}
        try:
            self.assertEqual(pcd.main([]), 0)
        finally:
            pcd._post = original


if __name__ == "__main__":
    unittest.main()
