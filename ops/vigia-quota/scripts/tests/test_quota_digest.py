#!/usr/bin/env python3
"""Tests deterministas de quota_digest (sin red, sin cron, sin Hermes vivo)."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "quota_digest.py"


def load_module(home: Path):
    """Importa quota_digest con HERMES_HOME apuntando a un directorio temporal."""
    import os

    old = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = str(home)
    try:
        spec = importlib.util.spec_from_file_location("quota_digest_under_test", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        if old is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = old


CACHE_FIXTURE = {
    "fetched_at": "2026-11-11T14:48:38.703150+00:00",
    "providers": {
        "openai-codex": {
            "label": "openai-codex",
            "plan": "Plus",
            "account_label": "captain@neuralcrewlabs.com",
            "unavailable_reason": None,
            "details": ["You have 1 reset banked"],
            "windows": [
                {"label": "Session", "used_percent": 79.0, "reset_at": "2026-11-11T18:02:01+00:00"},
                {"label": "Weekly", "used_percent": 28.0, "reset_at": "2026-11-12T04:15:14+00:00"},
            ],
        },
        "opencode-go": {
            "label": "opencode-go",
            "plan": None,
            "unavailable_reason": None,
            "details": [],
            "windows": [
                {"label": "5-hour", "used_percent": 100.0, "reset_at": "2026-11-11T19:48:38+00:00"},
                {"label": "Weekly", "used_percent": 19.0, "reset_at": "2026-11-16T00:00:00+00:00"},
                {"label": "Monthly", "used_percent": 93.0, "reset_at": "2026-11-13T22:59:34+00:00"},
            ],
        },
        "antigravity": {
            "label": "antigravity",
            "plan": None,
            "unavailable_reason": "opt-in-disabled",
            "details": [],
            "windows": [],
        },
    },
}

NAN_FIXTURE = {
    "state": "ok",
    "period_end": "2026-12-01T00:00:00+00:00",
    "worst_level": "red",
    "worst_model": "deepseek-v4-flash",
    "models": [
        {
            "model": "deepseek-v4-flash",
            "pct": 63.4,
            "tokens_used": 1901168238,
            "cap": 3000000000,
            "kind": "period",
            "level": "red",
            "projected_pct": 180.3,
            "pack_tokens": 0,
            "_reset": "2026-12-01T00:00:00+00:00",
        },
        {
            "model": "qwen3.8-flash",
            "pct": 54.0,
            "tokens_used": 269944135,
            "cap": 500000000,
            "kind": "period",
            "level": "ok",
            "projected_pct": 61.0,
            "pack_tokens": 50000000,
            "_reset": "2026-12-01T00:00:00+00:00",
        },
    ],
}


class SubscriptionRowsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mod = load_module(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_windows_se_normalizan_por_suscripcion(self):
        rows = self.mod.subscription_rows(CACHE_FIXTURE)
        by_id = {r["id"]: r for r in rows}
        self.assertEqual([w["label"] for w in by_id["openai-codex"]["windows"]], ["Session", "Weekly"])
        self.assertEqual(by_id["openai-codex"]["plan"], "Plus")
        self.assertEqual(len(by_id["opencode-go"]["windows"]), 3)
        self.assertEqual(by_id["antigravity"]["state"], "unavailable")

    def test_proveedor_ausente_no_revienta(self):
        rows = self.mod.subscription_rows({})
        self.assertTrue(all(r["state"] == "missing" for r in rows))

    def test_niveles_por_porcentaje(self):
        self.assertEqual(self.mod._worst_level(10), "ok")
        self.assertEqual(self.mod._worst_level(80), "amber")
        self.assertEqual(self.mod._worst_level(100), "red")
        self.assertEqual(self.mod._worst_level(None), "ok")


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mod = load_module(Path(self.tmp.name))
        self.now = dt.datetime(2026, 11, 11, 15, 0, tzinfo=dt.timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def test_informe_incluye_las_cuatro_suscripciones(self):
        text = self.mod.render(self.mod.subscription_rows(CACHE_FIXTURE), NAN_FIXTURE, CACHE_FIXTURE["fetched_at"], self.now)
        for needle in ("OpenCode Go", "Codex", "Antigravity", "NaN (nan.builders)"):
            self.assertIn(needle, text)

    def test_ventanas_y_resets_en_hora_local(self):
        text = self.mod.render(self.mod.subscription_rows(CACHE_FIXTURE), NAN_FIXTURE, CACHE_FIXTURE["fetched_at"], self.now)
        self.assertIn("Session: 79% usado", text)
        self.assertIn("hoy 13:02", text)  # 18:02Z == 13:02 Bogotá
        self.assertIn("Monthly: 93% usado", text)

    def test_antigravity_declara_opt_in(self):
        text = self.mod.render(self.mod.subscription_rows(CACHE_FIXTURE), NAN_FIXTURE, CACHE_FIXTURE["fetched_at"], self.now)
        self.assertIn("Antigravity", text)
        self.assertIn("opt-in-disabled", text)

    def test_nan_muestra_tokens_y_packs(self):
        text = self.mod.render(self.mod.subscription_rows(CACHE_FIXTURE), NAN_FIXTURE, CACHE_FIXTURE["fetched_at"], self.now)
        self.assertIn("1.90B/3.00B", text)
        self.assertIn("proy. 180.3%", text)
        self.assertIn("pack 50M", text)
        self.assertIn("cookie de sesión", text)

    def test_nan_caido_no_rompe_el_informe(self):
        broken = {"state": "error", "reason": "HTTPError 500"}
        text = self.mod.render(self.mod.subscription_rows(CACHE_FIXTURE), broken, None, self.now)
        self.assertIn("no disponible (HTTPError 500)", text)
        self.assertIn("Codex", text)  # el resto sigue saliendo

    def test_ventana_nan_usa_su_propio_reset(self):
        """Un modelo de ventana móvil no debe fechar el reset del periodo."""
        nan = {
            "state": "ok",
            "period_end": "2026-12-01T00:00:00+00:00",
            "worst_level": "ok",
            "models": [
                {
                    "model": "glm5.3",
                    "pct": 0.0,
                    "kind": "window",
                    "level": "ok",
                    "resets_at": "2026-11-14T20:36:42+00:00",
                    "period_resets_at": "2026-12-01T00:00:00+00:00",
                }
            ],
        }
        text = self.mod.render([], nan, None, self.now)
        self.assertIn("14-Nov 15:36", text)
        self.assertNotIn("30-Nov", text)

    def test_periodo_nan_ignora_period_end_contaminado(self):
        """period_end puede traer el reset de una ventana móvil: manda el del modelo."""
        nan = {
            "state": "ok",
            "period_end": "2026-11-14T20:36:42+00:00",  # contaminado por la ventana
            "worst_level": "ok",
            "models": [
                {
                    "model": "glm5.3",
                    "pct": 0.0,
                    "kind": "window",
                    "level": "ok",
                    "resets_at": "2026-11-14T20:36:42+00:00",
                },
                {
                    "model": "deepseek-v4-flash",
                    "pct": 10.0,
                    "kind": "period",
                    "level": "ok",
                    "resets_at": "2026-12-01T00:00:00+00:00",
                },
            ],
        }
        text = self.mod.render([], nan, None, self.now)
        # La ventana usa su reset; el periodo usa el suyo (no el period_end contaminado).
        self.assertIn("glm5.3: 0.0% de la ventana (reset 14-Nov 15:36)", text)
        period_line = next(line for line in text.splitlines() if "deepseek-v4-flash" in line)
        self.assertNotIn("14-Nov", period_line)

    def test_used_percent_corrupto_no_revienta(self):
        cache = {
            "providers": {
                "openai-codex": {
                    "label": "openai-codex",
                    "unavailable_reason": None,
                    "windows": [{"label": "Session", "used_percent": "no-se", "reset_at": None}],
                }
            }
        }
        text = self.mod.render(self.mod.subscription_rows(cache), NAN_FIXTURE, None, self.now)
        self.assertIn("Session: —", text)

    def test_informe_largo_no_pasa_de_1900_chars(self):
        """20 modelos NaN no deben truncar el pie del mensaje en Discord."""
        models = [
            {
                "model": f"modelo-{i}",
                "pct": 1.0,
                "cap": 100000,
                "kind": "period",
                "level": "ok",
                "projected_pct": 2.0,
                "resets_at": "2026-12-01T00:00:00+00:00",
            }
            for i in range(20)
        ]
        nan = {"state": "ok", "period_end": "2026-12-01T00:00:00+00:00", "worst_level": "ok", "models": models}
        text = self.mod.render(self.mod.subscription_rows(CACHE_FIXTURE), nan, CACHE_FIXTURE["fetched_at"], self.now)
        self.assertLessEqual(len(text), 1900)
        self.assertIn("y 10 modelos más", text)
        self.assertIn("datos:", text)  # el pie sobrevive


class NanSnapshotTest(unittest.TestCase):
    def test_extra_tokens_llega_al_snapshot(self):
        sys.path.insert(0, str(Path("/opt/hermes-agent-data/scripts")))
        import nan_quota

        quota = {
            "periodStart": "2026-11-01",
            "models": [
                {
                    "model": "m1",
                    "tokensUsed": 10,
                    "cap": 100,
                    "remaining": 90,
                    "periodEnd": "2026-12-01T00:00:00Z",
                    "extraTokens": 5000,
                    "extraUsable": True,
                }
            ],
        }
        snap = nan_quota.analyze(quota)
        self.assertEqual(snap["models"][0]["extra_tokens"], 5000)
        self.assertIs(snap["models"][0]["extra_usable"], True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
