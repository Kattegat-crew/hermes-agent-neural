[0m
> build · deepseek-v4-pro
[0m
[0m$ [0mcd /opt/hermes-agent-data/worktrees/buzon-push && git log --oneline -3 && git show --stat fce8201c0c86c83f59a7fd3b71c5032e057ad52c
fce8201c0c feat(buzon): aviso push por webhook manteniendo el deposito como fuente de verdad
d04667851e fix(skills): peguelo detecta el desafio retorico y la prohibicion directa
7d4a697957 docs(skills): dos reglas pagadas en la sesion del 12-nov
commit fce8201c0c86c83f59a7fd3b71c5032e057ad52c
Author: Ragnar <ragnar@neuralcrewlabs.com>
Date:   Fri Nov 13 12:31:38 2026 -0500

    feat(buzon): aviso push por webhook manteniendo el deposito como fuente de verdad
    
    Nuevo modulo ops/buzon/notify.py con firma Generic V2 del adaptador
    (X-Webhook-Timestamp + X-Webhook-Signature-V2) e idempotencia por webhook-id.
    agent_handoff.py deposita el ticket igual que antes y despues emite el aviso;
    si el webhook falla el deposito sigue siendo valido y lo recoge el barrido.
    
    El aviso nunca lanza, no reintenta (el reintento es el barrido) y no usa
    variables de entorno para configuracion no secreta: --no-webhook y
    --webhook-base/--webhook-route son flags, el secreto sale del archivo de
    secretos.
    
    Tests: 13/13 (8 de contrato del notificador contra un HTTP real, 5 de
    integracion sobre el CLI con inbox temporal).

 ops/buzon/PLAN.md                       |  75 ++++++++
 ops/buzon/agent_handoff.py              | 321 ++++++++++++++++++++++++++++++++
 ops/buzon/notify.py                     | 120 ++++++++++++
 ops/buzon/test_agent_handoff_webhook.py | 145 +++++++++++++++
 ops/buzon/test_notify.py                | 167 +++++++++++++++++
 5 files changed, 828 insertions(+)
[0m
[0m→ [0mRead ops/buzon/notify.py
[0m→ [0mRead ops/buzon/agent_handoff.py
[0m→ [0mRead ops/buzon/test_notify.py
[0m→ [0mRead ops/buzon/test_agent_handoff_webhook.py
[0m→ [0mRead ops/buzon/PLAN.md
[0m
[0m$ [0mcd /opt/hermes-agent-data/worktrees/buzon-push && grep -n "_validate_signature\|_validate_svix_signature\|_header_delivery_id\|def _validate\|hmac\|hexdigest\|serves_profile_prefix\|event_type\|_route_allows_profile\|webhook-id\|webhook_timestamp\|Timestamp\|Signature" gateway/platforms/webhook.py
16:import hmac
77:def _header_delivery_id(headers) -> str:
80:        "webhook-id", headers.get("X-Request-ID", uuid.uuid4().hex))))
122:def _hmac_str_equal(provided: str, expected: str) -> bool:
125:    return hmac.compare_digest(provided.encode(), expected.encode())
128:def _hex_hmac(secret: str, data: bytes) -> str:
129:    return hmac.new(secret.encode(), data, hashlib.sha256).hexdigest()
174:def _validate_svix_signature(body: bytes, secret: str, msg_id: str, timestamp: str, signature_header: str) -> bool:
195:    expected = base64.b64encode(hmac.new(key, signed_content, hashlib.sha256).digest()).decode()
199:        if _ and version == "v1" and _hmac_str_equal(signature, expected):
212:    serves_profile_prefix: bool = True
256:    def _validate_route(self, name: str, route: dict) -> None:
518:    def _route_allows_profile(route_config: dict, request_profile: Optional[str]) -> bool:
555:        if secret != _INSECURE_NO_AUTH and not self._validate_signature(request, raw_body, secret):
573:                                   event_type: str, delivery_id: str, profile: Optional[str] = None) -> web.Response:
580:        logger.info("[webhook] direct-deliver event=%s route=%s target=%s msg_len=%d delivery=%s", event_type,
596:    def _handle_cron_trigger(self, prompt: str, route_config: dict, route_name: str, event_type: str,
603:        event_context = (f"This run was triggered by webhook event '{event_type}' on route '{route_name}' "
605:        logger.info("[webhook] cron-trigger event=%s route=%s job=%s delivery=%s", event_type, route_name, job_ref,
625:        return web.json_response({"status": "accepted", "route": route_name, "cron_job": job_ref, "event": event_type,
638:        if not self._route_allows_profile(route_config, profile):
675:        delivery_id = _header_delivery_id(headers)
694:        event_type = (headers.get("X-GitHub-Event", "") or headers.get("X-GitLab-Event", "")
695:                      or payload.get("event_type", "") or payload.get("type", "") or "unknown")
697:        if allowed_events and event_type not in allowed_events:
698:            logger.debug("[webhook] Ignoring event %s for route %s (allowed: %s)", event_type, route_name,
700:            return web.json_response({"status": "ignored", "event": event_type})
701:        if not self._route_processor.route_filters_match(route_config, payload, event_type, request.headers):
702:            logger.info("[webhook] filtered event=%s route=%s", event_type, route_name)
715:                    logger.info("[webhook] script ignored event=%s route=%s", event_type, route_name)
718:            prompt = (render_mcp_event_prompt(self, route_config, payload, event_type, route_name)
719:                      or self._render_prompt(route_config.get("prompt", ""), payload, event_type, route_name))
735:            return self._handle_cron_trigger(prompt, route_config, route_name, event_type, delivery_id, profile)
737:            return await self._handle_deliver_only(prompt, payload, route_config, route_name, event_type, delivery_id,
740:                route_name=route_name, coalesce=coalesce, payload=payload, event_type=event_type, prompt=prompt,
742:            return web.json_response({"status": "coalesced", "route": route_name, "event": event_type,
744:        return await self._dispatch_agent_run(request, route_config, route_name, profile, payload, prompt, event_type,
748:                            event_type: str, delivery_id: str, now: float) -> web.Response:
750:        logger.info("[webhook] %s event=%s route=%s prompt_len=%d delivery=%s", request.method, event_type, route_name,
753:                                              route_name=route_name, profile=profile, event_type=event_type)
758:        return web.json_response({"status": "accepted", "route": route_name, "event": event_type,
762:                         route_name: str, profile, event_type: str, superseded=()) -> asyncio.Task:
769:                                                  route_name=route_name, profile=profile, event_type=event_type)
795:                               route_name: str, profile, event_type: str) -> Optional[str]:
860:    # --- Signature validation ---
862:    def _validate_signature(self, request: web.Request, body: bytes, secret: str) -> bool:
871:        # sends webhook-id/webhook-timestamp on EVERY delivery and webhook-signature only when a signing
876:            svix = [_header(name) for name in ("webhook-id", "webhook-timestamp", "webhook-signature")]
878:            return _validate_svix_signature(body, secret, *svix)
881:                (_header("linear-signature"), lambda: _hex_hmac(secret, body)),
882:                (headers.get("X-Hub-Signature-256", ""), lambda: "sha256=" + _hex_hmac(secret, body)),
885:                return _hmac_str_equal(provided, expected())
887:        # Generic V2: X-Webhook-Signature-V2 = hex HMAC-SHA256 of "<timestamp>.<body>", X-Webhook-Timestamp
891:        v2_sig = headers.get("X-Webhook-Signature-V2", "")
893:            v2_timestamp = headers.get("X-Webhook-Timestamp", "")
895:                logger.warning("[webhook] Route '%s' sent X-Webhook-Signature-V2 with no X-Webhook-Timestamp — "
901:            return _hmac_str_equal(v2_sig, _hex_hmac(secret, v2_timestamp.encode() + b"." + body))
903:        generic_sig = headers.get("X-Webhook-Signature", "")
908:                               "to replay attacks. Add an 'X-Webhook-Timestamp' header and switch to "
909:                               "'X-Webhook-Signature-V2' (HMAC-SHA256 of '<timestamp>.<body>').", route_name)
910:            return _hmac_str_equal(generic_sig, _hex_hmac(secret, body))
916:    def _render_prompt(self, template: str, payload: dict, event_type: str, route_name: str) -> str:
921:            return f"Webhook event '{event_type}' on route '{route_name}':\n\n```json\n{truncated}\n```"
927:            if key == "event_type":
928:                return event_type
[0m
[0m→ [0mRead gateway/platforms/webhook.py[90m [offset=60, limit=160][0m
[0m→ [0mRead gateway/platforms/webhook.py[90m [offset=510, limit=70][0m
[0m→ [0mRead gateway/platforms/webhook.py[90m [offset=860, limit=60][0m
[0m
[0m$ [0mcd /opt/hermes-agent-data/worktrees/buzon-push/ops/buzon && uv run --quiet --with pytest python -m pytest -q 2>&1 | tail -30
...F.........                                                            [100%]
=================================== FAILURES ===================================
_________________________ test_sin_secreto_no_intenta __________________________

tmp_path = PosixPath('/opt/hermes-agent-data/cache/scratch/pytest-of-hermes/pytest-69/test_sin_secreto_no_intenta0')

    def test_sin_secreto_no_intenta(tmp_path):
        with _Server(status=202) as srv:
            out = _run(tmp_path, "--webhook-base", srv.url)
            assert out.returncode == 0, out.stderr
>           assert srv.hits == []
E           AssertionError: assert [{'path': '/p...r-ullr-0001'}] == []
E             
E             Left contains one more item: {'path': '/p/ullr/webhooks/buzon', 'body': {'event_type': 'buzon.nuevo', 'ticket_id': 'tkt-20261113-ragnar-ullr-0001', 'de': 'ragnar', 'para': 'ullr', ...}, 'firma_ok': False, 'webhook_id': 'tkt-20261113-ragnar-ullr-0001'}
E             Use -v to get more diff

test_agent_handoff_webhook.py:136: AssertionError
=========================== short test summary info ============================
FAILED test_agent_handoff_webhook.py::test_sin_secreto_no_intenta - Assertion...
1 failed, 12 passed in 6.32s
[0m
[0m$ [0mls -la /opt/hermes-agent-data/secrets/webhook-buzon.json /opt/data/secrets/webhook-buzon.json 2>&1; echo "---"; for f in /opt/hermes-agent-data/secrets/webhook-buzon.json /opt/data/secrets/webhook-buzon.json; do [ -f "$f" ] && echo "EXISTS: $f" && python3 -c "import json;d=json.load(open('$f'));print('keys:',list(d.keys()))" 2>&1; done
-rw------- 1 hermes hermes 140 Nov 13 12:33 /opt/data/secrets/webhook-buzon.json
-rw------- 1 hermes hermes 140 Nov 13 12:33 /opt/hermes-agent-data/secrets/webhook-buzon.json
---
EXISTS: /opt/hermes-agent-data/secrets/webhook-buzon.json
keys: ['secret', 'created', 'routes']
EXISTS: /opt/data/secrets/webhook-buzon.json
keys: ['secret', 'created', 'routes']
[0m
[0m$ [0mcd /opt/hermes-agent-data/worktrees/buzon-push/ops/buzon && python3 - <<'PY'
import json, tempfile, os
# Probe 1: _leer_secreto on a non-dict secret file -> does it raise?
import importlib.util
spec = importlib.util.spec_from_file_location("aho", "agent_handoff.py")
m = importlib.util.module_from_spec(spec)
# avoid running main; just exec the module source minus the __main__ guard
src = open("agent_handoff.py").read().split('if __name__ == "__main__":')[0]
exec(compile(src, "agent_handoff.py", "exec"), m.__dict__)

# Temporarily monkeypatch SECRET_CANDIDATES to a non-dict file
import pathlib
d = tempfile.mkdtemp()
bad = pathlib.Path(d)/"bad.json"
bad.write_text('["not", "a", "dict"]')
m.SECRET_CANDIDATES = (bad,)
try:
    r = m._leer_secreto(None)
    print("RETURNED:", repr(r))
except Exception as e:
    print("RAISED:", type(e).__name__, e)

# Probe 2: notify with non-serializable payload -> does it raise?
import notify
class Weird:
    pass
try:
    res = notify.notify("ullr", {"event_type":"x", "fecha": Weird()}, base_url="http://127.0.0.1:1", secret="s")
    print("NOTIFY RETURNED:", res)
except Exception as e:
    print("NOTIFY RAISED:", type(e).__name__, e)
PY
RAISED: AttributeError 'list' object has no attribute 'get'
NOTIFY RAISED: TypeError Object of type Weird is not JSON serializable
[0m
[0m$ [0mcd /opt/hermes-agent-data/worktrees/buzon-push/ops/buzon && python3 - <<'PY'
import notify, hmac, hashlib
secret = "sécret-ñ-密钥"
ts = "1731500000"
body = '{"asunto":"tarea con acentos áéíóú y emoji 🔔"}'.encode("utf-8")
a = notify.firmar(secret, ts, body)
# receiver _hex_hmac uses secret.encode() (utf-8 default) and v2_timestamp.encode() (utf-8 default)
b = hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
print("firmar == receiver?", a == b)
print("lowercase?", a == a.lower())
PY
firmar == receiver? True
lowercase? True
[0m
[0m$ [0mcd /opt/hermes-agent-data/worktrees/buzon-push/ops/buzon && uv run --quiet --with pytest python -m pytest -q test_notify.py 2>&1 | tail -5 && echo "=== verify 403 case presence ===" && grep -n "403\|test_firma_invalida" test_notify.py
........                                                                 [100%]
8 passed in 4.10s
=== verify 403 case presence ===
62:                        code = 403
111:def test_firma_invalida_es_rechazada_y_no_reintenta():
116:        assert res.status == 403
[0m
FINDINGS

- [MAJOR] ops/buzon/test_agent_handoff_webhook.py:132 (`test_sin_secreto_no_intenta`) — el test no es hermético: `_leer_secreto()` lee rutas absolutas reales (`/opt/hermes-agent-data/secrets/webhook-buzon.json` y `/opt/data/secrets/webhook-buzon.json`), que en esta máquina **existen** (creados 12:33, claves `secret/created/routes`). Con el archivo presente `_leer_secreto` devuelve un secreto real y el handoff SÍ emite el POST, así que `assert srv.hits == []` falla. La suite está **roja: 1 failed, 12 passed** (6.32s), contradiciendo el mensaje de commit "13/13" y el criterio de la fase "suite completa en verde". Arreglo: inyectar las rutas de candidatos (parámetro/env de test) o aislarlas, y no depender del estado de `/opt/...`.

- [MAJOR] ops/buzon/notify.py:93 — `cuerpo = json.dumps(dict(payload), ...)` está **fuera** del `try` (que empieza en :109). Un payload con un valor no serializable (datetime, set, bytes, `Path`) lanza `TypeError` que se escapa de `notify()`, rompiendo el contrato "Nunca lanza" del docstring (:17) y el diseño. Igual quedan fuera del try `clock()` (:94, si no es callable) y `base_url.rstrip` (:95, si `base_url` no es `str`). Verificado: `notify("ullr", {"event_type":"x","fecha": Weird()}, ...)` → `TypeError: Object of type Weird is not JSON serializable`. Arreglo: meter la serialización (y la construcción de timestamp/url) dentro del bloque protegido que devuelve `NotifyResult(False, None, "error")`.

- [MAJOR] ops/buzon/agent_handoff.py:69 — en `_leer_secreto()` el `datos.get(clave)` está fuera del `try` (que sólo envuelve `read_text`+`json.loads`). Si el archivo de secretos es JSON válido pero no un dict (p.ej. `["not","a","dict"]`), `list.get` lanza `AttributeError` que propaga a `send_handoff` **después** del depósito → salida con código ≠ 0 y traceback, violando el criterio 5 ("NINGUNA ruta de error del aviso haga que el proceso salga != 0"). Verificado: `_leer_secreto` sobre un archivo lista → `AttributeError 'list' object has no attribute 'get'`. Arreglo: `if not isinstance(datos, dict): continue` o envolver todo el cuerpo del bucle.

- [MINOR] ops/buzon/test_notify.py:58 — la verificación de firma es auto-referencial: el servidor de test recalcula la misma fórmula del módulo (`hmac.new(SECRET.encode(), ts.encode()+b"."+body, sha256).hexdigest()`) en vez de validar contra `_validate_signature` real del gateway. Copia el bug: no detectaría una divergencia real (p.ej. codificación distinta del secreto). Confirmé que la fórmula SÍ coincide byte a byte con `_hex_hmac(secret, v2_timestamp.encode()+b"."+body)` (probe con secreto y body UTF-8 → `True`, hexdigest en minúsculas), pero el test no lo demuestra. Falta caso de body con acentos/UTF-8; el caso 403 sí existe (`test_firma_invalida_es_rechazada_y_no_reintenta`, :111) pero vía el mismo servidor auto-referencial.

- [MINOR] ops/buzon/agent_handoff.py:48-51 — `from notify import notify` usa un nombre de módulo de nivel superior genérico y el `except Exception: _notify = None` silencia cualquier error de importación o *shadowing* por un paquete `notify` instalado en `sys.path`, desactivando el aviso en silencio. Funciona sólo porque `sys.path[0]` apunta al directorio del script; frágil fuera de esa disposición.

- [MINOR] ops/buzon/notify.py:63-69 — fallback de idempotencia: dos tickets distintos con cuerpo idéntico y sin `ticket_id`/`id`/`msg_id` colisionan (mismo `sha256[:32]`) y el gateway se traga el segundo dentro de la ventana TTL 3600s. No es alcanzable por `agent_handoff` (siempre pone `ticket_id`), pero es un pie-de-gun para la librería general.

- [MINOR] ops/buzon/notify.py:110 — `timeout=2.0` en `urlopen` es timeout por operación de socket (cubre connect, send y read), pero un servidor que "gotea" la respuesta sin estar nunca 2s inactivo puede exceder el total sin disparar timeout. `timeout` negativo cae en el `except Exception` → `"error"` (no rompe), y `clock` no callable queda fuera del try (ya cubierto en el segundo hallazgo).

VERDICT: REJECT

JUSTIFICATION
El criterio de aceptación de la fase ("suite completa en verde", commit "13/13") es falso: la suite está roja (1 failed / 12 passed) por un test no hermético que lee secretos reales de `/opt/hermes-agent-data`/`/opt/data`, y el contrato central "nunca lanza" se viola en dos rutas alcanzables (`json.dumps` fuera del try en `notify`, y `datos.get` sobre un JSON no-dict en `_leer_secreto`), la segunda con salida no-cero tras el depósito. La firma sí coincide byte a byte con `_validate_signature` (verificado por probe) y no se introducen env vars no secretas; lo demás son nitpicks.

TESTS-EVIDENCE
- `uv run --quiet --with pytest python -m pytest -q` en `ops/buzon` → `1 failed, 12 passed in 6.32s` (fallo: `test_sin_secreto_no_intenta`, `assert srv.hits == []`).
- `uv run --quiet --with pytest python -m pytest -q test_notify.py` → `8 passed in 4.10s`.
- Probe firma: `notify.firmar(secret_no_ascii, ts, body_utf8) == hmac.new(secret.encode(), ts.encode()+b"."+body, sha256).hexdigest()` → `True`, minúsculas `True`.
- Probe `_leer_secreto` con archivo `["not","a","dict"]` → `AttributeError 'list' object has no attribute 'get'`.
- Probe `notify(...)` con payload no serializable → `TypeError: Object of type Weird is not JSON serializable`.
- `ls /opt/hermes-agent-data/secrets/webhook-buzon.json /opt/data/secrets/webhook-buzon.json` → ambos existen (claves `secret/created/routes`).
EXIT:0
