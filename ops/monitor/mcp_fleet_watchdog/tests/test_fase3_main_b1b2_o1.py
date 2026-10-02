"""Pruebas FASE3 r4 (post-minfix): comportamiento main() aislado B1/B2 y
fallo atómico O1. JAMÁS tocan estado runtime vivo: todos los destinos
(STATE/FASE2/FASE3/LOCK/ERRLOG/TOKENS/config) van a TemporaryDirectory y
los globals del módulo se parchean en-process (no subprocess, no env).
Ejecutar con: python3 -m pytest tests/test_fase3_main_b1b2_o1.py -q
"""
import asyncio
import contextlib
import inspect
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mcp_fleet_probe as m  # noqa: E402

N_SRV = "srv_fallo"

# Globals del módulo que parcheamos; se restauran tras cada test para no
# contaminar al resto de la suite (los tests corren en un solo proceso).
_PATCHED = ("STATE", "FASE2_SHADOW_STATE", "FASE3_ANTISPAM_STATE",
            "LOCK_PATH", "ERRLOG", "TOKENS_DIR", "CFG_PATH", "ENV_FILE",
            "evaluate_with_retry", "heal_token_perms")


def _snap():
    return {k: getattr(m, k, None) for k in _PATCHED}


def _restore(snap):
    for k, v in snap.items():
        setattr(m, k, v)


def _config_cfg(td):
    cfg = Path(td) / "config.yaml"
    cfg.write_text("mcp_servers:\n  %s:\n    command: ['true']\n" % N_SRV)
    return cfg


async def _fake_probe(name, spec, expand, timeout=None):
    # Fallo determinista SIN red: nunca invoca comandos reales.
    return {"server": N_SRV, "verdict": "FAILED", "status": "FAIL",
            "tools": None, "detail": "determinista", "secs": 0,
            "probe": "fake", "reason": "fallo inyectado aislado"}


def _patch_to(td):
    """Parchea globals del módulo a tmp (aislamiento garantizado)."""
    td = Path(td)
    m.STATE = td / "state-fase1.json"
    m.FASE2_SHADOW_STATE = str(td / "fase2-shadow.json")
    m.FASE3_ANTISPAM_STATE = str(td / "fase3-antispam.json")
    m.LOCK_PATH = str(td / "lock.file")
    m.ERRLOG = td / "errors.log"
    m.TOKENS_DIR = td / "tokens-vacio"       # heal_token_perms no-op
    m.CFG_PATH = str(_config_cfg(td))
    m.ENV_FILE = str(td / "no.env")
    return td


def _run_cycle():
    # unittest deja sys.argv del runner: parse_args() lo rechazaría.
    argv_orig = sys.argv
    sys.argv = ["mcp-fleet-probe"]
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            m.evaluate_with_retry = _fake_probe
            m.heal_token_perms = lambda: ([], [])
            rc = asyncio.run(m.main())
    finally:
        sys.argv = argv_orig
    return rc, buf.getvalue()


class TestMainAisladoB1B2(unittest.TestCase):
    """4 ciclos FAILED del mismo servidor, in-process, todo en tmp."""

    def setUp(self):
        self._snap = _snap()

    def tearDown(self):
        _restore(self._snap)

    def test_b1_alerta_confirmada_ciclo2_y_no_repite(self):
        with tempfile.TemporaryDirectory() as td:
            _patch_to(td)
            outs = [_run_cycle()[1] for _ in range(4)]
            # B1: aviso de caída CONFIRMADA sale EXACTAMENTE en ciclo 2
            # (confirmación), no antes (ciclo 1) ni repetido (ciclos 3-4).
            self.assertNotIn("CONFIRMADA", outs[0])
            self.assertIn("CONFIRMADA", outs[1])
            self.assertNotIn("CONFIRMADA", outs[2])
            self.assertNotIn("CONFIRMADA", outs[3])

    def test_b2_episode_id_estable_no_none(self):
        with tempfile.TemporaryDirectory() as td:
            td = _patch_to(td)
            for _ in range(4):
                _run_cycle()
            f3 = json.loads((Path(td) / "fase3-antispam.json").read_text())
            s = f3["servers"][N_SRV]
            # B2: episode_id poblado y ESTABLE durante todo el episodio.
            self.assertIsInstance(s.get("episode_id"), str)
            self.assertTrue(s.get("episode_id"))
            self.assertTrue(s.get("alerted"))
            self.assertEqual(s.get("consec_bad"), 4)

    def test_aislamiento_state_runtime_es_tmp(self):
        # Guardia de seguridad: STATE usado nunca es el runtime vivo.
        with tempfile.TemporaryDirectory() as td:
            td = _patch_to(td)
            _run_cycle()
            self.assertEqual(Path(m.STATE).parent, Path(td))
            self.assertTrue(str(m.STATE).startswith(str(Path(td))))


class TestO1EscrituraAtomica(unittest.TestCase):
    def setUp(self):
        self._snap = _snap()

    def tearDown(self):
        _restore(self._snap)

    def test_atomic_write_fallo_devuelve_detalle_no_excepcion(self):
        # STATE apuntando a un DIRECTORIO: os.replace falla -> (False, det).
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "estado.json"
            target.mkdir()
            ok, det = m._atomic_write_json(target, {"x": 1})
            self.assertFalse(ok)
            self.assertTrue(det)

    def test_atomic_write_ok_deja_fichero_valido(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "estado.json"
            ok, det = m._atomic_write_json(target, {"x": 1})
            self.assertTrue(ok, det)
            self.assertEqual(json.loads(target.read_text()), {"x": 1})

    def test_o1_fallo_persistencia_fase1_es_visible_en_main(self):
        # Contrato: fallo de persistencia = fallo del monitor VISIBLE,
        # nunca 'except OSError: pass'.
        with tempfile.TemporaryDirectory() as td:
            td = _patch_to(td)
            # STATE como directorio -> escritura atómica falla.
            (Path(td) / "state-fase1.json").mkdir()
            rc, out = _run_cycle()
            self.assertIn("NO escribible", out)
            self.assertIn("FALLO DEL MONITOR", out)

    def test_o1_wiring_atomico_en_main(self):
        src = inspect.getsource(m.main)
        self.assertIn("_atomic_write_json", src)
        self.assertIn("NO escribible", src)


if __name__ == "__main__":
    unittest.main()
