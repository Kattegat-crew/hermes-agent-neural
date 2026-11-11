#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas de session_reset.py (F1.5) con bases sqlite temporales.

Cubre el cambio del 11-nov-2026 pedido por el Admin:
  · el umbral de tokens baja a 300 k
  · al superar el umbral se cierra SIN exigir hora de inactividad
  · el perfil `default` (Admin) entra al reset, con su memoria en la raíz de datos

Ejecutar:  python3.12 -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "session_reset.py"
spec = importlib.util.spec_from_file_location("session_reset", SCRIPT)
assert spec is not None and spec.loader is not None, f"no puedo cargar {SCRIPT}"
sr = importlib.util.module_from_spec(spec)
sys.modules["session_reset"] = sr
spec.loader.exec_module(sr)

AHORA = time.time()


def _db(path: Path, filas):
    """Crea un state.db mínimo con la tabla sessions que lee el script."""
    con = sqlite3.connect(path)
    con.execute(
        """CREATE TABLE sessions (
               id INTEGER PRIMARY KEY, session_key TEXT, started_at REAL,
               last_activity_at REAL, message_count INTEGER,
               input_tokens INTEGER, output_tokens INTEGER, ended_at REAL)"""
    )
    for f in filas:
        con.execute(
            "INSERT INTO sessions (session_key, started_at, last_activity_at, message_count,"
            " input_tokens, output_tokens, ended_at) VALUES (?,?,?,?,?,?,?)",
            (f.get("key", "agent:x:discord:dm:1"), f.get("started", AHORA - 7200),
             f.get("activity", AHORA - 300), f.get("msgs", 40),
             f.get("tokens", 10_000), 0, f.get("ended")),
        )
    con.commit()
    con.close()


class UmbralTokensTest(unittest.TestCase):
    def test_sesion_gorda_activa_se_cierra_por_tokens_sin_exigir_hora(self):
        """El caso Goldie/Lucky: 5,68 M de tokens y actividad de hace 1 min."""
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "state.db"
            _db(db, [{"tokens": 5_680_000, "activity": AHORA - 60}])
            cands = sr.candidatas(db, 24)
            self.assertEqual(len(cands), 1, "una sesión de 5,68 M debe entrar al reset")
            self.assertEqual(cands[0]["motivo"], "tokens")

    def test_justo_por_debajo_del_umbral_no_entra(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "state.db"
            _db(db, [{"tokens": 299_999, "activity": AHORA - 1800}])
            self.assertEqual(sr.candidatas(db, 24), [])

    def test_umbral_exacto_entra(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "state.db"
            _db(db, [{"tokens": 300_000, "activity": AHORA - 60}])
            self.assertEqual(len(sr.candidatas(db, 24)), 1)

    def test_umbral_por_defecto_es_300k(self):
        self.assertEqual(sr.MAX_TOKENS, 300_000)

    def test_sesion_sin_session_key_no_se_toca_aunque_sea_gorda(self):
        """Las filas de sistema (sin session_key) no son chats: nunca se cierran."""
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "state.db"
            _db(db, [{"key": "", "tokens": 900_000, "activity": AHORA - 60}])
            self.assertEqual(sr.candidatas(db, 24), [])


class CaminoPorEdadTest(unittest.TestCase):
    def test_vieja_e_inactiva_se_cierra(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "state.db"
            _db(db, [{"tokens": 10_000, "started": AHORA - 30 * 3600, "activity": AHORA - 3 * 3600}])
            cands = sr.candidatas(db, 24)
            self.assertEqual([c["motivo"] for c in cands], ["edad"])

    def test_vieja_pero_activa_no_se_parte(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "state.db"
            _db(db, [{"tokens": 10_000, "started": AHORA - 30 * 3600, "activity": AHORA - 300}])
            self.assertEqual(sr.candidatas(db, 24), [])

    def test_sesion_ya_cerrada_no_reaparece(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "state.db"
            _db(db, [{"tokens": 900_000, "activity": AHORA - 60, "ended": AHORA - 30}])
            self.assertEqual(sr.candidatas(db, 24), [])


class PerfilDefaultTest(unittest.TestCase):
    def _flota(self, tmp: Path, con_default: bool):
        (tmp / "profiles" / "golden-game").mkdir(parents=True)
        (tmp / "profiles" / "golden-game" / "state.db").write_bytes(b"")
        (tmp / "profiles" / "neural-admin-test").mkdir(parents=True)
        (tmp / "profiles" / "neural-admin-test" / "state.db").write_bytes(b"")
        if con_default:
            (tmp / "state.db").write_bytes(b"")

    def test_default_entra_en_la_flota_y_solo_se_excluye_el_perfil_de_pruebas(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._flota(tmp, con_default=True)
            self.assertEqual(sr.clientes_flota(tmp), ["default", "golden-game"])

    def test_sin_state_db_raiz_no_hay_default(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._flota(tmp, con_default=False)
            self.assertEqual(sr.clientes_flota(tmp), ["golden-game"])

    def test_default_no_se_duplica_si_existe_profiles_default_legado(self):
        """Si quedó un profiles/default/state.db legado, la raíz no debe auditarse dos veces."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._flota(tmp, con_default=True)
            (tmp / "profiles" / "default").mkdir(parents=True)
            (tmp / "profiles" / "default" / "state.db").write_bytes(b"")
            self.assertEqual(sr.clientes_flota(tmp).count("default"), 1)

    def test_db_de_default_apunta_a_la_raiz(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self.assertEqual(sr.db_de("default", tmp), tmp / "state.db")
            self.assertEqual(sr.db_de("golden-game", tmp), tmp / "profiles" / "golden-game" / "state.db")


class MemoriaTest(unittest.TestCase):
    def _job(self, base: Path, perfil: str, job_id="abc123", contenido="x" * 1500):
        pdir = base if perfil == "default" else base / "profiles" / perfil
        (pdir / "cron" / "output" / job_id).mkdir(parents=True, exist_ok=True)
        (pdir / "cron" / "jobs.json").write_text(json.dumps(
            {"jobs": [{"id": job_id, "name": "guardar-diario-memoria", "last_status": "ok"}]}
        ))
        art = pdir / "cron" / "output" / job_id / "2026-11-11_2304.md"
        art.write_text(contenido)
        return art

    def test_memoria_de_perfil_normal_acredita(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._job(tmp, "golden-game")
            ok, det = sr.memoria_reciente("golden-game", 20, tmp)
            self.assertTrue(ok, det)

    def test_memoria_de_default_lee_la_raiz_de_datos(self):
        """El job del Admin no vive bajo profiles/: si no se mira la raíz, default se omitiría siempre."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._job(tmp, "default")
            ok, det = sr.memoria_reciente("default", 20, tmp)
            self.assertTrue(ok, det)

    def test_sin_job_no_acredita(self):
        with tempfile.TemporaryDirectory() as td:
            ok, det = sr.memoria_reciente("golden-game", 20, Path(td))
            self.assertFalse(ok)
            self.assertIn("jobs.json", det)

    def test_artefacto_bloqueado_no_acredita(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._job(tmp, "golden-game", contenido="**Status:** BLOCKED (configuration)\n" + "y" * 1200)
            ok, det = sr.memoria_reciente("golden-game", 20, tmp)
            self.assertFalse(ok)
            self.assertIn("BLOQUEADA", det)

    def test_artefacto_enano_no_acredita(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._job(tmp, "golden-game", contenido="corto")
            self.assertFalse(sr.memoria_reciente("golden-game", 20, tmp)[0])

    def test_corrida_vieja_no_acredita(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            art = self._job(tmp, "golden-game")
            viejo = time.time() - 30 * 3600
            os.utime(art, (viejo, viejo))
            self.assertFalse(sr.memoria_reciente("golden-game", 20, tmp)[0])


class MainTest(unittest.TestCase):
    """El loop de main(): no aborta con un perfil roto y el modo --quiet calla de verdad."""

    class _FakeDB:
        cerradas: list = []

        def __init__(self, db_path=None):
            self.db_path = db_path

        def promote_to_session_reset(self, id, reason=None):
            MainTest._FakeDB.cerradas.append(id)
            return True

        def close(self):
            pass

    def setUp(self):
        import io
        import types
        from contextlib import redirect_stdout
        self.io, self.redirect_stdout = io, redirect_stdout
        self._prev = sys.modules.get("hermes_state")
        falso = types.ModuleType("hermes_state")
        falso.SessionDB = self._FakeDB  # type: ignore[attr-defined]
        sys.modules["hermes_state"] = falso
        MainTest._FakeDB.cerradas = []

    def tearDown(self):
        if self._prev is None:
            sys.modules.pop("hermes_state", None)
        else:
            sys.modules["hermes_state"] = self._prev

    def _correr(self, argv):
        buf = self.io.StringIO()
        try:
            with self.redirect_stdout(buf):
                sr.main(argv)
        finally:
            pass
        return buf.getvalue()

    def test_perfil_corrupto_no_aborta_el_resto(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "profiles" / "good").mkdir(parents=True)
            _db(tmp / "profiles" / "good" / "state.db", [{"tokens": 900_000, "activity": AHORA - 60}])
            (tmp / "profiles" / "roto").mkdir(parents=True)
            (tmp / "profiles" / "roto" / "state.db").write_bytes(b"esto no es sqlite")
            salida = self._correr(["--data-base", str(tmp), "--profile", "roto", "--profile", "good",
                                   "--apply", "--force"])
            self.assertIn("sin lectura de sesiones", salida)
            self.assertIn("RESET OK", salida)
            self.assertEqual(len(MainTest._FakeDB.cerradas), 1)

    def test_quiet_calla_si_no_hay_nada_ni_problemas(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "profiles" / "vacio").mkdir(parents=True)
            _db(tmp / "profiles" / "vacio" / "state.db", [])
            self.assertEqual(self._correr(["--data-base", str(tmp), "--profile", "vacio", "--quiet"]), "")

    def test_quiet_no_calla_un_problema(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "profiles" / "roto").mkdir(parents=True)
            (tmp / "profiles" / "roto" / "state.db").write_bytes(b"no sqlite")
            salida = self._correr(["--data-base", str(tmp), "--profile", "roto", "--quiet"])
            self.assertIn("PROBLEMAS", salida)


if __name__ == "__main__":
    unittest.main()
