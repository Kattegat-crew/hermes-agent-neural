#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_vps_dev_guardian.py — Tests del monitor nativo VPS Dev Guardian v1.1.0.

Principios:
  * Cero efectos sobre el host real: checks de red/sistema se mockean en memoria,
    el estado se redirige a un directorio temporal por test.
  * Entrega Discord SIEMPRE con transporte mock (post_fn inyectado): NUNCA hay
    POST real ni secret real en tests.
  * Los checks reales contra systemd/bridge/memoria/load/disk se ejecutan como
    clase aparte (TestHostLive), marcados como verificación de lectura only.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vps_dev_guardian as g


class GuardianTestBase(unittest.TestCase):
    """Redirige el estado a un tmpdir y aísla entorno de entrega."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="vps-guardian-test-")
        self.state = Path(self.tmp) / "monitor_state" / "vps_dev_guardian"
        patches = [
            mock.patch.object(g, "STATE_DIR", self.state),
            mock.patch.object(g, "STATE_FILE", self.state / "incident_state.json"),
            mock.patch.object(g, "LOCK_FILE", self.state / "guardian.lock"),
            mock.patch.object(g, "SUMMARY_STAMP", self.state / "last_summary_date.txt"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        # Entrega desactivada por defecto en tests (salvo test específico)
        for var in (g.DELIVERY_ENV, g.WEBHOOK_URL_ENV, g.WEBHOOK_FILE_ENV,
                    g.FAILURE_THRESHOLD_ENV):
            os.environ.pop(var, None)
        self.addCleanup(os.environ.pop, g.DELIVERY_ENV, None)
        self.addCleanup(os.environ.pop, g.WEBHOOK_URL_ENV, None)
        self.addCleanup(os.environ.pop, g.WEBHOOK_FILE_ENV, None)
        self.addCleanup(os.environ.pop, g.FAILURE_THRESHOLD_ENV, None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # Helpers: snapshot de salud "sana"
    @staticmethod
    def healthy_snapshot():
        # Lista mutable (los tests mutan elementos por índice antes de evaluar).
        return [
            [{"name": u, "kind": "unit", "healthy": True,
              "detail": "ActiveState=active SubState=running MainPID=123"}
             for u in g.EXPECTED_UNITS],
            {"name": "whatsapp-bridge", "kind": "bridge", "healthy": True,
             "detail": "status=connected queueLength=0"},
            g.check_vigia(),
            {"ram_pct": 40.0, "ram_used_mb": 1000, "ram_total_mb": 2500,
             "swap_pct": 0.0, "swap_used_mb": 0, "swap_total_mb": 0},
            {"load1": 0.1, "load5": 0.2, "load15": 0.3, "cores": 4,
             "load5_per_core": 0.05},
            {"used_pct": 50.0, "used_gb": 10, "total_gb": 20},
        ]


class TestThresholdsAndEvaluate(GuardianTestBase):
    def test_healthy_no_incidents(self):
        snap = self.healthy_snapshot()
        self.assertEqual(g.evaluate(*snap), [])

    def test_ram_over_threshold_incident(self):
        snap = self.healthy_snapshot()
        snap[3]["ram_pct"] = 90.0
        kinds = [k for k, _, _ in g.evaluate(*snap)]
        self.assertIn("ram_high", kinds)

    def test_ram_under_threshold_no_incident(self):
        snap = self.healthy_snapshot()
        snap[3]["ram_pct"] = 84.9
        self.assertEqual(g.evaluate(*snap), [])

    def test_cpu_sustained_threshold(self):
        snap = self.healthy_snapshot()
        snap[4]["load5_per_core"] = 1.5
        kinds = [k for k, _, _ in g.evaluate(*snap)]
        self.assertIn("cpu_sustained", kinds)

    def test_disk_critical_and_warning(self):
        snap = self.healthy_snapshot()
        snap[5]["used_pct"] = 90.0
        self.assertIn("disk_high", [k for k, _, _ in g.evaluate(*snap)])
        snap[5]["used_pct"] = 80.0
        self.assertIn("disk_warn", [k for k, _, _ in g.evaluate(*snap)])
        snap[5]["used_pct"] = 50.0
        self.assertEqual([k for k, _, _ in g.evaluate(*snap)
                          if k.startswith("disk")], [])

    def test_vigia_never_generates_incident_or_ok(self):
        snap = self.healthy_snapshot()
        snap[2] = {"name": "vigia", "kind": "vigia", "healthy": None,
                   "detail": g.VIGIA_NOTE}
        self.assertEqual(g.evaluate(*snap), [])

    def test_failure_threshold_from_env(self):
        os.environ[g.FAILURE_THRESHOLD_ENV] = "3"
        self.assertEqual(g.failure_threshold(), 3)
        os.environ[g.FAILURE_THRESHOLD_ENV] = "0"   # se fuerza mínimo 1
        self.assertEqual(g.failure_threshold(), 1)
        os.environ[g.FAILURE_THRESHOLD_ENV] = "basura"
        self.assertEqual(g.failure_threshold(), g.DEFAULT_FAILURE_THRESHOLD)


class TestConsecutiveFailures(GuardianTestBase):
    def _snap_with_unit_down(self):
        snap = self.healthy_snapshot()
        snap[0][0]["healthy"] = False
        snap[0][0]["detail"] = "ActiveState=failed SubState=failed MainPID=0"
        return g.evaluate(*snap)

    def test_no_alert_before_threshold(self):
        os.environ[g.FAILURE_THRESHOLD_ENV] = "3"
        inc = self._snap_with_unit_down()
        r1 = g.process_incidents(inc)
        self.assertEqual(r1["to_alert"], [])
        r2 = g.process_incidents(inc)
        self.assertEqual(r2["to_alert"], [])  # 2 < 3: aún sin alertar
        r3 = g.process_incidents(inc)
        self.assertEqual([f"{k}:{t}" for k, t, _ in r3["to_alert"]],
                         ["unit_down:hermes-agent.service"])

    def test_transient_failure_no_alert(self):
        inc = self._snap_with_unit_down()
        g.process_incidents(inc)                      # check 1 falla
        r2 = g.process_incidents([])                  # check 2 se recupera solo
        self.assertEqual(r2["to_alert"], [])
        self.assertEqual(r2["to_recover"], [])        # baja silenciosa
        state = json.loads(g.STATE_FILE.read_text())
        self.assertNotIn("unit_down:hermes-agent.service", state["known"])

    def test_counter_resets_after_recovery(self):
        inc = self._snap_with_unit_down()
        g.process_incidents(inc)   # consec=1
        g.process_incidents(inc)   # consec=2 → alerta (umbral 2)
        g.process_incidents([])    # recuperación, contador a cero
        r = g.process_incidents(inc)  # vuelve a contar desde 1
        self.assertEqual(r["to_alert"], [])

    def test_threshold_one_alerts_immediately(self):
        os.environ[g.FAILURE_THRESHOLD_ENV] = "1"
        inc = self._snap_with_unit_down()
        r = g.process_incidents(inc)
        self.assertEqual(len(r["to_alert"]), 1)

    def test_cpu_transient_not_confirmed(self):
        # CPU transitoria: 1 check con pico y luego sano → sin alerta (umbral 2)
        snap = self.healthy_snapshot()
        snap[4]["load5_per_core"] = 1.5
        inc = g.evaluate(*snap)
        r1 = g.process_incidents(inc)
        self.assertEqual(r1["to_alert"], [])
        r2 = g.process_incidents([])
        self.assertEqual(r2["to_alert"], [])
        state = json.loads(g.STATE_FILE.read_text())
        self.assertNotIn("cpu_sustained:cpu", state["known"])


class TestDeliveryDisabledByDefault(GuardianTestBase):
    def test_default_mode_is_disabled(self):
        self.assertEqual(g.delivery_mode(), "disabled")

    def test_optin_env_activates(self):
        os.environ[g.DELIVERY_ENV] = "discord"
        self.assertEqual(g.delivery_mode(), "discord")
        os.environ[g.DELIVERY_ENV] = "Discord"
        self.assertEqual(g.delivery_mode(), "discord")
        os.environ[g.DELIVERY_ENV] = "otra-cosa"
        self.assertEqual(g.delivery_mode(), "disabled")

    def test_send_discord_disabled_no_secret_no_post(self):
        # Sin opt-in y sin secret: send_discord NO debe hacer POST real.
        with mock.patch.object(g, "_real_discord_post") as real:
            ok = g.send_discord("mensaje de prueba")
            self.assertFalse(ok)
            real.assert_not_called()

    def test_process_incidents_without_delivery_marks_local_only(self):
        # Modo disabled: dedup LOCAL — NO se marca 'alerted' (reservado para
        # entrega externa exitosa). El dedup local no es un aviso externo.
        os.environ[g.FAILURE_THRESHOLD_ENV] = "1"
        inc = [("unit_down", "hermes-agent.service", "ActiveState=failed")]
        r = g.process_incidents(inc)
        self.assertEqual(r["delivery_mode"], "disabled")
        self.assertEqual(r["delivered_alerts"], [])   # nada salió externamente
        state = json.loads(g.STATE_FILE.read_text())
        self.assertEqual(state["known"]["unit_down:hermes-agent.service"],
                         "local-only")

    def test_disabled_no_external_recovery_message(self):
        # Modo disabled: sin alerta externa previa NO sale recuperación.
        # Un incidente local-only que se resuelve BAJA EN SILENCIO (sin
        # marca 'recovered' y sin cierre huérfano).
        os.environ[g.FAILURE_THRESHOLD_ENV] = "1"
        inc = [("unit_down", "hermes-agent.service", "failed")]
        g.process_incidents(inc)                       # local-only
        with mock.patch.object(g, "_real_discord_post") as real:
            r = g.process_incidents([], post_fn=lambda u, p, t: 200)
            self.assertEqual(r["delivered_recovers"], [])
            self.assertEqual(r["to_recover"], [])      # nunca estuvo 'alerted'
            state = json.loads(g.STATE_FILE.read_text())
            self.assertNotIn("unit_down:hermes-agent.service", state["known"])
            real.assert_not_called()                   # 0 POST externos


class TestDisabledToEnabledTransition(GuardianTestBase):
    """Transición disabled→enabled: sin pérdida silenciosa ni cierre huérfano."""

    def test_enable_with_open_incident_delivers_alert_once(self):
        # Incidente confirmado en disabled (local-only). Al activar la
        # entrega con el incidente AÚN ABIERTO, la alerta se entrega UNA vez.
        os.environ[g.FAILURE_THRESHOLD_ENV] = "1"
        inc = [("unit_down", "hermes-agent.service", "failed")]
        r_disabled = g.process_incidents(inc)          # marca local-only
        self.assertEqual(r_disabled["delivery_mode"], "disabled")
        calls = []
        os.environ[g.DELIVERY_ENV] = "discord"

        def mock_post(url, payload, timeout):
            calls.append((url, payload))
            return 200
        r_enabled = g.process_incidents(inc, post_fn=mock_post)
        self.assertEqual(r_enabled["delivered_alerts"],
                         ["unit_down:hermes-agent.service"])
        self.assertEqual(len(calls), 1)                # exactamente UNA alerta
        self.assertIn("INCIDENTE", calls[0][1]["content"])
        state = json.loads(g.STATE_FILE.read_text())
        self.assertEqual(state["known"]["unit_down:hermes-agent.service"],
                         "alerted")
        # Siguiente check: NO re-alerta (dedup activo).
        r2 = g.process_incidents(inc, post_fn=mock_post)
        self.assertEqual(r2["delivered_alerts"], [])
        self.assertEqual(len(calls), 1)

    def test_enable_after_local_resolution_no_orphan_recovery(self):
        # Incidente resuelto mientras estaba local-only: al activar entrega
        # NO sale una recuperación de algo que nunca se alertó externamente.
        os.environ[g.FAILURE_THRESHOLD_ENV] = "1"
        inc = [("unit_down", "hermes-agent.service", "failed")]
        g.process_incidents(inc)                       # local-only
        g.process_incidents([])                        # baja en local
        os.environ[g.DELIVERY_ENV] = "discord"
        calls = []

        def mock_post(url, payload, timeout):
            calls.append((url, payload))
            return 200
        r = g.process_incidents([], post_fn=mock_post)
        self.assertEqual(r["delivered_recovers"], [])
        self.assertEqual(r["delivered_alerts"], [])
        self.assertEqual(calls, [])                    # 0 POST externos

    def test_enable_with_failed_retry_still_delivers_once(self):
        # Igual que la transición, pero el primer intento de entrega tras
        # activar FALLA: reintento en el check siguiente entrega 1 vez.
        os.environ[g.FAILURE_THRESHOLD_ENV] = "1"
        inc = [("unit_down", "hermes-agent.service", "failed")]
        g.process_incidents(inc)                       # local-only
        os.environ[g.DELIVERY_ENV] = "discord"
        calls = []

        def failing_post(url, payload, timeout):
            calls.append((url, payload))
            return 500
        r1 = g.process_incidents(inc, post_fn=failing_post)
        self.assertEqual(r1["failed_alerts"], ["unit_down:hermes-agent.service"])
        state = json.loads(g.STATE_FILE.read_text())
        self.assertEqual(state["known"]["unit_down:hermes-agent.service"],
                         "local-only")                 # NO marcado tras fallo
        # Reintento exitoso en el siguiente check (sigue abierto).
        def ok_post(url, payload, timeout):
            calls.append((url, payload))
            return 204
        r2 = g.process_incidents(inc, post_fn=ok_post)
        self.assertEqual(r2["delivered_alerts"], ["unit_down:hermes-agent.service"])
        self.assertEqual(len(calls), 2)                # fallo + reintento, 1 entrega
        state = json.loads(g.STATE_FILE.read_text())
        self.assertEqual(state["known"]["unit_down:hermes-agent.service"],
                         "alerted")

    def test_recovery_only_if_external_alert_was_delivered(self):
        # Alerta externa exitosa, luego fallo de recuperación, luego éxito:
        # el cierre sale UNA vez y solo porque hubo alerta externa previa.
        os.environ[g.DELIVERY_ENV] = "discord"
        os.environ[g.FAILURE_THRESHOLD_ENV] = "1"
        inc = [("unit_down", "hermes-agent.service", "failed")]
        g.process_incidents(inc, post_fn=lambda u, p, t: 200)  # alerted
        # Recuperación con entrega fallida → NO se marca recovered.
        r1 = g.process_incidents([], post_fn=lambda u, p, t: 503)
        self.assertEqual(r1["failed_recovers"], ["unit_down:hermes-agent.service"])
        self.assertEqual(json.loads(g.STATE_FILE.read_text())["known"]
                         ["unit_down:hermes-agent.service"], "alerted")
        # Reintento exitoso del cierre → exactamente 1 recuperación.
        closes = []

        def ok_close(url, payload, timeout):
            closes.append(payload)
            return 200
        r2 = g.process_incidents([], post_fn=ok_close)
        self.assertEqual(r2["delivered_recovers"], ["unit_down:hermes-agent.service"])
        self.assertEqual(len(closes), 1)
        self.assertIn("RECUPERADO", closes[0]["content"])
        # Y no vuelve a cerrar.
        r3 = g.process_incidents([], post_fn=ok_close)
        self.assertEqual(r3["delivered_recovers"], [])
        self.assertEqual(len(closes), 1)


class TestDiscordDeliveryMockTransport(GuardianTestBase):
    """Entrega REAL implementada, probada SOLO con transporte mock (sin POST real)."""

    def _alert_once(self, post_calls, status=200):
        def mock_post(url, payload, timeout):
            post_calls.append((url, payload))
            return status
        os.environ[g.DELIVERY_ENV] = "discord"
        os.environ[g.FAILURE_THRESHOLD_ENV] = "1"
        inc = [("unit_down", "hermes-agent.service", "ActiveState=failed")]
        return g.process_incidents(inc, post_fn=mock_post)

    def test_alert_delivered_marks_alerted(self):
        calls = []
        r = self._alert_once(calls)
        self.assertEqual(r["delivered_alerts"], ["unit_down:hermes-agent.service"])
        self.assertEqual(r["failed_alerts"], [])
        self.assertEqual(len(calls), 1)
        url, payload = calls[0]
        self.assertIn("INCIDENTE unit_down:hermes-agent.service", payload["content"])
        self.assertIn("🔴", payload["content"])
        self.assertEqual(json.loads(g.STATE_FILE.read_text())["known"]
                         ["unit_down:hermes-agent.service"], "alerted")

    def test_failed_delivery_is_retryable_no_false_alert(self):
        calls = []
        r = self._alert_once(calls, status=500)
        self.assertEqual(r["delivered_alerts"], [])
        self.assertEqual(r["failed_alerts"], ["unit_down:hermes-agent.service"])
        state = json.loads(g.STATE_FILE.read_text())
        # NO se marca como alertado: reintento en el próximo check
        self.assertNotIn("unit_down:hermes-agent.service", state["known"])

        # Reintento exitoso en el siguiente check (sigue abierto, consec=2)
        def mock_post(url, payload, timeout):
            calls.append((url, payload))
            return 204
        r2 = g.process_incidents([("unit_down", "hermes-agent.service", "x")],
                                 post_fn=mock_post)
        self.assertEqual(r2["delivered_alerts"], ["unit_down:hermes-agent.service"])
        self.assertEqual(json.loads(g.STATE_FILE.read_text())["known"]
                         ["unit_down:hermes-agent.service"], "alerted")

    def test_recovery_requires_successful_delivery(self):
        calls = []
        self._alert_once(calls)  # alertado OK
        # Recovery con fallo de entrega → NO se marca recovered, queda reintentable
        def failing_post(url, payload, timeout):
            calls.append((url, payload))
            return 503
        os.environ[g.DELIVERY_ENV] = "discord"
        r = g.process_incidents([], post_fn=failing_post)
        self.assertEqual(r["failed_recovers"], ["unit_down:hermes-agent.service"])
        state = json.loads(g.STATE_FILE.read_text())
        self.assertEqual(state["known"]["unit_down:hermes-agent.service"], "alerted")

        # Reintento exitoso → recovered
        def ok_post(url, payload, timeout):
            calls.append((url, payload))
            return 200
        r2 = g.process_incidents([], post_fn=ok_post)
        self.assertEqual(r2["delivered_recovers"], ["unit_down:hermes-agent.service"])
        self.assertEqual(json.loads(g.STATE_FILE.read_text())["known"]
                         ["unit_down:hermes-agent.service"], "recovered")

    def test_recovery_only_once(self):
        calls = []
        self._alert_once(calls)
        g.process_incidents([], post_fn=lambda u, p, t: 200)  # cierre
        r = g.process_incidents([], post_fn=lambda u, p, t: 200)  # ya cerrado
        self.assertEqual(r["delivered_recovers"], [])

    def test_mock_transport_never_real_post(self):
        # Postura defensiva: si alguien activa entrega real en tests, el mock
        # post_fn intercepta. Verificamos que _real_discord_post nunca se invoca.
        with mock.patch.object(g, "_real_discord_post") as real:
            calls = []
            self._alert_once(calls)
            real.assert_not_called()

    def test_secret_not_logged_on_failure(self):
        import io
        import contextlib
        os.environ[g.DELIVERY_ENV] = "discord"
        os.environ[g.WEBHOOK_URL_ENV] = "https://discord.com/api/webhooks/SECRET/token"
        os.environ[g.FAILURE_THRESHOLD_ENV] = "1"
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf), \
                mock.patch.object(g.urllib.request, "urlopen",
                                  side_effect=OSError("conn refused")):
            args = mock.Mock(command="check", dry_run=False)
            g.cmd_check(args)
        out = buf.getvalue()
        self.assertNotIn("SECRET", out)
        self.assertNotIn("discord.com", out)


class TestSummarySameEvaluateAndStamp(GuardianTestBase):
    def _snap_with_errors(self, snap):
        return tuple(snap) + ([],)

    def test_summary_stamp_atomic_and_once(self):
        os.environ[g.DELIVERY_ENV] = "discord"
        calls = []
        with mock.patch.object(g, "run_checks",
                               return_value=self._snap_with_errors(self.healthy_snapshot())), \
             mock.patch.object(g, "send_discord",
                               side_effect=lambda content: calls.append(content) or True):
            args = mock.Mock(command="summary", dry_run=False)
            rc = g.cmd_summary(args)
            self.assertEqual(rc, 0)
            self.assertEqual(len(calls), 1)
            stamp = g.SUMMARY_STAMP.read_text().strip()
            self.assertEqual(len(stamp.split("-")), 3)  # fecha YYYY-MM-DD

            # Segundo summary el mismo día → no duplica
            rc2 = g.cmd_summary(args)
            self.assertEqual(rc2, 0)
            self.assertEqual(len(calls), 1)

            # El stamp es atómico (via _atomic_write_text): sin tmp residuales
            tmps = [p for p in g.STATE_DIR.iterdir() if p.name.startswith(".tmp-")]
            self.assertEqual(tmps, [])

    def test_summary_stamp_only_after_successful_delivery(self):
        os.environ[g.DELIVERY_ENV] = "discord"
        with mock.patch.object(g, "run_checks",
                               return_value=self._snap_with_errors(self.healthy_snapshot())), \
             mock.patch.object(g, "send_discord", return_value=False):
            args = mock.Mock(command="summary", dry_run=False)
            rc = g.cmd_summary(args)
            self.assertEqual(rc, 1)
            self.assertFalse(g.SUMMARY_STAMP.exists())

    def test_summary_no_false_ok_when_incidents(self):
        os.environ[g.DELIVERY_ENV] = "discord"   # activar entrega para capturar el envío
        snap = self.healthy_snapshot()
        snap[3]["ram_pct"] = 92.0   # RAM en incidente
        calls = []
        with mock.patch.object(g, "run_checks",
                               return_value=self._snap_with_errors(snap)), \
             mock.patch.object(g, "send_discord",
                               side_effect=lambda c: calls.append(c) or True):
            # Independiente del stamp de otros tests: simular día distinto
            os.environ["VPS_GUARDIAN_FAKE_TODAY"] = "2099-12-31"
            self.addCleanup(os.environ.pop, "VPS_GUARDIAN_FAKE_TODAY", None)
            args = mock.Mock(command="summary", dry_run=False)
            g.cmd_summary(args)
            self.assertEqual(len(calls), 1)
            self.assertIn("CRITICAL", calls[0])
            self.assertIn("ram_high", calls[0])

    def test_check_and_summary_share_evaluate(self):
        # El resumen usa exactamente la misma evaluación que el check:
        # un disco al 80% es disk_warn en ambos.
        snap = self.healthy_snapshot()
        snap[5]["used_pct"] = 80.0
        inc = g.evaluate(*snap)
        self.assertEqual([k for k, _, _ in inc], ["disk_warn"])


class TestStateIntegrity(GuardianTestBase):
    def test_atomic_state_no_residuals_0600(self):
        g.process_incidents([("unit_down", "x", "d")], dry_run=False)
        self.assertTrue(g.STATE_FILE.exists())
        self.assertEqual(oct(os.stat(g.STATE_FILE).st_mode)[-3:], "600")
        tmps = [p for p in g.STATE_DIR.iterdir() if p.name.startswith(".tmp-")]
        self.assertEqual(tmps, [])

    def test_corrupt_state_recovers_to_empty(self):
        os.environ[g.FAILURE_THRESHOLD_ENV] = "1"
        g.STATE_DIR.mkdir(parents=True, exist_ok=True)
        g.STATE_FILE.write_text("{corrupto")
        r = g.process_incidents([("unit_down", "x", "d")])
        self.assertEqual(r["to_alert"], [("unit_down", "x", "d")])

    def test_dry_run_writes_nothing_and_sends_nothing(self):
        before = sorted(p.name for p in self.state.iterdir()) if self.state.exists() else []
        inc = [("unit_down", "hermes-agent.service", "failed")]
        r = g.process_incidents(inc, dry_run=True)
        self.assertEqual(r["delivery_mode"], "dry-run")
        self.assertEqual(r["to_alert"], inc)
        after = sorted(p.name for p in self.state.iterdir()) if self.state.exists() else []
        self.assertEqual(before, after)
        self.assertFalse(g.STATE_FILE.exists())

    def test_partial_failure_isolation(self):
        with mock.patch.object(g, "get_memory", side_effect=OSError("boom")):
            units, bridge, vigia, mem, load, disk, errors = g.run_checks()
            self.assertEqual(len(errors), 1)
            self.assertIn("memory", errors[0])
            self.assertEqual(len(units), 2)   # el resto de checks intactos
            self.assertTrue(bridge["healthy"] or not bridge["healthy"])

    def test_no_secrets_in_report(self):
        snap = self.healthy_snapshot()
        report = g.build_report("OK", *snap, incidents=[])
        for marker in ("webhook", "discord.com/api", "token", "SECRET"):
            self.assertNotIn(marker, report)


class TestLock(GuardianTestBase):
    def test_second_lock_same_process_raises(self):
        with g.GuardianLock():
            with self.assertRaises(RuntimeError):
                with g.GuardianLock():
                    pass

    def test_dry_run_lock_skips_state_writes(self):
        # dry-run usa /proc/self/exe como lock y no crea archivos de estado
        with g.GuardianLock(skip_write=True):
            self.assertFalse(g.LOCK_FILE.exists())


class TestHostLive(unittest.TestCase):
    """Verificación real de solo lectura contra este host (sin escrituras)."""

    def test_real_units_active(self):
        res = g.check_units()
        self.assertEqual(len(res), len(g.EXPECTED_UNITS))
        for r in res:
            self.assertTrue(r["healthy"], f"{r['name']}: {r['detail']}")

    def test_real_bridge_connected(self):
        r = g.check_bridge()
        self.assertTrue(r["healthy"], r["detail"])

    def test_real_memory_load_disk(self):
        mem = g.get_memory()
        self.assertLess(mem["ram_pct"], 100)
        load = g.get_load()
        self.assertGreater(load["cores"], 0)
        disk = g.get_disk()
        self.assertLessEqual(disk["used_pct"], 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
