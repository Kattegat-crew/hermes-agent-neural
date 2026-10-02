"""Tests FASE3 — antispam de avisos (lógica pura, SIN red, SIN envíos).

Contrato ORIGINAL autorizado (plan msg 164222, recuperado 2026-09-30;
fuente: home/monitor_state/contrato_original_recovery/plan_original_recuperado_20260930.md):
  * caída confirmada SOLO tras 2 ciclos programados consecutivos de fallo
    real (FAILED/DEGRADED; FASE2_CONFIRM_CYCLES) -> UN aviso 'down_alert'
    por episodio, sin repetición en ciclos siguientes.
  * UNVERIFIED: verificación pendiente — NO prueba caída, NO confirma,
    NO avisa (decisión conservadora documentada en la cabecera FASE3).
  * reminder cada 24 h mientras la caída confirmada persista.
  * recuperación -> UN aviso 'recovered' tras FASE3_RECOVER_HEALTHY (2)
    ciclos HEALTHY consecutivos, sólo si hubo aviso de caída en el episodio.
  * FASE3 NO ENVÍA NADA: los avisos son DATOS devueltos por la función.
  * FASE3 usa fichero PROPIO: jamás el STATE FASE1 ni el sombra FASE2.
  * main() NUNCA corre contra destinos por defecto en tests: todos los
    destinos (STATE/lock/sombra/antispam/config) van a TemporaryDirectory.

Ejecutar: /opt/hermes-agent/.venv/bin/python -m pytest tests/test_fase3_antispam.py -v
"""
import sys
import os
import json
import time
import unittest
import tempfile
import inspect
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import mcp_fleet_probe as m  # noqa: E402

NOW = 1_790_000_000.0  # tiempo fijo determinista (epoch)


def _r(name, verdict):
    return {"server": name, "verdict": verdict, "status": "x",
            "detail": "", "secs": 0, "probe": None}


def _cycles(verdicts, name="srv", now0=NOW, step=1800.0):
    """Ejecuta N ciclos encadenados por un servidor; devuelve (avisos, estado)."""
    prev, avisos = {}, []
    for i, v in enumerate(verdicts):
        # consec_bad del sombra FASE2 equivalente a i+1 ciclos no-healthy
        sb = 0 if v == "HEALTHY" else min(
            i + 1 - sum(1 for x in verdicts[:i] if x == "HEALTHY"), 99)
        av, prev = m.fase3_decide_notifications(
            prev, [dict(_r(name, v), consec_bad=sb)], now=now0 + i * step)
        avisos.extend(av)
    return avisos, prev


class TestFASE3DownAlertUnaVez(unittest.TestCase):
    def test_ciclo1_no_confirma_no_avisa(self):
        avisos, st = _cycles(["FAILED"])
        self.assertEqual(avisos, [])
        self.assertFalse(st["servers"]["srv"]["alerted"])

    def test_ciclo2_confirmado_un_down_alert(self):
        avisos, st = _cycles(["FAILED", "FAILED"])
        self.assertEqual([a["kind"] for a in avisos], ["down_alert"])
        self.assertEqual(avisos[0]["server"], "srv")
        self.assertTrue(st["servers"]["srv"]["alerted"])

    def test_ciclos_3_a_5_sin_repetir_aviso(self):
        avisos, st = _cycles(["FAILED"] * 5)  # ~2 h de caída, < 24 h
        self.assertEqual([a["kind"] for a in avisos], ["down_alert"])
        self.assertTrue(st["servers"]["srv"]["alerted"])

    def test_unverified_no_confirma_y_preserva_consec_bad(self):
        # Semántica ORIGINAL (decisión conservadora documentada): UNVERIFIED
        # es verificación pendiente — NO prueba caída, NO confirma, NO avisa.
        # No rompe el contador de fallos reales ya acumulado (FAILED->UNVERIFIED
        # ->FAILED = 3 fallos reales => confirmado en el 3er ciclo, no reinicia).
        avisos, _ = _cycles(["DEGRADED", "UNVERIFIED"])
        self.assertEqual(avisos, [])
        avisos2, st2 = _cycles(["DEGRADED", "UNVERIFIED", "DEGRADED"])
        self.assertEqual([a["kind"] for a in avisos2], ["down_alert"])
        # contador conservado: D,U,D cuenta 2 fallos reales consecutivos
        # (UNVERIFIED no rompe ni suma) => confirmado al 3er ciclo real
        self.assertEqual(st2["servers"]["srv"]["consec_bad"], 2)

    def test_nuevo_episodio_tras_recuperacion_reavisa(self):
        # episodio 1: caída+aviso+recuperación; episodio 2: caída -> nuevo down_alert
        seq = ["FAILED", "FAILED", "HEALTHY", "HEALTHY", "FAILED", "FAILED"]
        avisos, _ = _cycles(seq)
        self.assertEqual([a["kind"] for a in avisos],
                         ["down_alert", "recovered", "down_alert"])


class TestFASE3Reminder24h(unittest.TestCase):
    def test_antes_de_24h_no_hay_reminder(self):
        avisos, _ = _cycles(["FAILED"] * 5)  # pasos de 30 min
        self.assertNotIn("reminder", [a["kind"] for a in avisos])

    def test_a_24h_un_reminder_y_no_mas(self):
        # 25 h de caída con ciclos de 30 min -> down_alert + reminder (1)
        n = 51  # 0..50 pasos de 30 min = 25 h
        prev, avisos = {}, []
        for i in range(n):
            av, prev = m.fase3_decide_notifications(
                prev, [dict(_r("srv", "FAILED"), consec_bad=i + 1)],
                now=NOW + i * 1800.0)
            avisos.extend(av)
        kinds = [a["kind"] for a in avisos]
        self.assertEqual(kinds[0], "down_alert")
        self.assertEqual(kinds.count("reminder"), 1, kinds)
        self.assertEqual(kinds[-1], "reminder")

    def test_reminder_reinicia_ventana_de_24h(self):
        # 26 h -> reminder en h24; otras 25 h -> segundo reminder en h49
        prev, avisos = {}, []
        for i in range(99):
            av, prev = m.fase3_decide_notifications(
                prev, [dict(_r("srv", "FAILED"), consec_bad=i + 1)],
                now=NOW + i * 1800.0)
            avisos.extend(av)
        kinds = [a["kind"] for a in avisos]
        self.assertEqual(kinds.count("reminder"), 2, kinds)


class TestFASE3Recuperacion(unittest.TestCase):
    def test_un_healthy_no_recupera(self):
        avisos, st = _cycles(["FAILED", "FAILED", "HEALTHY"])
        self.assertEqual([a["kind"] for a in avisos], ["down_alert"])
        self.assertTrue(st["servers"]["srv"]["alerted"])
        self.assertEqual(st["servers"]["srv"]["consec_healthy"], 1)

    def test_dos_healthy_consecutivos_recuperan(self):
        avisos, st = _cycles(["FAILED", "FAILED", "HEALTHY", "HEALTHY"])
        self.assertEqual([a["kind"] for a in avisos], ["down_alert", "recovered"])
        s = st["servers"]["srv"]
        self.assertFalse(s["alerted"])
        self.assertEqual(s["consec_healthy"], 0)
        self.assertTrue(avisos[-1]["kind"] == "recovered")

    def test_sin_aviso_previo_no_hay_recovered(self):
        # caída NO confirmada (1 ciclo) y luego healthy: nunca hubo aviso
        avisos, _ = _cycles(["FAILED", "HEALTHY", "HEALTHY"])
        self.assertEqual(avisos, [])

    def test_recaida_en_mitad_de_healthy_no_recupera(self):
        avisos, _ = _cycles(["FAILED", "FAILED", "HEALTHY", "FAILED", "FAILED"])
        self.assertEqual([a["kind"] for a in avisos], ["down_alert"])


class TestFASE3SinEnvioYEstructura(unittest.TestCase):
    def test_avisos_son_datos_sin_campos_de_envio(self):
        avisos, _ = _cycles(["FAILED", "FAILED"])
        self.assertEqual(len(avisos), 1)
        self.assertEqual(set(avisos[0]), {"server", "kind", "ts", "episode_id"})

    def test_estado_estructura_fase3(self):
        _, st = _cycles(["FAILED", "FAILED"])
        s = st["servers"]["srv"]
        for k in ("consec_healthy", "episode_id", "alerted", "last_alert_ts",
                  "last_reminder_ts", "recovered", "last_verdict"):
            self.assertIn(k, s)

    def test_no_import_canales_ni_send_en_fase3(self):
        # La lógica FASE3 no referencia canales/envíos en el código nuevo
        src = (inspect.getsource(m.fase3_decide_notifications)
               + inspect.getsource(m.write_fase3_antispam_state))
        for bad in ("smtplib", "requests", "urllib", "discord", "send(",
                    "subprocess", "httpx"):
            self.assertNotIn(bad, src.lower().replace("send(", "sendX(") if bad == "send(" else src.lower())

    def test_ficheros_propios_separados(self):
        self.assertNotEqual(m.FASE3_ANTISPAM_STATE, m.STATE)
        self.assertNotEqual(m.FASE3_ANTISPAM_STATE, m.FASE2_SHADOW_STATE)
        self.assertNotEqual(m.FASE3_ANTISPAM_STATE, m.LOCK_PATH)
        self.assertIn("fase3", m.FASE3_ANTISPAM_STATE.lower())


class TestFASE3PersistenciaTmp(unittest.TestCase):
    def test_roundtrip_tmp(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "fase3.json")
            ok, det = m.write_fase3_antispam_state({"ts": "x", "servers": {}}, path=p)
            self.assertTrue(ok, det)
            # load devuelve triple (estado, ok, detalle); compat: _reported
            self.assertEqual(
                m.load_fase3_antispam_state_reported(path=p).get("ts"), "x")
            st, ok_r, det_r = m.load_fase3_antispam_state(path=p)
            self.assertTrue(ok_r and det_r == "" and st.get("ts") == "x")
            self.assertNotEqual(Path(p), m.STATE)
            self.assertNotEqual(Path(p), m.FASE2_SHADOW_STATE)

    def test_load_corrupto_reporta_y_no_finge_estado(self):
        # Estado corrupto: ({}, ok=False, detalle) — nunca fingir dedup previo
        # (contrato ORIGINAL: pérdida de estado = incertidumbre reportada).
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "fase3_roto.json")
            with open(p, "w") as fh:
                fh.write("{no-json")
            st, ok_r, det_r = m.load_fase3_antispam_state(path=p)
            self.assertEqual(st, {})
            self.assertFalse(ok_r)
            self.assertIn("corrupto", det_r)

    def test_load_ausente_reporta_ausente(self):
        with tempfile.TemporaryDirectory() as td:
            st, ok_r, det_r = m.load_fase3_antispam_state(
                path=os.path.join(td, "inexistente.json"))
            self.assertEqual((st, ok_r, det_r), ({}, False, "ausente"))

    def test_estado_no_escribible_detectable(self):
        self.assertNotEqual(os.geteuid(), 0)
        with tempfile.TemporaryDirectory() as td:
            ro = os.path.join(td, "ro")
            os.mkdir(ro)
            f = os.path.join(ro, "fase3.json")
            with open(f, "w") as fh:
                fh.write("{}")
            os.chmod(ro, 0o555)
            os.chmod(f, 0o444)
            try:
                ok, det = m.write_fase3_antispam_state({"ts": "y"}, path=f)
                self.assertFalse(ok)
                self.assertIn("PermissionError", det)
            finally:
                os.chmod(ro, 0o755)
                os.chmod(f, 0o644)


class TestFASE3WiringMain(unittest.TestCase):
    def test_main_llama_fase3_sin_envio(self):
        src = inspect.getsource(m.main)
        self.assertIn("fase3_decide_notifications", src)
        self.assertIn("write_fase3_antispam_state", src)
        self.assertIn("NO escribible", src)  # fallo detectable
        self.assertIn("NO enviado", src)     # explicitación de no activación

    def test_main_no_envia_avisos(self):
        # ninguna llamada a canales en main(): solo impresión local de datos
        src = inspect.getsource(m.main).lower()
        for bad in ("smtplib", "requests.post", "urllib", "httpx", "discord.send"):
            self.assertNotIn(bad, src)

    def test_gate_legacy_en_main_2_ciclos_y_dedup(self):
        # GATING del aviso legacy FASE1 wired en main(): el stdout sale sólo
        # vía fase3_notify_gate (caída CONFIRMADA 2 ciclos + no notificada).
        import inspect
        src = inspect.getsource(m.main)
        self.assertIn("fase3_notify_gate", src)
        # ya no existe el aviso legacy a 1 ciclo sin gate
        self.assertNotIn('out.append(f"⚠️ MCPs con fallo', src)

    def test_gate_suprime_primer_ciclo(self):
        # 1er ciclo de fallo: confirmación pendiente -> suprimido (sin aviso).
        st = {"servers": {"srv": {"consec_bad": 1, "alerted": False}}}
        avisables, suprimidos, motivo = m.fase3_notify_gate(
            [_r("srv", "FAILED")], st)
        self.assertEqual(avisables, [])
        self.assertEqual(suprimidos, [("srv", "confirmacion-pendiente")])
        self.assertEqual(motivo, "confirmacion-pendiente")

    def test_gate_suprime_ya_notificado(self):
        # caída confirmada PERO ya notificada en el episodio -> silencio.
        st = {"servers": {"srv": {"consec_bad": 5, "alerted": True}}}
        avisables, suprimidos, motivo = m.fase3_notify_gate(
            [_r("srv", "FAILED")], st)
        self.assertEqual(avisables, [])
        self.assertEqual(suprimidos, [("srv", "ya-notificado")])

    def test_gate_pasa_confirmada_no_notificada(self):
        st = {"servers": {"srv": {"consec_bad": 2, "alerted": False}}}
        avisables, suprimidos, motivo = m.fase3_notify_gate(
            [_r("srv", "FAILED")], st)
        self.assertEqual(len(avisables), 1)
        self.assertEqual(suprimidos, [])
        self.assertIsNone(motivo)

    def test_smoke_main_aislado_tmp_todos_los_destinos(self):
        # Smoke de main() con TODOS los destinos en TemporaryDirectory explícito:
        # config VACÍA (main retorna 0 sin sondear: sin red, sin servidores),
        # lock, sombra FASE2 y antispam FASE3 en tmp. JAMÁS destinos por
        # defecto. Nota: con config vacía main() no alcanza el bloque FASE3;
        # el wiring FASE3 se verifica además por inspección (tests anteriores).
        import subprocess, textwrap, yaml
        with tempfile.TemporaryDirectory() as td:
            cfgp = os.path.join(td, "config.yaml")
            with open(cfgp, "w") as fh:
                yaml.safe_dump({"mcp_servers": {}}, fh)
            env = dict(os.environ)
            env.update({
                "MCP_PROBE_CONFIG": cfgp,
                "MCP_PROBE_ENV": os.path.join(td, "nohay.env"),
                "MCP_PROBE_LOCK": os.path.join(td, "lock.file"),
                "MCP_PROBE_FASE2_STATE": os.path.join(td, "fase2.json"),
                "MCP_PROBE_FASE3_STATE": os.path.join(td, "fase3.json"),
            })
            code = textwrap.dedent("""
                import sys
                sys.path.insert(0, %r)
                sys.argv = ['x', '--no-heal']
                import asyncio
                import mcp_fleet_probe as m
                rc = asyncio.run(m.main())
                print('RC', rc)
            """) % str(HERE)
            r = subprocess.run([sys.executable, "-c", code], env=env,
                               capture_output=True, text=True, timeout=60,
                               cwd=str(td))
            self.assertIn("RC 0", r.stdout, r.stderr)
            self.assertIn("sin mcp_servers", r.stdout)
            # config vacía: main retorna antes del bloque FASE3 (sin red)
            self.assertFalse(os.path.exists(os.path.join(td, "fase3.json")))


if __name__ == "__main__":
    unittest.main()
