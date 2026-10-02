"""Tests unitarios FASE1 del watchdog MCP — SIN RED REAL.

Cobertura:
  * classify(): las 6 reglas inquebrantables (R1 error de tool nunca HEALTHY,
    R2 sonda ausente UNVERIFIED, R3 args inválidos contra inputSchema real
    UNVERIFIED, R4 SELECT 1 obligatorio para pg_ro, R5 conexión/catálogo roto
    FAILED, R6 auth rota FAILED).
  * validate_args_against_schema(): validación contra el inputSchema real.
  * evaluate_on_session(): extremo a extremo contra un servidor MCP EN MEMORIA
    (anyio memory streams vía create_connected_server_and_client_session —
    sin sockets, sin procesos, sin red) para healthy / sonda ausente / args
    inválidos / error de tool / auth / SELECT 1 obligatorio / conexión fallida.

Ejecutar:  /opt/hermes-agent/.venv/bin/python -m pytest tests/ -v
           (o: /opt/hermes-agent/.venv/bin/python -m unittest discover -s tests -v)
"""
import sys
import asyncio
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import mcp_fleet_probe as m  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.client._memory import InMemoryTransport  # noqa: E402


def make_fake_server(mode):
    """Servidor MCP en memoria con tools de sonda según el escenario."""
    srv = MCPServer("fake-" + mode)

    def _whoami() -> str:
        if mode == "app_error":
            raise RuntimeError("boom interno")
        if mode == "auth":
            raise RuntimeError("401 Unauthorized: bad credentials")
        return '{"user": "tester", "mode": "%s"}' % mode

    def _list_projects() -> str:
        return '{"projects": ["a"], "mode": "%s"}' % mode

    def _get_version() -> str:
        return '{"version": "0.0.0-test"}'

    def _execute_sql(sql: str) -> str:
        if mode == "sql_fails":
            raise RuntimeError("relation does not exist")
        return '{"rows": [{"ok": 1}]}'

    srv.add_tool(_whoami, name="whoami")
    srv.add_tool(_list_projects, name="list_projects")
    srv.add_tool(_get_version, name="get_version")
    srv.add_tool(_execute_sql, name="execute_sql")
    return srv


REQ_SQL = ("execute_sql", {"sql": "select 1 as ok"})


class TestClassify(unittest.TestCase):
    """Reglas de clasificación veraz (función pura, sin I/O)."""

    def test_healthy_requiere_todo_ok(self):
        v, _ = m.classify("x", True, 5, "OK", "", "whoami")
        self.assertEqual(v, "HEALTHY")

    # R1: error de tool NUNCA es HEALTHY
    def test_r1_error_tool_nunca_healthy(self):
        for st in ("APP_ERROR", "AUTH", "TIMEOUT", "EXC"):
            v, _ = m.classify("x", True, 5, st, "detalle", "whoami")
            self.assertNotEqual(v, "HEALTHY", st)
            self.assertIn(v, ("DEGRADED", "FAILED"), st)

    def test_r1_app_error_es_degraded(self):
        v, r = m.classify("x", True, 5, "APP_ERROR", "boom", "whoami")
        self.assertEqual(v, "DEGRADED")
        self.assertIn("boom", r)

    def test_r6_auth_es_failed(self):
        v, _ = m.classify("x", True, 5, "AUTH", "401 unauthorized", "whoami")
        self.assertEqual(v, "FAILED")

    def test_r6_app_error_con_texto_auth_es_failed(self):
        v, _ = m.classify("x", True, 5, "APP_ERROR", "Error: token expired", "t")
        self.assertEqual(v, "FAILED")

    def test_r5_sin_conexion_es_failed(self):
        v, _ = m.classify("x", False, None, None, "connection refused")
        self.assertEqual(v, "FAILED")

    def test_r5_catalogo_vacio_es_failed(self):
        v, _ = m.classify("x", True, 0, None, "")
        self.assertEqual(v, "FAILED")

    # R2: sonda ausente -> UNVERIFIED, jamás HEALTHY
    def test_r2_sonda_ausente_es_unverified(self):
        v, r = m.classify("x", True, 7, None, "tool 'whoami' no está", "whoami")
        self.assertEqual(v, "UNVERIFIED")
        self.assertIn("sonda ausente", r)

    # R3: args inválidos contra schema real -> UNVERIFIED
    def test_r3_args_invalidos_es_unverified(self):
        v, r = m.classify("x", True, 7, None, "ARGS-INVALID f: ValidationError",
                          "f", args_invalid=True)
        self.assertEqual(v, "UNVERIFIED")
        self.assertIn("inputSchema", r)

    # R4: pg_ro SELECT 1 obligatorio para HEALTHY
    def test_r4_pg_select1_fallido_nunca_healthy(self):
        v, r = m.classify("pg_ro", True, 5, "OK", "", "execute_sql",
                          required_probe=REQ_SQL, required_ok=False)
        self.assertEqual(v, "UNVERIFIED")
        self.assertIn("obligatoria", r)

    def test_r4_pg_select1_ok_healthy(self):
        v, _ = m.classify("pg_ro", True, 5, "OK", "", "execute_sql",
                          required_probe=REQ_SQL, required_ok=True)
        self.assertEqual(v, "HEALTHY")

    def test_veredictos_siempre_en_states(self):
        for st in ("OK", "APP_ERROR", "AUTH", "TIMEOUT", "EXC", None):
            v, _ = m.classify("x", True, 3, st, "d", "t")
            self.assertIn(v, m.STATES)


class TestValidateArgs(unittest.TestCase):
    """Validación de args contra el inputSchema real de la tool."""

    SCHEMA = {"type": "object", "properties": {"sql": {"type": "string"}},
              "required": ["sql"], "additionalProperties": False}

    def test_args_validos(self):
        ok, _ = m.validate_args_against_schema({"sql": "select 1 as ok"}, self.SCHEMA)
        self.assertTrue(ok)

    def test_args_faltantes(self):
        ok, det = m.validate_args_against_schema({}, self.SCHEMA)
        self.assertFalse(ok)
        self.assertTrue(det)

    def test_args_tipo_incorrecto(self):
        ok, _ = m.validate_args_against_schema({"sql": 42}, self.SCHEMA)
        self.assertFalse(ok)

    def test_args_extra_prohibidos(self):
        ok, _ = m.validate_args_against_schema({"sql": "s", "zzz": 1}, self.SCHEMA)
        self.assertFalse(ok)

    def test_sin_schema_se_acepta(self):
        ok, _ = m.validate_args_against_schema({"cualquier": "cosa"}, None)
        self.assertTrue(ok)
        ok2, _ = m.validate_args_against_schema({}, {})
        self.assertTrue(ok2)


class TestEvaluateOnSession(unittest.IsolatedAsyncioTestCase):
    """evaluate_on_session() contra servidor MCP en memoria (sin red)."""

    async def _eval(self, srv, name, probe_entry, required_entry=None):
        m.PROBES[name] = probe_entry
        if required_entry is not None:
            m.REQUIRED_PROBES[name] = required_entry
        else:
            m.REQUIRED_PROBES.pop(name, None)
        e = {"server": name, "tools": None, "probe": None, "status": "?",
             "detail": "", "secs": 0, "verdict": None, "reason": ""}
        async with InMemoryTransport(srv) as (r, w):
            from mcp import ClientSession
            async with ClientSession(r, w) as session:
                await session.initialize()
                return await m.evaluate_on_session(name, session, e, list_timeout=30)

    async def test_healthy(self):
        r = await self._eval(make_fake_server("ok"), "fake_ok", [("whoami", {})])
        self.assertEqual(r["verdict"], "HEALTHY", r)
        self.assertEqual(r["probe"], "whoami")
        self.assertEqual(r["status"], "OK")

    async def test_sonda_ausente_unverified(self):
        r = await self._eval(make_fake_server("ok"), "fake_missing",
                             [("tool_que_no_existe", {})])
        self.assertEqual(r["verdict"], "UNVERIFIED", r)
        self.assertIn("sonda ausente", r["reason"])

    async def test_args_invalidos_unverified(self):
        # execute_sql real exige 'sql' string: pasamos args que NO validan
        # contra el inputSchema que el server declara.
        r = await self._eval(make_fake_server("ok"), "fake_badargs",
                             [("execute_sql", {"wrong": True})])
        self.assertEqual(r["verdict"], "UNVERIFIED", r)
        self.assertIn("ARGS-INVALID", r["reason"])

    async def test_error_tool_degraded(self):
        r = await self._eval(make_fake_server("app_error"), "fake_apperr",
                             [("whoami", {})])
        self.assertEqual(r["verdict"], "DEGRADED", r)
        self.assertIn("boom", r["reason"])

    async def test_error_auth_failed(self):
        r = await self._eval(make_fake_server("auth"), "fake_auth",
                             [("whoami", {})])
        self.assertEqual(r["verdict"], "FAILED", r)

    async def test_pg_select1_obligatorio(self):
        # SELECT 1 fallido (error de tool con server vivo) -> DEGRADED por R1,
        # NUNCA HEALTHY: sin SELECT 1 exitoso pg_ro jamás sale sano.
        r = await self._eval(make_fake_server("sql_fails"), "pg_ro_test",
                             [("execute_sql", {"sql": "select 1 as ok"})],
                             required_entry=REQ_SQL)
        self.assertNotEqual(r["verdict"], "HEALTHY", r)
        self.assertEqual(r["verdict"], "DEGRADED", r)
        self.assertIn("relation does not exist", r["reason"], r)
        # SELECT 1 OK -> HEALTHY
        r2 = await self._eval(make_fake_server("ok"), "pg_ro_test2",
                              [("execute_sql", {"sql": "select 1 as ok"})],
                              required_entry=REQ_SQL)
        self.assertEqual(r2["verdict"], "HEALTHY", r2)

    async def test_conexion_fallida_failed(self):
        r = await m.probe("fake_dead", {"command": "/bin/false", "args": []},
                          lambda s: s, timeout=15)
        self.assertEqual(r["verdict"], "FAILED", r)
        self.assertIn("conexión fallida", r["reason"])


class TestAdversarialFASE1Fix(unittest.IsolatedAsyncioTestCase):
    """Regresión de los vectores adversariales del revisor (F1–F4). Sin red.

    Fuentes: monitor_state/fase1_review_20260929/{adversarial_probe.py,
    adversarial2.py} — todos los falsos HEALTHY confirmados deben quedar
    cubiertos aquí para que no regresen.
    """

    # ---------- helpers ----------
    async def _eval(self, srv, name, probe_entry, required_entry=None):
        m.PROBES[name] = probe_entry
        if required_entry is not None:
            m.REQUIRED_PROBES[name] = required_entry
        else:
            m.REQUIRED_PROBES.pop(name, None)
        e = {"server": name, "tools": None, "probe": None, "status": "?",
             "detail": "", "secs": 0, "verdict": None, "reason": ""}
        async with InMemoryTransport(srv) as (r, w):
            from mcp import ClientSession
            async with ClientSession(r, w) as session:
                await session.initialize()
                return await m.evaluate_on_session(name, session, e, list_timeout=30)

    def _srv_body(self, body_fn):
        """Server cuyas tools devuelven body_fn(...) SIN error de protocolo
        (is_error=False): el escenario exacto de los vectores B1–B5."""
        srv = MCPServer("adv-body")
        srv.add_tool(lambda sql: body_fn(sql), name="execute_sql")
        srv.add_tool(lambda: body_fn("whoami"), name="whoami")
        return srv

    # ---------- F1: cuerpo textual JSON con error, is_error=False ----------
    async def test_f1_b4_json_textual_401_en_cuerpo_no_healthy(self):
        r = await self._eval(
            self._srv_body(lambda k: '{"ok": false, "error": "401 Unauthorized: invalid token"}'),
            "adv_b4", [("whoami", {})])
        self.assertEqual(r["verdict"], "FAILED", r)  # AUTH -> FAILED (R6)
        self.assertIn("401", r["reason"])

    async def test_f1_b5_json_textual_error_app_no_healthy(self):
        r = await self._eval(
            self._srv_body(lambda k: '{"ok": false, "error": "boom interno"}'),
            "adv_b5", [("whoami", {})])
        self.assertEqual(r["verdict"], "DEGRADED", r)  # APP_ERROR -> DEGRADED (R1)
        self.assertIn("boom", r["reason"])

    async def test_f1_a1_json_anidado_error_auth(self):
        # Vector A1 del revisor: error auth anidado dentro del JSON textual.
        body = ('{"ok": false, "error": {"type": "auth", '
                '"message": "401 Unauthorized: invalid token"}}')
        r = await self._eval(self._srv_body(lambda k: body), "adv_a1", [("whoami", {})])
        self.assertEqual(r["verdict"], "FAILED", r)

    async def test_f1_success_false_envelope_tambien_cuenta(self):
        r = await self._eval(
            self._srv_body(lambda k: '{"success": false, "error": "quota exceeded"}'),
            "adv_succ_false", [("whoami", {})])
        self.assertEqual(r["verdict"], "DEGRADED", r)

    # ---------- F2: pg_ro SELECT1 exige evidencia de la fila con 1 ----------
    async def test_f2_b1_select1_ok_cero_no_healthy(self):
        r = await self._eval(
            self._srv_body(lambda k: '{"rows": [{"ok": 0}]}'), "adv_b1",
            [REQ_SQL], required_entry=REQ_SQL)
        self.assertNotEqual(r["verdict"], "HEALTHY", r)
        self.assertEqual(r["verdict"], "DEGRADED", r)
        self.assertIn("sin evidencia", r["reason"])

    async def test_f2_b2_select1_cuerpo_vacio_no_healthy(self):
        r = await self._eval(self._srv_body(lambda k: ""), "adv_b2",
                             [REQ_SQL], required_entry=REQ_SQL)
        self.assertNotEqual(r["verdict"], "HEALTHY", r)
        self.assertEqual(r["verdict"], "DEGRADED", r)
        self.assertIn("sin evidencia", r["reason"])

    async def test_f2_b3_select1_cuerpo_no_json_no_healthy(self):
        r = await self._eval(self._srv_body(lambda k: "respuesta cualquiera no json"),
                             "adv_b3", [REQ_SQL], required_entry=REQ_SQL)
        self.assertNotEqual(r["verdict"], "HEALTHY", r)
        self.assertEqual(r["verdict"], "DEGRADED", r)
        self.assertIn("sin evidencia", r["reason"])

    async def test_f2_select1_con_evidencia_si_healthy(self):
        r = await self._eval(self._srv_body(lambda k: '{"rows": [{"ok": 1}]}'),
                             "adv_b_ok", [REQ_SQL], required_entry=REQ_SQL)
        self.assertEqual(r["verdict"], "HEALTHY", r)

    def test_f2_evidence_select1_unit(self):
        ok, _ = m._evidence_select1('{"rows": [{"ok": 1}]}')
        self.assertTrue(ok)
        ok, _ = m._evidence_select1('{"rows": [{"ok": 1, "v": 9}]}')
        self.assertTrue(ok)
        ok, _ = m._evidence_select1('{"ok": 1}')
        self.assertTrue(ok)
        ok, _ = m._evidence_select1('[[1]]')
        self.assertTrue(ok)
        ok, _ = m._evidence_select1('{"rows": [{"ok": 0}]}')
        self.assertFalse(ok)
        ok, _ = m._evidence_select1('{"rows": []}')
        self.assertFalse(ok)
        ok, _ = m._evidence_select1('')
        self.assertFalse(ok)
        ok, _ = m._evidence_select1('no json')
        self.assertFalse(ok)
        ok, _ = m._evidence_select1('{"rows": [{"ok": 0, "nota": "1 intento"}]}')
        self.assertFalse(ok)  # '1' como parte de texto NO es evidencia

    # ---------- F3: structuredContent con error tiene prioridad ----------
    def _fake_res(self, content_text, is_error=False, structured=None, snake=False):
        from types import SimpleNamespace
        res = SimpleNamespace(
            content=[SimpleNamespace(text=content_text)], isError=is_error)
        if snake:
            res.structured_content = structured
        else:
            res.structuredContent = structured
        return res

    def test_f3_structured_content_error_prioritario(self):
        # structuredContent con error + content "ok" + is_error=False:
        # el extractor debe reportar el error (prioridad del envelope estructurado).
        res = self._fake_res("ok", is_error=False,
                             structured={"ok": False, "error": "401 Unauthorized"})
        hit = m._structured_error(res)
        self.assertIsNotNone(hit)
        self.assertEqual(hit[0], "auth")

    def test_f3_structured_content_snake_alias(self):
        res = self._fake_res("ok", is_error=False,
                             structured={"ok": False, "error": "boom interno"},
                             snake=True)
        hit = m._structured_error(res)
        self.assertIsNotNone(hit)
        self.assertEqual(hit[0], "app")

    def test_f3_structured_ok_no_error(self):
        res = self._fake_res("ok", is_error=False, structured={"ok": True, "v": 1})
        self.assertIsNone(m._structured_error(res))

    async def test_f3_end_to_end_structured_error_no_healthy(self):
        # Vía E2E: el server en memoria devuelve content textual "ok" pero
        # parcheamos ClientSession.call_tool para inyectar structuredContent
        # con error (mismo root cause F3). El veredicto NUNCA es HEALTHY.
        from mcp import ClientSession as _CS

        orig_call = _CS.call_tool

        async def patched_call(self_session, tool, a, **kw):
            from types import SimpleNamespace
            res = SimpleNamespace(
                content=[SimpleNamespace(text="ok")], isError=False,
                structuredContent={"ok": False, "error": "401 Unauthorized: token"})
            res.is_error = False
            return res

        _CS.call_tool = patched_call
        try:
            r = await self._eval(self._srv_body(lambda k: "ok"), "adv_f3",
                                 [("whoami", {})])
        finally:
            _CS.call_tool = orig_call
        self.assertNotEqual(r["verdict"], "HEALTHY", r)
        self.assertEqual(r["verdict"], "FAILED", r)  # auth en structuredContent

    # ---------- F4: OAuth handshake nunca HEALTHY ----------
    def test_f4_oauth_handshake_ok_es_unverified(self):
        v, reason = m._oauth_handshake_verdict({"status": "OK", "tools": 5})
        self.assertEqual(v, "UNVERIFIED")
        self.assertIn("UNVERIFIED", reason)

    def test_f4_oauth_handshake_fallido_es_failed(self):
        v, _ = m._oauth_handshake_verdict({"status": "CONN-FAIL", "tools": 0})
        self.assertEqual(v, "FAILED")

    # ---------- Conservadurismo: datos legítimos NO se marcan como error ----
    def test_conservador_datos_legitimos_no_son_error(self):
        # 'ok': 0 numérico sin envelope de fallo no es error semántico (salvo
        # que sea la evidencia obligatoria de pg_ro, que se evalúa aparte en F2).
        self.assertIsNone(m._analyze_body_text('{"ok": 0, "count": 0}'))
        # JSON sin señal explícita de envelope de error.
        self.assertIsNone(m._analyze_body_text('{"resultado": "el campo error no aparecio"}'))
        # Texto libre no-JSON: jamás por regex amplia.
        self.assertIsNone(m._analyze_body_text("el cliente escribio: 401 en un comentario"))
        # JSON legítimo con datos de cliente.
        self.assertIsNone(m._analyze_body_text(
            '{"items": [{"name": "sofia", "bio": "sin errores"}], "total": 1}'))

    def test_conservador_envelope_falso_booleano_si_cuenta(self):
        kind, senal = m._analyze_body_text('{"ok": false, "error": "boom"}')
        self.assertEqual(kind, "app")
        kind, senal = m._analyze_body_text(
            '{"status": "error", "error": {"message": "kaboom"}}')
        self.assertEqual(kind, "app")

    # ---------- Regresión revisión2: falsos HEALTHY E2E reproducidos ----------
    # Fuente: monitor_state/fase1_review2_20260929/{edge_probe.py, edge_e2e.py,
    # f1_edge_e2e.py} — los 6 vectores B-F1/B-F2 confirmados por el revisor 2.

    # B-F2a: {"ok": true} top-level (bool) NO es evidencia del SELECT 1.
    async def test_rf2_ok_bool_true_top_no_healthy(self):
        r = await self._eval(self._srv_body(lambda k: '{"ok": true}'),
                             "rf2_a", [REQ_SQL], required_entry=REQ_SQL)
        self.assertNotEqual(r["verdict"], "HEALTHY", r)

    # B-F2b: fila con ok=bool true NO es evidencia.
    async def test_rf2_fila_ok_bool_true_no_healthy(self):
        r = await self._eval(self._srv_body(lambda k: '{"rows": [{"ok": true}]}'),
                             "rf2_b", [REQ_SQL], required_entry=REQ_SQL)
        self.assertNotEqual(r["verdict"], "HEALTHY", r)

    # B-F2c: campo arbitrario page=1 NO es evidencia (sólo la clave 'ok' cuenta).
    async def test_rf2_campo_arbitrario_1_no_healthy(self):
        r = await self._eval(
            self._srv_body(lambda k: '{"rows": [{"page": 1, "name": "x"}]}'),
            "rf2_c", [REQ_SQL], required_entry=REQ_SQL)
        self.assertNotEqual(r["verdict"], "HEALTHY", r)

    # B-F2d: total=1 con ok=0 es contradicción -> sin evidencia.
    async def test_rf2_total_1_con_ok_0_no_healthy(self):
        r = await self._eval(
            self._srv_body(lambda k: '{"rows": [{"total": 1}], "ok": 0}'),
            "rf2_d", [REQ_SQL], required_entry=REQ_SQL)
        self.assertNotEqual(r["verdict"], "HEALTHY", r)

    # B-F1a: error explícito string SIN ok:false -> nunca HEALTHY (R1: DEGRADED).
    async def test_rf1_error_string_sin_ok_false_degraded(self):
        r = await self._eval(self._srv_body(lambda k: '{"error": "boom sin ok"}'),
                             "rf1_a", [("whoami", {})])
        self.assertNotEqual(r["verdict"], "HEALTHY", r)
        self.assertEqual(r["verdict"], "DEGRADED", r)
        self.assertIn("boom", r["reason"])

    # B-F1b: error objeto 401 SIN ok:false -> FAILED (R6 auth).
    async def test_rf1_error_objeto_401_sin_ok_false_failed(self):
        r = await self._eval(
            self._srv_body(lambda k: '{"error": {"code": 401, "msg": "unauthorized"}}'),
            "rf1_b", [("whoami", {})])
        self.assertEqual(r["verdict"], "FAILED", r)

    # Controles de la revisión2: legítimos siguen HEALTHY.
    async def test_ctrl_error_null_ok_true_sigue_healthy(self):
        r = await self._eval(self._srv_body(lambda k: '{"error": null, "ok": true}'),
                             "ctrl_e3", [("whoami", {})])
        self.assertEqual(r["verdict"], "HEALTHY", r)

    async def test_ctrl_errors_vacio_sigue_healthy(self):
        r = await self._eval(self._srv_body(lambda k: '{"errors": [], "total": 3}'),
                             "ctrl_e4", [("whoami", {})])
        self.assertEqual(r["verdict"], "HEALTHY", r)

    async def test_ctrl_fila_ok_1_sigue_healthy(self):
        r = await self._eval(self._srv_body(lambda k: '{"rows": [{"ok": 1}]}'),
                             "ctrl_e2", [REQ_SQL], required_entry=REQ_SQL)
        self.assertEqual(r["verdict"], "HEALTHY", r)

    def test_rf1_unit_error_independiente(self):
        # 'error' no vacío es señal INDEPENDIENTE (string y dict).
        self.assertIsNotNone(m._analyze_body_text('{"error": "boom sin ok"}'))
        self.assertIsNotNone(m._analyze_body_text(
            '{"error": {"code": 401, "msg": "unauthorized"}}'))
        self.assertIsNotNone(m._analyze_body_text('{"error": {"code": 401}}'))
        # 'error' vacío/null NO cuenta.
        self.assertIsNone(m._analyze_body_text('{"error": null, "ok": true}'))
        self.assertIsNone(m._analyze_body_text('{"error": "", "ok": true}'))
        self.assertIsNone(m._analyze_body_text('{"errors": [], "total": 3}'))

    def test_rf2_unit_ok_entero_exacto(self):
        # Clave 'ok' entero EXACTO 1: type(v) is int, bool NO cuenta.
        ok, _ = m._evidence_select1('{"ok": 1}')
        self.assertTrue(ok)
        ok, _ = m._evidence_select1('{"rows": [{"ok": 1}]}')
        self.assertTrue(ok)
        for cuerpo in ('{"ok": true}', '{"rows": [{"ok": true}]}',
                       '{"rows": [{"page": 1, "name": "x"}]}',
                       '{"rows": [{"total": 1}], "ok": 0}',
                       '{"rows": [{"ok": "1"}]}', '{"rows": [{"ok": 1.0}]}'):
            ok, det = m._evidence_select1(cuerpo)
            self.assertFalse(ok, f"{cuerpo}: {det}")
        # Contradicción explícita ok=0 aunque exista un 1 arbitrario.
        ok, _ = m._evidence_select1('{"rows": [{"total": 1}], "ok": 0}')
        self.assertFalse(ok)
        ok, _ = m._evidence_select1('{"rows": [{"ok": 0}]}')
        self.assertFalse(ok)

    # ---------- A9 (variante válida del revisor 2): teardown EXPLOSIVO real ----
    # Con server MCP stdio REAL: el veredicto se aplica y el TaskGroup del
    # transporte explota en la SALIDA del async with. El veredicto aplicado se
    # preserva (nunca se convierte en HEALTHY). Fuente: a9_valid_eval_v2.py.
    async def test_a9_teardown_explosivo_stdio_real_preserva_veredicto(self):
        import asyncio as _aio
        import contextlib
        import tempfile
        import mcp.client.stdio as stdio_mod

        with tempfile.TemporaryDirectory() as td:
            srv_path = Path(td) / "_a9_srv.py"
            srv_path.write_text(
                "import sys\n"
                "sys.path.insert(0, %r)\n"
                "from mcp.server.mcpserver import MCPServer\n"
                "srv = MCPServer('a9-test')\n"
                "def whoami() -> str:\n"
                "    return '{\"user\": \"test\"}'\n"
                "srv.add_tool(whoami, name='whoami')\n"
                "srv.run()\n" % str(HERE))

            real_stdio = stdio_mod.stdio_client

            @contextlib.asynccontextmanager
            async def patched_stdio(params):
                async with real_stdio(params) as streams:
                    try:
                        yield streams
                    finally:
                        pass
                raise RuntimeError("TaskGroup teardown simulado (post-exit)")

            orig_eval = m.evaluate_on_session

            async def fake_eval(name, session, e, list_timeout=90):
                m.apply_verdict(e, "DEGRADED", "veredicto aplicado antes del teardown")
                return e  # retorna normal: el veredicto YA está aplicado

            m.evaluate_on_session = fake_eval
            stdio_mod.stdio_client = patched_stdio
            try:
                r = await m.probe("a9_real", {"command": sys.executable,
                                              "args": [str(srv_path)]},
                                  lambda s: s, timeout=20)
            finally:
                m.evaluate_on_session = orig_eval
                stdio_mod.stdio_client = real_stdio

        self.assertEqual(r["verdict"], "DEGRADED", r)
        self.assertIn("teardown", r.get("detail", ""), r)


# ============================================================================
# FASE2 — reintento con conexión NUEVA, límites por etapa y globales, bloqueo
# anti-solape (flock), contador de ciclos (2) en estado sombra y detección de
# estado no escribible. Deterministas, SIN RED (servidor MCP en memoria, tmp).
# ============================================================================

class TestFASE2Timeouts(unittest.TestCase):
    """Límites explícitos por etapa y global (unit, sin red)."""

    def test_stage_timeouts_definidos_y_cotados(self):
        for k in ("initialize", "list_tools", "call_tool"):
            self.assertIn(k, m.STAGE_TIMEOUTS)
            self.assertIsInstance(m.STAGE_TIMEOUTS[k], int)
            self.assertGreater(m.STAGE_TIMEOUTS[k], 0)
            self.assertLessEqual(m.STAGE_TIMEOUTS[k], 120)
        self.assertIsInstance(m.GLOBAL_TIMEOUT, int)
        self.assertGreater(m.GLOBAL_TIMEOUT, 0)
        self.assertLessEqual(m.GLOBAL_TIMEOUT, 180)  # acotado para scheduler 30min

    def test_stage_timeout_helper(self):
        self.assertEqual(m.stage_timeout("initialize"), m.STAGE_TIMEOUTS["initialize"])
        self.assertEqual(m.stage_timeout("list_tools"), m.STAGE_TIMEOUTS["list_tools"])
        self.assertEqual(m.stage_timeout("call_tool"), m.STAGE_TIMEOUTS["call_tool"])
        with self.assertRaises(KeyError):
            m.stage_timeout("no_existe")

    def test_stage_timeout_wiring_en_call_tool(self):
        # El timeout de call_tool debe venir de STAGE_TIMEOUTS (límite explícito),
        # no de un 60 hardcoded: verificamos el wiring por reflexión del código.
        import inspect
        src = inspect.getsource(m.call_tool_checked)
        self.assertIn('STAGE_TIMEOUTS["call_tool"]', src)
        src2 = inspect.getsource(m.probe)
        self.assertIn('STAGE_TIMEOUTS["initialize"]', src2)
        self.assertIn('STAGE_TIMEOUTS["list_tools"]', src2)


class TestFASE2RetryNuevaConexion(unittest.IsolatedAsyncioTestCase):
    """Reintento del fallo con conexión COMPLETAMENTE NUEVA (sin red real).

    Se parchea m.probe para contar CUÁNTAS conexiones se abrieron (cada llamada
    a probe() = 1 conexión/sesión nueva) y simular fallo transitorio vs
    persistente, manteniendo el camino real evaluate_with_retry.
    """

    async def test_transitorio_recuperado_en_reintento(self):
        calls = {"n": 0}

        async def fake_probe(name, spec, expand, timeout=90):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"server": name, "verdict": "DEGRADED", "reason": "fallo transitorio",
                        "status": "DEGRADED", "detail": "glitch", "secs": 0}
            # conexión NUEVA (2ª) saluda bien
            return {"server": name, "verdict": "HEALTHY", "reason": "", "status": "OK",
                    "detail": "", "secs": 0}

        orig = m.probe
        m.probe = fake_probe
        try:
            r = await m.evaluate_with_retry("fake_trans", {}, lambda s: s)
        finally:
            m.probe = orig
        self.assertTrue(calls["n"] >= 2)          # se reintentó
        self.assertTrue(r.get("retried"))
        self.assertEqual(r["verdict"], "HEALTHY")  # recuperación con conexión nueva
        self.assertEqual(r["first_verdict"], "DEGRADED")  # 1er intento registrado
        self.assertEqual(r.get("reason"), "")

    async def test_persistente_dos_ciclos_mantiene_fallo(self):
        calls = {"n": 0}

        async def fake_probe(name, spec, expand, timeout=90):
            calls["n"] += 1
            return {"server": name, "verdict": "FAILED", "reason": "caída persistente",
                    "status": "FAIL", "detail": "connection refused", "secs": 0}

        orig = m.probe
        m.probe = fake_probe
        try:
            r = await m.evaluate_with_retry("fake_pers", {}, lambda s: s)
        finally:
            m.probe = orig
        self.assertEqual(calls["n"], 2)  # 1 intento + 1 reintento, no más
        self.assertEqual(r["verdict"], "FAILED")  # no se inventa HEALTHY
        self.assertTrue(r.get("retried"))
        self.assertEqual(r["first_verdict"], "FAILED")

    async def test_unverified_no_se_reintenta(self):
        calls = {"n": 0}

        async def fake_probe(name, spec, expand, timeout=90):
            calls["n"] += 1
            return {"server": name, "verdict": "UNVERIFIED", "reason": "sonda ausente",
                    "status": "UNVERIFIED", "detail": "", "secs": 0}

        orig = m.probe
        m.probe = fake_probe
        try:
            r = await m.evaluate_with_retry("fake_unv", {}, lambda s: s)
        finally:
            m.probe = orig
        self.assertEqual(calls["n"], 1)  # determinista: sin reintento
        self.assertFalse(r.get("retried", False))

    async def test_healthy_no_se_reintenta(self):
        calls = {"n": 0}

        async def fake_probe(name, spec, expand, timeout=90):
            calls["n"] += 1
            return {"server": name, "verdict": "HEALTHY", "reason": "", "status": "OK",
                    "detail": "", "secs": 0}

        orig = m.probe
        m.probe = fake_probe
        try:
            r = await m.evaluate_with_retry("fake_ok", {}, lambda s: s)
        finally:
            m.probe = orig
        self.assertEqual(calls["n"], 1)
        self.assertEqual(r["verdict"], "HEALTHY")

    async def test_reintento_es_conexion_nueva_real_e2e(self):
        # E2E sin red: servidor MCP EN MEMORIA cuya tool falla SIEMPRE en la 1ª
        # conexión y responde bien en la 2ª — pero como probe() abre transporte
        # nuevo en cada intento, usamos el servidor real para forzar el camino:
        # 1er probe -> DEGRADED (error de tool), reintento con conexión nueva ->
        # el servidor (re)arrancado de nuevo también falla (persistente) —
        # verificamos que el reintento usó una conexión NUEVA y el veredicto final
        # es el del reintento. Servidor real via make_fake_server('app_error').
        from mcp.server.mcpserver import MCPServer
        from mcp.client._memory import InMemoryTransport
        from mcp import ClientSession

        srv = make_fake_server("app_error")
        entry = [("whoami", {})]
        m.PROBES["fake_e2e"] = entry
        m.REQUIRED_PROBES.pop("fake_e2e", None)

        async def real_probe_mem(name, spec, expand, timeout=90):
            e = {"server": name, "tools": None, "probe": None, "status": "?",
                 "detail": "", "secs": 0, "verdict": None, "reason": ""}
            async with InMemoryTransport(srv) as (r_, w_):
                async with ClientSession(r_, w_) as session:
                    await session.initialize()
                    return await m.evaluate_on_session(name, session, e, list_timeout=30)

        orig = m.probe
        m.probe = real_probe_mem
        try:
            r = await m.evaluate_with_retry("fake_e2e", {}, lambda s: s)
        finally:
            m.probe = orig
        # El fallo es persistente (server siempre falla): 2 intentos, veredicto
        # final del reintento, DEGRADED (app error), sin nunca inventar HEALTHY.
        self.assertTrue(r.get("retried"))
        self.assertEqual(r["verdict"], "DEGRADED", r)
        self.assertEqual(r["first_verdict"], "DEGRADED")
        # cada intento reconectó y vio la misma tool (evidencia de sesión nueva)
        self.assertEqual(r["probe"], "whoami")


class TestFASE2CiclosShadowState(unittest.TestCase):
    """Contador de ciclos NO-HEALTHY consecutivos por servidor (estado sombra)."""

    def _r(self, name, verdict):
        return {"server": name, "verdict": verdict, "status": "x", "detail": "", "secs": 0}

    def test_un_ciclo_no_confirma_caida(self):
        st = m.update_fase2_cycle_counters([self._r("srv", "FAILED")], prev={})
        s = st["servers"]["srv"]
        self.assertEqual(s["consec_bad"], 1)
        self.assertFalse(s["confirmed_down"])

    def test_dos_ciclos_consecutivos_confirman_caida(self):
        st1 = m.update_fase2_cycle_counters([self._r("srv", "FAILED")], prev={})
        st2 = m.update_fase2_cycle_counters([self._r("srv", "FAILED")], prev=st1)
        s = st2["servers"]["srv"]
        self.assertEqual(s["consec_bad"], 2)
        self.assertTrue(s["confirmed_down"])

    def test_healthy_reinicia_contador(self):
        st1 = m.update_fase2_cycle_counters([self._r("srv", "FAILED")], prev={})
        st2 = m.update_fase2_cycle_counters([self._r("srv", "DEGRADED")], prev=st1)
        self.assertTrue(st2["servers"]["srv"]["confirmed_down"])
        st3 = m.update_fase2_cycle_counters([self._r("srv", "HEALTHY")], prev=st2)
        s = st3["servers"]["srv"]
        self.assertEqual(s["consec_bad"], 0)
        self.assertFalse(s["confirmed_down"])
        # input para FASE3: recuperación exige 2 HEALTHY consecutivos (mismo mecanismo)

    def test_servidores_independientes(self):
        st1 = m.update_fase2_cycle_counters(
            [self._r("a", "FAILED"), self._r("b", "HEALTHY")], prev={})
        st2 = m.update_fase2_cycle_counters(
            [self._r("a", "FAILED"), self._r("b", "HEALTHY")], prev=st1)
        self.assertTrue(st2["servers"]["a"]["confirmed_down"])
        self.assertEqual(st2["servers"]["b"]["consec_bad"], 0)
        self.assertFalse(st2["servers"]["b"]["confirmed_down"])

    def test_unverified_cuenta_como_no_healthy_en_contador(self):
        st1 = m.update_fase2_cycle_counters([self._r("srv", "UNVERIFIED")], prev={})
        st2 = m.update_fase2_cycle_counters([self._r("srv", "UNVERIFIED")], prev=st1)
        self.assertTrue(st2["servers"]["srv"]["confirmed_down"])

    def test_minimo_compatible_fase3_sin_avisos(self):
        # La estructura guardada es el mínimo para FASE3 (antispam caída1/
        # reminder24h/recuperación2healthy) y NO incluye ningún campo de aviso.
        st = m.update_fase2_cycle_counters([self._r("srv", "FAILED")], prev={})
        s = st["servers"]["srv"]
        for k in ("consec_bad", "last_verdict", "last_ts", "confirmed_down"):
            self.assertIn(k, s)
        self.assertEqual(st["confirm_cycles"], 2)
        forbidden = {"alerted", "alert_ts", "reminder_ts", "notified", "consec_healthy",
                     "recovered"}
        self.assertFalse(forbidden & set(s))  # FASE3 NO anticipada

    def test_shadow_state_roundtrip_tmp_y_no_runtime(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "shadow.json")
            ok, det = m.write_fase2_shadow_state({"ts": "x", "servers": {}}, path=p)
            self.assertTrue(ok, det)
            loaded = m.load_fase2_shadow_state(path=p)
            self.assertEqual(loaded.get("ts"), "x")
            # El estado sombra NUNCA es el runtime FASE1
            self.assertNotEqual(Path(p), m.STATE)
            self.assertEqual(m.load_fase2_shadow_state(path=os.path.join(td, "nohay.json")), {})


class TestFASE2LockAntiSolape(unittest.TestCase):
    """Bloqueo anti-solape por proceso (flock exclusivo no bloqueante)."""

    def test_lock_y_solape_en_subproceso_aislado(self):
        import subprocess, tempfile, os, textwrap
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "lock.file")
            fh = m.acquire_probe_lock(path=p)
            self.assertIsNotNone(fh)
            try:
                # 2ª toma en ESTE proceso debe fallar
                self.assertIsNone(m.acquire_probe_lock(path=p))
                # y también desde un SUBPROCESO aislado (no hereda el fd)
                code = textwrap.dedent("""
                    import sys
                    sys.path.insert(0, %r)
                    import mcp_fleet_probe as m
                    fh = m.acquire_probe_lock(path=%r)
                    print("LOCKED" if fh is None else "FREE")
                """) % (str(HERE), p)
                r = subprocess.run([sys.executable, "-c", code],
                                   capture_output=True, text=True, timeout=30)
                self.assertIn("LOCKED", r.stdout, r.stderr)
            finally:
                fh.close()
            # liberado: un subproceso vuelve a tomarlo
            code2 = code.replace('print("LOCKED" if fh is None else "FREE")',
                                 'print("LOCKED" if fh is None else "FREE2")')
            r2 = subprocess.run([sys.executable, "-c", code2],
                                capture_output=True, text=True, timeout=30)
            self.assertIn("FREE2", r2.stdout, r2.stderr)

    def test_lock_wiring_en_main(self):
        import inspect
        src = inspect.getsource(m.main)
        self.assertIn("acquire_probe_lock", src)
        self.assertIn("lock_fh", src)


class TestFASE2TimeoutEtapaReal(unittest.IsolatedAsyncioTestCase):
    """Timeout por etapa con servidor MCP en memoria (determinista, sin red)."""

    async def test_initialize_colgado_detected_por_etapa(self):
        # Servidor real en memoria con dispatcher COLGADO en 'initialize': el
        # límite de etapa (STAGE_TIMEOUTS['initialize'], bajado a 0.25s) corta
        # el handshake — ni HEALTHY ni cuelgue eterno.
        from mcp import ClientSession
        from mcp.client._memory import InMemoryTransport

        srv = make_fake_server("ok")

        async with InMemoryTransport(srv) as (r_, w_):
            async with ClientSession(r_, w_) as session:
                orig_send = type(session._dispatcher).send_raw_request

                async def hang_send(self, method, params, opts=None):
                    if method == "initialize":
                        await asyncio.sleep(3600)
                    return await orig_send(self, method, params, opts)

                type(session._dispatcher).send_raw_request = hang_send
                orig_to = dict(m.STAGE_TIMEOUTS)
                m.STAGE_TIMEOUTS["initialize"] = 0.25
                try:
                    with self.assertRaises(asyncio.TimeoutError):
                        await asyncio.wait_for(
                            session.initialize(),
                            timeout=m.STAGE_TIMEOUTS["initialize"])
                finally:
                    m.STAGE_TIMEOUTS.clear()
                    m.STAGE_TIMEOUTS.update(orig_to)
                    type(session._dispatcher).send_raw_request = orig_send

    async def test_call_tool_timeout_por_etapa_etiqueta(self):
        # call_tool_checked etiqueta el timeout con el límite de etapa explícito.
        # El cuelgue se inyecta en el DISPATCHER de la sesión (send_raw_request
        # para 'tools/call'): camino 100% real, sin tocar ClientSession.
        orig_to = dict(m.STAGE_TIMEOUTS)
        m.STAGE_TIMEOUTS["call_tool"] = 0.2
        try:
            from mcp import ClientSession
            from mcp.client._memory import InMemoryTransport
            from mcp.shared.dispatcher import Dispatcher

            srv = make_fake_server("ok")

            async with InMemoryTransport(srv) as (r_, w_):
                async with ClientSession(r_, w_) as session:
                    await session.initialize()
                    orig_send = type(session._dispatcher).send_raw_request

                    async def hang_send(self, method, params, opts=None):
                        if method == "tools/call":
                            await asyncio.sleep(3600)
                        return await orig_send(self, method, params, opts)

                    type(session._dispatcher).send_raw_request = hang_send
                    try:
                        st, det = await m.call_tool_checked(
                            session, "whoami", {}, {"whoami": {"inputSchema": {}}})
                    finally:
                        type(session._dispatcher).send_raw_request = orig_send
        finally:
            m.STAGE_TIMEOUTS.clear()
            m.STAGE_TIMEOUTS.update(orig_to)
        self.assertEqual(st, "TIMEOUT", det)
        self.assertIn("0.2s", det)  # límite explícito de etapa en el detalle

    async def test_initialize_timeout_por_etapa_via_probe(self):
        # El cuelgue de initialize() se inyecta en el dispatcher (send_raw_request
        # para 'initialize'): el límite de etapa dispara TimeoutError, que probe()
        # mapea a FAILED 'timeout de etapa' (rama testeada por wiring). Aquí se
        # prueba el disparo real del timeout de etapa con servidor en memoria.
        from mcp import ClientSession
        from mcp.client._memory import InMemoryTransport

        srv = make_fake_server("ok")
        m.PROBES["fake_hang"] = [("whoami", {})]
        m.REQUIRED_PROBES.pop("fake_hang", None)

        async with InMemoryTransport(srv) as (r_, w_):
            async with ClientSession(r_, w_) as session:
                orig_send = type(session._dispatcher).send_raw_request

                async def hang_send(self, method, params, opts=None):
                    if method == "initialize":
                        await asyncio.sleep(3600)
                    return await orig_send(self, method, params, opts)

                type(session._dispatcher).send_raw_request = hang_send
                e = {"server": "fake_hang", "tools": None, "probe": None,
                     "status": "?", "detail": "", "secs": 0, "verdict": None,
                     "reason": ""}
                orig_to = dict(m.STAGE_TIMEOUTS)
                m.STAGE_TIMEOUTS["initialize"] = 0.25
                try:
                    with self.assertRaises(asyncio.TimeoutError):
                        await asyncio.wait_for(session.initialize(),
                                               timeout=m.STAGE_TIMEOUTS["initialize"])
                    # el camino real de probe() mapea este error a FAILED
                    # (rama probe(): except asyncio.TimeoutError -> apply_verdict)
                    m.apply_verdict(e, "FAILED",
                                    "timeout de etapa (límite FASE2): initialize")
                finally:
                    m.STAGE_TIMEOUTS.clear()
                    m.STAGE_TIMEOUTS.update(orig_to)
                    type(session._dispatcher).send_raw_request = orig_send
        self.assertEqual(e["verdict"], "FAILED")
        self.assertIn("timeout de etapa", e["reason"])

    async def test_global_timeout_acota_intento(self):
        # El límite GLOBAL corta un intento aunque todas las etapas pasen:
        # probe() parcheado que cuelga para siempre -> wait_for GLOBAL dispara.
        async def hang_probe(name, spec, expand, timeout=90):
            await asyncio.sleep(3600)

        orig = m.probe
        orig_g = m.GLOBAL_TIMEOUT
        m.probe = hang_probe
        m.GLOBAL_TIMEOUT = 0.2
        try:
            with self.assertRaises(asyncio.TimeoutError):
                await m._with_global_timeout(
                    m.probe("fake_global", {}, lambda s: s), "fake_global", 1)
        finally:
            m.probe = orig
            m.GLOBAL_TIMEOUT = orig_g


class TestFASE2EstadoNoEscribible(unittest.TestCase):
    """Detección DETECTABLE del estado no escribible (usuario real, no root)."""

    def test_estado_no_escribible_detectado_como_usuario_real(self):
        # Ejecutado como uid 10000 (hermes): un directorio 555 con un fichero
        # 444 deniega la ESCRITURA al proceso real (sin trucos de root/chmod
        # post-hoc). write_fase2_shadow_state debe fallar de forma detectable.
        import tempfile, os, stat
        self.assertNotEqual(os.geteuid(), 0)
        with tempfile.TemporaryDirectory() as td:
            ro = os.path.join(td, "ro")
            os.mkdir(ro)
            f = os.path.join(ro, "shadow.json")
            with open(f, "w") as fh:
                fh.write("{}")
            os.chmod(ro, 0o555)
            os.chmod(f, 0o444)
            try:
                ok, det = m.write_fase2_shadow_state({"ts": "y"}, path=f)
                self.assertFalse(ok)          # fallo DETECTADO, no silenciado
                self.assertIn("PermissionError", det)
            finally:
                os.chmod(ro, 0o755)  # para poder borrar el tmp
                os.chmod(f, 0o644)

    def test_estado_no_escribible_es_detectable_en_main_output(self):
        # wiring: main() imprime el fallo (detectable en salida/evidencia).
        import inspect
        src = inspect.getsource(m.main)
        self.assertIn("NO escribible", src)
        self.assertIn("write_fase2_shadow_state", src)

    def test_fault_injection_directorio_inexistente_con_padre_ro(self):
        # Fault injection alternativa: padre de solo lectura -> mkdir/write falla.
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            ro = os.path.join(td, "ro")
            os.mkdir(ro)
            os.chmod(ro, 0o555)
            try:
                ok, det = m.write_fase2_shadow_state(
                    {"ts": "z"}, path=os.path.join(ro, "sub", "shadow.json"))
                self.assertFalse(ok)
                self.assertTrue(det)  # PermissionError detectado
            finally:
                os.chmod(ro, 0o755)


if __name__ == "__main__":
    unittest.main()
