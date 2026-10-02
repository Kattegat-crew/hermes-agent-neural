#!/usr/bin/env python3
"""mcp_fleet_probe.py — Sonda FUNCIONAL de la flota MCP (read-only, $0).

Para qué: `hermes mcp list` sólo lee config y `mcp test` sólo prueba el handshake.
Esto conecta con la MISMA config del config.yaml, lista tools y ejecuta UNA llamada
real de lectura por servidor: detecta credenciales muertas (401/403/expired), proxies
que conectan pero no sirven y servidores que ya no arrancan.

Salida: SILENCIOSA si todo está sano (apto para cron no_agent). Si algo falla imprime
un informe compacto. Exit code siempre 0 salvo error propio del script (2).

Uso:
  python3 mcp_fleet_probe.py               # informe sólo si hay fallos
  python3 mcp_fleet_probe.py --verbose     # tabla completa
  python3 mcp_fleet_probe.py --json        # JSON crudo
  python3 mcp_fleet_probe.py --only ap,twenty
  python3 mcp_fleet_probe.py --no-heal     # no tocar permisos de mcp-tokens
"""
import argparse, asyncio, json, os, re, sys, tempfile, time, traceback
from pathlib import Path

CFG_PATH = os.environ.get("MCP_PROBE_CONFIG", "/opt/hermes-agent-data/config.yaml")
ENV_FILE = os.environ.get("MCP_PROBE_ENV", "/opt/hermes-agent-data/.env")
TOKENS_DIR = Path("/opt/hermes-agent-data/mcp-tokens")
ERRLOG = Path("/opt/hermes-agent-data/logs/errors.log")
STATE = Path("/opt/hermes-agent-data/state/mcp-watchdog-state.json")

# --- sondas: SOLO lectura (nunca dispara gasto ni muta nada) -----------------
# Para los pares _write se usa una tool de lectura del mismo proceso.
PROBES = {
    "engram": [("mem_context", {})],
    "ncl_google": [("gmail_digest", {"max": 5}), ("gmail_list", {"max": 1})],
    "ncl_google_write": [("gmail_list", {"max": 1})],
    "ap": [("ap_list_flows", {"project": "videogen"})],
    "ap_write": [("ap_list_flows", {"project": "videogen"})],
    "twenty": [("list_object_metadata_names", {"workspace": "golden"})],
    "twenty_write": [("get_tool_catalog", {"workspace": "golden"})],
    "cloudflare": [("docs", {}), ("execute", {"code": "return 1"})],
    "cloudflare_write": [("docs", {})],
    "composio": [("COMPOSIO_SEARCH_TOOLS", {"query": "gmail"})],
    "composio_write": [("COMPOSIO_SEARCH_SKILLS", {"query": "email"})],
    "pg_ro": [("execute_sql", {"sql": "select 1 as ok"})],
    "stirling": [("stirling_describe_operation", {"operation": "add-page-numbers"})],
    "stirling_write": [("stirling_describe_operation", {"operation": "add-page-numbers"})],
    "paperless": [("get_statistics", {})],
    "paperless_write": [("list_tags", {})],
    "coolify": [("get_version", {})],
    "coolify_write": [("list_applications", {})],
    "fal": [("search_models", {"query": "video"})],
    "fal_write": [("get_pricing", {"model_id": "fal-ai/flux/dev"})],
    "github": [("get_me", {}), ("search_repositories", {"query": "hermes"})],
    "github_write": [("search_repositories", {"query": "hermes"})],
    "docuseal": [("search_templates", {})],
    "docuseal_write": [("search_templates", {})],
    "formbricks": [("list_workspaces", {})],
    "formbricks_write": [("list_workspaces", {})],
    "outline": [("whoami", {})],
    "opendesign": [("list_projects", {})],
    "canva": [("search-designs", {"query": "golden"})],
}
DEFAULT_PROBES = [("whoami", {}), ("list_projects", {}), ("get_version", {})]

# FASE1: sondas OBLIGATORIAS — el veredicto HEALTHY exige que esta operación
# concreta tenga éxito. Para pg_ro el SELECT 1 es obligatorio (evidencia real
# de que el PostgreSQL responde, no sólo de que el proceso MCP vive).
REQUIRED_PROBES = {
    "pg_ro": ("execute_sql", {"sql": "select 1 as ok"}),
}

AUTH_RE = re.compile(
    r"\b401\b|\b403\b|unauthorized|forbidden|bad credentials|invalid[_ -]?token|"
    r"token (expired|revoked)|expired|authentication|permission denied|"
    r"insufficient|not authorized", re.I)

# FASE1 (fix revisión): evidencia OBLIGATORIA en el cuerpo de la sonda obligatoria.
# R4-segunda-mitad: para pg_ro no basta is_error=False — el cuerpo DEBE evidenciar
# que el SELECT 1 devolvió la fila con valor 1 (o {"ok": 1} top-level).
REQUIRED_EVIDENCE = {
    # por nombre de TOOL (independiente del nombre del server en config):
    # execute_sql debe evidenciar la fila del SELECT 1 con valor 1.
    "execute_sql": "select1",
}

# ============================================================================
# FASE2 — Reintento con conexión NUEVA, límites explícitos y bloqueo anti-solape
#
# Modo SOMBRA: los contadores por servidor NO disparan avisos ni tocan el estado
# runtime vivo (FASE1 STATE intacto). La activación de avisos es FASE3.
#   * Límites explícitos por etapa (initialize / list_tools / call_tool) y un
#     límite GLOBAL por servidor e intento — duraciones acotadas.
#   * Fallo -> reintento UNA vez con conexión NUEVA (cada probe() abre su propio
#     transporte/sesión desde cero). El veredicto final es el del reintento
#     (evidencia más fresca); el primero queda registrado en first_verdict.
#   * Bloqueo anti-solape por proceso (flock exclusivo no bloqueante).
#   * Caída confirmada sólo tras FASE2_CONFIRM_CYCLES ciclos NO-HEALTHY
#     consecutivos: contador por servidor, mínimo compatible con FASE3
#     (antispam caída1/reminder24h/recuperación) SIN activar avisos.
# ============================================================================
STAGE_TIMEOUTS = {
    "initialize": 60,   # handshake MCP
    "list_tools": 90,   # catálogo + sondas (el list_timeout manda aquí)
    "call_tool": 60,    # cada llamada de sonda
}
GLOBAL_TIMEOUT = 150            # límite por servidor y por intento (acotado)
FASE2_CONFIRM_CYCLES = 2        # caída confirmada tras 2 ciclos NO-HEALTHY seguidos
# UNVERIFIED es determinista (config/sonda ausente): reintentar no cambia nada.
FASE2_RETRY_VERDICTS = ("FAILED", "DEGRADED")
LOCK_PATH = os.environ.get(
    "MCP_PROBE_LOCK", "/opt/hermes-agent-data/state/mcp-fleet-watchdog.lock")
# FASE2 NUNCA usa el estado runtime vivo (STATE de FASE1): fichero separado.
FASE2_SHADOW_STATE = os.environ.get(
    "MCP_PROBE_FASE2_STATE",
    "/opt/hermes-agent-data/state/mcp-watchdog-fase2-shadow.json")

# ============================================================================
# FASE3 — Antispam de avisos (PREPARACIÓN LÓGICA, SIN ACTIVACIÓN)
#
# Contrato ORIGINAL autorizado (plan msg 164222, recuperado 2026-09-30;
# fuente: home/monitor_state/contrato_original_recovery/plan_original_recuperado_20260930.md):
#   * «Confirmar una caída solamente cuando falle en dos ciclos programados
#     consecutivos» (FASE2).
#   * «Caída confirmada: un aviso.»
#   * «Fallo persistente: silencio; recordatorio solo cada 24 horas.»
#   * «Cambio de error dentro de la misma incidencia: actualizar evidencia,
#     sin nuevo aviso.»
#   * «Recuperación: un aviso tras dos ciclos saludables consecutivos,
#     únicamente si hubo caída notificada.»
#   * «Reconexiones y "parking" transitorios: registro local, sin mensajes.»
#   * «El estado se guardará de forma atómica. Si no puede persistirse, se
#     tratará como fallo del monitor, no se ignorará.»
#   * ESTA FASE NO ENVÍA NADA: las notificaciones son datos que la función
#     devuelve y se persisten como evidencia; ningún canal, ningún envío.
#     La activación de envíos es una fase posterior explícita.
#   * Estado en FICHERO PROPIO, separado del STATE FASE1 y del sombra FASE2.
#
# Decisión conservadora documentada (silencio del doc original): UNVERIFIED
# es "verificación pendiente", NO fallo confirmado. No alimenta el episodio
# de caída ni cuenta para la confirmación de 2 ciclos; sí rompe rachas
# HEALTHY. El doc no define el caso: se elige la interpretación que nunca
# avisa por UNVERIFIED (nadie recibe un falso aviso). Requiere decisión CEO
# para cambiarla.
# ============================================================================
FASE3_REMINDER_SECS = 24 * 3600   # reminder de caída persistente cada 24 h
FASE3_RECOVER_HEALTHY = 2         # recuperación tras 2 HEALTHY consecutivos
# FASE3 NUNCA usa el estado runtime vivo ni el sombra FASE2: fichero propio.
FASE3_ANTISPAM_STATE = os.environ.get(
    "MCP_PROBE_FASE3_STATE",
    "/opt/hermes-agent-data/state/mcp-watchdog-fase3-antispam.json")

# ============================================================================
# FASE1 — Clasificación VERAZ por servidor: HEALTHY / DEGRADED / FAILED / UNVERIFIED
#
# Reglas inquebrantables (el watchdog nunca embellece):
#   R1  Error de la tool de sonda  -> NUNCA HEALTHY (FAILED o DEGRADED).
#   R2  Sonda ausente (el server no expone la tool de sonda) -> UNVERIFIED,
#       jamás HEALTHY: sin evidencia operativa no hay veredicto sano.
#   R3  Args de sonda validados contra el schema REAL que anuncia el server
#       (inputSchema) antes de llamar; inválido -> UNVERIFIED (config vencida),
#       nunca se "inventa" que la llamada pasó.
#   R4  pg_ro: éxito del SELECT 1 es OBLIGATORIO para HEALTHY.
#   R5  Fallo de conexión/initialize/list_tools -> FAILED (catalogo 0 tools
#       también: conexión viva que no sirve catálogo no es operativa).
#   R6  Autenticación rota (401/403/expired) -> FAILED con detalle AUTH.
# ============================================================================

STATES = ("HEALTHY", "DEGRADED", "FAILED", "UNVERIFIED")


def classify(name, connect_ok, tools_count, probe_status, probe_detail="",
             probe_tool=None, required_probe=None, required_ok=False,
             args_invalid=False):
    """Clasificación pura (sin I/O) — testeable sin red.

    connect_ok     : initialize() y list_tools() éxito
    tools_count    : nº de tools del catálogo (None si no se llegó)
    probe_status   : 'OK' | 'APP_ERROR' | 'AUTH' | 'TIMEOUT' | 'EXC' | None
    required_probe : (tool, args) obligatoria para HEALTHY si aplica al server
    required_ok    : la sonda obligatoria tuvo éxito (si hay una)
    args_invalid   : los args de la sonda no validan contra el inputSchema real
    """
    # R5: sin conexión o catálogo vacío no hay nada que operar.
    if not connect_ok:
        return "FAILED", "conexión/initialize/list_tools falló: " + (probe_detail or "")[:180]
    if not tools_count:
        return "FAILED", "catálogo vacío (0 tools) tras conectar"

    # R3: args que no validan contra el schema real -> sin evidencia válida.
    if args_invalid:
        return "UNVERIFIED", f"args de sonda inválidos contra inputSchema: {probe_detail}"[:220]

    # R2/R3: sin llamada efectiva -> UNVERIFIED (jamás HEALTHY).
    if probe_status is None:
        if isinstance(probe_detail, str) and probe_detail.startswith("ARGS-INVALID"):
            # R3: args que no validan contra el schema real del server.
            return "UNVERIFIED", f"args de sonda inválidos contra inputSchema: {probe_detail}"[:220]
        return "UNVERIFIED", f"sonda ausente (tool {probe_tool!r} no expuesta; {tools_count} tools)"

    # R1/R6: la tool respondió ERROR.
    if probe_status in ("AUTH", "TIMEOUT", "EXC"):
        return "FAILED", f"sonda {probe_tool} falló ({probe_status}): {probe_detail}"[:200]
    if probe_status == "APP_ERROR":
        if AUTH_RE.search(probe_detail or ""):
            return "FAILED", f"sonda {probe_tool} devolvió error de auth: {probe_detail}"[:200]
        # Error de aplicación/argumentos: el server vive y responde, pero la
        # operación de lectura no tuvo éxito -> DEGRADED (nunca HEALTHY: R1).
        return "DEGRADED", f"sonda {probe_tool} devolvió error de tool: {probe_detail}"[:200]

    # probe_status == 'OK': la tool de sonda tuvo éxito…
    if required_probe is not None and not required_ok:
        # R4: sonda obligatoria sin éxito (p.ej. pg_ro SELECT 1) -> UNVERIFIED.
        return ("UNVERIFIED",
                f"sonda aplicable OK pero sonda obligatoria {required_probe[0]!r} sin éxito")
    return "HEALTHY", ""


def validate_args_against_schema(args, schema):
    """Valida los args de la sonda contra el inputSchema REAL de la tool.

    Devuelve (ok, detalle). Sin schema o con schema vacío se acepta (el server
    no declara restricciones); si hay schema, jsonschema manda.
    """
    if not schema:
        return True, ""
    try:
        import jsonschema
        jsonschema.validate(args, schema)
        return True, ""
    except Exception as ex:
        return False, f"{type(ex).__name__}: {ex}"[:200]


def load_dotenv(p):
    d = {}
    try:
        for line in open(p):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return d


VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def make_expander(dotenv):
    def expand(s):
        if not isinstance(s, str):
            return s
        return VAR.sub(lambda m: (os.environ.get(m.group(1)) or dotenv.get(m.group(1)) or m.group(0)), s)
    return expand


def heal_token_perms():
    """Los tokens OAuth los reescribe a veces un runtime root; si quedan root:root 600
    el gateway (uid 10000) no los puede leer y el MCP queda 'parked'. Auto-sanación."""
    fixed, bad = [], []
    target_uid = 10000
    target_gid = 10000
    try:
        if TOKENS_DIR.exists():
            st_d = TOKENS_DIR.stat()
            if st_d.st_uid != target_uid or st_d.st_gid != target_gid or (st_d.st_mode & 0o777) != 0o700:
                try:
                    os.chown(TOKENS_DIR, target_uid, target_gid)
                    os.chmod(TOKENS_DIR, 0o700)
                except OSError:
                    pass
        for f in TOKENS_DIR.glob("*.json"):
            st = f.stat()
            if st.st_uid != target_uid or st.st_gid != target_gid or (st.st_mode & 0o777) != 0o600:
                try:
                    os.chown(f, target_uid, target_gid)
                    os.chmod(f, 0o600)
                    fixed.append(f.name)
                except OSError:
                    bad.append(f.name)
    except FileNotFoundError:
        pass
    return fixed, bad


def new_park_lines(since=None):
    """Cuenta las líneas 'parking until a reconnect' de hoy (o desde `since`).

    `since` = 'YYYY-MM-DD HH:MM:SS' de la corrida anterior: el cron sólo debe
    alertar de parques NUEVOS, no repetir los del día anterior toda la jornada.
    """
    try:
        # fichero compartido (logs/errors.log): se lee sólo la cola
        with open(ERRLOG, "rb") as fh:
            try:
                fh.seek(-400_000, os.SEEK_END)
            except OSError:
                fh.seek(0)
            data = fh.read().decode("utf-8", "replace")
    except FileNotFoundError:
        return 0, []
    today = time.strftime("%Y-%m-%d")
    lines = [l for l in data.splitlines() if "parking until a reconnect" in l and today in l]
    if since:
        lines = [l for l in lines if l[:19] > since]
    srv = sorted({m.group(1) for l in lines if (m := re.search(r"MCP server '([^']+)'", l))})
    return len(lines), srv


def _http_client(url, headers):
    """Devuelve un context manager del transporte HTTP, tolerante a mcp 1.x y 2.x.

    mcp 1.x: streamablehttp_client(url, headers=..., timeout=...) -> tupla de 3.
    mcp 2.0: streamable_http_client(url, http_client=create_mcp_http_client(headers=...))
             -> tupla de 2 (read, write); `headers`/`timeout` ya no son kwargs.
    """
    import contextlib
    import inspect as _inspect

    try:
        from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
    except ImportError:
        streamable_http_client = None

    if streamable_http_client is not None:
        params = _inspect.signature(streamable_http_client).parameters
        if "http_client" in params or "headers" not in params:
            kw = {}
            if "headers" in _inspect.signature(create_mcp_http_client).parameters:
                kw["headers"] = headers or None
            if "timeout" in _inspect.signature(create_mcp_http_client).parameters:
                kw["timeout"] = 30.0
            hc = create_mcp_http_client(**kw)

            @contextlib.asynccontextmanager
            async def _cm2():
                async with streamable_http_client(url, http_client=hc) as st:
                    yield st

            return _cm2()

    from mcp.client.streamable_http import streamablehttp_client as _legacy

    @contextlib.asynccontextmanager
    async def _cm1():
        async with _legacy(url, headers=headers or None, timeout=30) as st:
            yield st

    return _cm1()


def _needs_oauth(name):
    """Servidores sin header estático que autentican por OAuth (canva): el probe
    directo no puede hacer el flujo OAuth -> se validan con el cliente real."""
    return (TOKENS_DIR / f"{name}.client.json").exists()


def probe_via_cli(name, timeout=150):
    """Handshake con el cliente real de Hermes (misma maquinaria OAuth)."""
    import subprocess
    hermes = os.environ.get("HERMES_BIN", "/opt/hermes-agent/.venv/bin/hermes")
    started = time.time()
    e = {"server": name, "tools": None, "probe": "hermes mcp test", "status": "?", "detail": "", "secs": 0}
    try:
        r = subprocess.run(["/usr/bin/script", "-qec", f"{hermes} mcp test {name}", "/dev/null"],
                           capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "") + (r.stderr or "")
    except Exception as ex:
        e.update(status="FAIL", detail=f"{type(ex).__name__}: {ex}"[:200])
        e["secs"] = round(time.time() - started, 1)
        return e
    out = out.replace("\r", "")
    m = re.search(r"Tools discovered:\s*(\d+)", out)
    if m and "Connected" in out:
        e.update(status="OK", tools=int(m.group(1)), detail="handshake OAuth OK")
    else:
        bad = [l for l in out.splitlines() if re.search(r"error|failed|OAuth|401|403", l, re.I)]
        e.update(status="CONN-FAIL", detail=" | ".join(bad[:3])[:200])
    e["secs"] = round(time.time() - started, 1)
    return e


def _oauth_handshake_verdict(r):
    """F4: veredicto veraz para servers OAuth validados por handshake CLI.

    El handshake sólo prueba conexión+catálogo, NO una operación real.
    Sin sonda operativa el veredicto veraz es UNVERIFIED (jamás HEALTHY);
    el fallo de handshake sí es FAILED. Función pura, testeable sin red.
    """
    if r.get("status") != "OK":
        return "FAILED", "handshake falló"
    return ("UNVERIFIED",
            "handshake OAuth OK sin sonda operativa (vía CLI): "
            "sin evidencia de operación real -> UNVERIFIED")


def apply_verdict(e, verdict, reason):
    """Fija el veredicto FASE1 en el dict de resultado y su status legacy."""
    e["verdict"] = verdict
    e["reason"] = reason
    e["status"] = {"HEALTHY": "OK", "DEGRADED": "DEGRADED",
                   "FAILED": "FAIL", "UNVERIFIED": "UNVERIFIED"}[verdict]


def _parse_textual_json(txt):
    """Parsea el texto concatenado de content como JSON (si aplica).

    Devuelve (obj, es_json). Tolerante: muchos servers embeben el JSON en un
    bloque de texto con preámbulo; se intenta el primer '{'/'[' en adelante.
    """
    if not txt or not isinstance(txt, str):
        return None, False
    s = txt.strip()
    try:
        return json.loads(s), True
    except Exception:
        pass
    # Recorte conservador: sólo si el texto parece JSON embebido.
    for opener in ("{", "["):
        i = s.find(opener)
        if i > 0:
            try:
                return json.loads(s[i:]), True
            except Exception:
                continue
    return None, False


def _walk_ok_false(obj, depth=0):
    """Busca recursivamente envelopes semánticos de error en la estructura.

    Conservador: sólo señales EXPLÍCITAS de envelope —
      * {'ok': False} o {'success': False} (booleanos explícitos, no 0/null),
      * 'status' en ('error', 'failed', 'failure'),
      * key 'error' NO vacía (señal INDEPENDIENTE, aunque el envelope no declare
        ok:false — p.ej. credenciales muertas con {"error": {"code": 401}}).
    Así datos legítimos del cliente (p.ej. {'ok': 0, 'count': 0},
    {'error': null, 'ok': true} o {'errors': []}) no se confunden con un fallo.
    """
    if depth > 6 or not isinstance(obj, (dict, list)):
        return None
    if isinstance(obj, dict):
        # El 'error' es señal INDEPENDIENTE: si existe y no está vacío, el
        # envelope declara fallo — incluso sin ok:false (credenciales muertas
        # con envelope de error puro: {"error": "boom"} o {"error": {"code":401}}).
        # 'error' null/vacío NO cuenta (legítimo: {"error": null, "ok": true}).
        err = obj.get("error")
        if err is not None and err is not False and err != "" and err != [] and err != {}:
            return f'"error": {json.dumps(err)[:80]}'
        status = obj.get("status")
        if ("ok" in obj and obj["ok"] is False) or ("success" in obj and obj["success"] is False) or (
                isinstance(status, str) and status.lower() in ("error", "failed", "failure")):
            return 'envelope de fallo (ok/success=false o status error)'
        for v in obj.values():
            hit = _walk_ok_false(v, depth + 1)
            if hit:
                return hit
    else:
        for v in obj:
            hit = _walk_ok_false(v, depth + 1)
            if hit:
                return hit
    return None


def _analyze_body_text(txt):
    """F1: analiza el CUERPO textual de una tool 'exitosa' según el protocolo.

    Devuelve None si no hay evidencia de error semántico, o (kind, señal) con
    kind in ('auth', 'app'). Sólo se marca error cuando hay evidencia SEMÁNTICA
    explícita (JSON con ok/success=false o key 'error'), nunca por regex amplia
    sobre datos legítimos del cliente.
    """
    obj, es_json = _parse_textual_json(txt)
    if es_json:
        hit = _walk_ok_false(obj)
        if hit:
            hit_l = hit.lower()
            if AUTH_RE.search(hit_l) or AUTH_RE.search(txt[:200]):
                return "auth", hit
            return "app", hit
        return None
    # No-JSON: sólo señal explícita de envelope de error textual, jamás regex
    # amplia (un 'error' suelto en datos del cliente no es evidencia).
    stripped = txt.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return None
    return None


def _structured_error(res):
    """F3: extrae evidencia de error del structuredContent (si existe).

    Prioridad sobre content textual: si el envelope estructurado declara
    error, manda. Devuelve None o ('auth'|'app', señal).
    """
    sc = getattr(res, "structuredContent", None)
    if sc is None:
        sc = getattr(res, "structured_content", None)  # alias snake mcp 2.x
    if not isinstance(sc, dict):
        return None
    hit = _walk_ok_false(sc)
    if not hit:
        return None
    hit_l = hit.lower()
    if AUTH_RE.search(hit_l) or AUTH_RE.search(json.dumps(sc)[:200]):
        return "auth", hit
    return "app", hit


def _evidence_select1(txt):
    """F2: evidencia de que el SELECT 1 realmente devolvió la fila con 1.

    Acepta (conservador): {"rows": [{"ok": 1, ...}]} (o cualquier fila con el
    valor 1), {"ok": 1} top-level, o lista [[1]]/[[1, ...]]. Rechaza: cuerpo
    vacío, no-JSON, JSON sin filas, o filas cuyo ok/valor sea 0/False/otro.
    Devuelve (evidencia, detalle) — evidencia True sólo con prueba real.
    """
    obj, es_json = _parse_textual_json(txt)
    if not es_json or obj is None:
        return False, "cuerpo vacío o no-JSON: sin evidencia del resultado"

    def _es_uno(v):
        # Entero EXACTO 1: True/False (bool) NO cuentan, ni "1", ni 1.0.
        return type(v) is int and v == 1

    rows = None
    # Top-level: sólo clave 'ok' con entero EXACTO 1. bool True no es evidencia
    # (dice "éxito" pero no prueba que el SELECT devolvió 1) y no se aceptan
    # campos arbitrarios de datos (page/total/count=1) ni contradicciones.
    if isinstance(obj, dict):
        if _es_uno(obj.get("ok")):
            return True, 'evidencia {"ok": 1}'
        if obj.get("ok") is False or obj.get("ok") == 0:
            return False, f'contradicción top-level ok={obj.get("ok")!r}: sin evidencia'
        for key in ("rows", "result", "results", "data"):
            v = obj.get(key)
            if isinstance(v, list):
                rows = v
                break
    elif isinstance(obj, list):
        rows = obj
    if rows is None:
        return False, "JSON sin lista de filas: sin evidencia del resultado"
    if not rows:
        return False, "0 filas: sin evidencia del resultado"
    for row in rows:
        if isinstance(row, dict):
            # Sólo la clave 'ok' con entero EXACTO 1 prueba el SELECT 1.
            # Campos arbitrarios con valor 1 (page/total/ids) NO son evidencia.
            if _es_uno(row.get("ok")):
                return True, f"evidencia fila ok=1: {json.dumps(row)[:80]}"
            if "ok" in row and not _es_uno(row.get("ok")):
                return False, f"contradicción en fila ok={row.get('ok')!r}: sin evidencia"
        elif isinstance(row, list):
            if any(_es_uno(v) for v in row):
                return True, f"evidencia fila [1]: {json.dumps(row)[:80]}"
        elif _es_uno(row):
            return True, "evidencia valor escalar 1"
    return False, f"filas sin ok=1 entero: {json.dumps(rows)[:80]}"


async def call_tool_checked(session, tool, a, tools_by_name):
    """Llama la sonda validando args contra el inputSchema REAL del catálogo.

    Devuelve (probe_status, detalle). probe_status:
    'OK' | 'APP_ERROR' | 'AUTH' | 'TIMEOUT' | 'EXC' | None (sonda ausente/args inválidos).
    F1/F3: además de isError/is_error, se analizan el structuredContent (prioritario)
    y el cuerpo textual como JSON semántico — un server que devuelve
    {"ok": false, "error": ...} con is_error=False NO es éxito.
    """
    tmeta = tools_by_name.get(tool)
    if tmeta is None:
        return None, f"tool {tool!r} no está en el catálogo del server"
    ok, det = validate_args_against_schema(a, tmeta.get("inputSchema"))
    if not ok:
        # R3: no se llama con args que el server declara inválidos.
        return None, f"ARGS-INVALID {tool}: {det}"
    try:
        res = await asyncio.wait_for(session.call_tool(tool, a),
                                     timeout=STAGE_TIMEOUTS["call_tool"])
    except asyncio.TimeoutError:
        return "TIMEOUT", f"call_tool {tool} excedió {STAGE_TIMEOUTS['call_tool']}s"
    except Exception as ex:
        return "EXC", f"{type(ex).__name__}: {ex}"[:200]
    txt = "\n".join([(getattr(c, "text", None) or "") for c in (res.content or [])])[:400]
    # mcp 2.0 renombró `isError` → `is_error`; tolerar ambas.
    _err = getattr(res, "isError", None)
    if _err is None:
        _err = getattr(res, "is_error", False)
    # F3: structuredContent con error tiene PRIORIDAD (superficie distinta,
    # mismo root cause que F1).
    struct_err = _structured_error(res)
    if _err or struct_err:
        kind, señal = struct_err if struct_err else (None, None)
        if kind is None:
            analyzed = _analyze_body_text(txt)
            kind = analyzed[0] if analyzed else (
                "auth" if AUTH_RE.search(txt) else "app")
            señal = analyzed[1] if analyzed else txt[:120]
        if kind == "auth":
            return "AUTH", f"{señal} | {txt[:180]}"[:200]
        return "APP_ERROR", f"{señal} | {txt[:180]}"[:200]
    # F1: protocolo dice success — verificar que el CUERPO no declare error.
    body_err = _analyze_body_text(txt)
    if body_err:
        kind, señal = body_err
        detalle = f"cuerpo con error semántico (is_error=False): {señal} | {txt[:180]}"
        return ("AUTH", detalle[:200]) if kind == "auth" else ("APP_ERROR", detalle[:200])
    return "OK", txt[:200]


async def evaluate_on_session(name, session, e, list_timeout=90):
    """Corre la sonda FASE1 sobre una sesión MCP ya inicializada.

    SIEMPRE cierra con un veredicto explícito en e (nunca deja 'sin veredicto').
    """
    tl = await asyncio.wait_for(session.list_tools(), timeout=list_timeout)
    e["tools"] = len(tl.tools)
    tools_by_name = {t.name: {"inputSchema": t.input_schema} for t in tl.tools}

    probe_list = PROBES.get(name) or DEFAULT_PROBES
    req = REQUIRED_PROBES.get(name)
    # Sondas candidatas; la obligatoria va primero y sin duplicar.
    ordered = ([req] if req else []) + [p for p in probe_list if p != req]
    main_status = main_detail = main_tool = None
    required_ok = False
    for tool, a in ordered:
        if tool not in tools_by_name:
            continue
        e["probe"] = tool
        st, det = await call_tool_checked(session, tool, a, tools_by_name)
        if st is None and det.startswith("ARGS-INVALID"):
            # conservar el detalle para el veredicto UNVERIFIED (R3)
            main_status, main_detail, main_tool = None, det, tool
            break
        if req is not None and (tool, a) == req:
            required_ok = (st == "OK")
            if st is None:
                # sonda obligatoria ausente o args inválidos: sin evidencia válida
                apply_verdict(e, "UNVERIFIED",
                              f"sonda obligatoria {tool!r} sin llamada posible: {det}"[:200])
                return e
            if st != "OK":
                # R4: la sonda obligatoria falló -> nunca HEALTHY.
                v, rr = classify(name, True, e["tools"], st, det, tool,
                                 required_probe=req, required_ok=False)
                apply_verdict(e, v, rr)
                return e
            # F2: el protocolo dijo OK, pero la operación obligatoria exige
            # EVIDENCIA del resultado (p.ej. pg_ro: la fila del SELECT 1 con 1).
            # Cuerpo vacío / no-JSON / ok=0 -> sin evidencia -> NUNCA HEALTHY.
            ev = REQUIRED_EVIDENCE.get(tool)
            if ev == "select1":
                ev_ok, ev_det = _evidence_select1(det)
                required_ok = ev_ok
                if not ev_ok:
                    apply_verdict(e, "DEGRADED",
                                  f"sonda {tool} OK según protocolo pero sin evidencia "
                                  f"del resultado obligatorio: {ev_det}"[:200])
                    return e
            # la obligatoria tuvo éxito: si también está en probe_list es la
            # sonda principal; si no, sigue una sonda de catálogo.
            if main_status is None and (tool, a) in probe_list:
                main_status, main_detail, main_tool = st, det, tool
            continue
        if main_status is None:
            main_status, main_detail, main_tool = st, det, tool
        break
    # Clasificar con la sonda principal (puede ser la obligatoria ya OK).
    v, rr = classify(name, True, e["tools"], main_status, main_detail or "", main_tool,
                     required_probe=req, required_ok=required_ok)
    apply_verdict(e, v, rr)
    return e


async def probe(name, spec, expand, timeout=90):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    url = spec.get("url")
    cmd = spec.get("command")
    args = [expand(a) for a in (spec.get("args") or [])]
    env = dict(os.environ)
    env.update({k: expand(v) for k, v in (spec.get("env") or {}).items()})
    env.setdefault("HOME", "/opt/hermes-agent-data")
    headers = {k: expand(v) for k, v in (spec.get("headers") or {}).items()}
    started = time.time()
    e = {"server": name, "tools": None, "probe": None, "status": "?", "detail": "", "secs": 0,
         "verdict": None, "reason": ""}

    state = {"done": False}
    try:
        if url:
            async with _http_client(url, headers) as _streams:
                r, w = _streams[0], _streams[1]
                async with ClientSession(r, w) as s:
                    await asyncio.wait_for(s.initialize(), timeout=STAGE_TIMEOUTS["initialize"])
                    await evaluate_on_session(name, s, e, list_timeout=STAGE_TIMEOUTS["list_tools"])
                    state["done"] = True
        else:
            async with stdio_client(StdioServerParameters(command=cmd, args=args, env=env)) as (r, w):
                async with ClientSession(r, w) as s:
                    await asyncio.wait_for(s.initialize(), timeout=STAGE_TIMEOUTS["initialize"])
                    await evaluate_on_session(name, s, e, list_timeout=STAGE_TIMEOUTS["list_tools"])
                    state["done"] = True
    except asyncio.TimeoutError as ex:
        if state["done"]:
            e["detail"] = ((e["detail"] + " ") if e["detail"] else "") + f"[teardown: {type(ex).__name__}]"
        else:
            e["detail"] = f"TIMEOUT de etapa en {name}: {ex}"[:600]
            apply_verdict(e, "FAILED", f"timeout de etapa (límite FASE2): {ex}"[:200])
    except Exception as ex:
        if state["done"]:
            # El veredicto ya está tomado: el error viene del desmontaje del
            # transporte (TaskGroup de mcp 2.x), no del servidor.
            e["detail"] = ((e["detail"] + " ") if e["detail"] else "") + f"[teardown: {type(ex).__name__}]"
        else:
            import traceback as _tb
            e["detail"] = (f"{type(ex).__name__}: {ex}"[:200] + " || " + _tb.format_exc()[-300:])[:600]
            apply_verdict(e, "FAILED",
                          f"conexión fallida antes de catálogo: {type(ex).__name__}: {ex}"[:200])
    e["secs"] = round(time.time() - started, 1)
    if e["verdict"] is None:
        # No debería pasar (evaluate_on_session siempre cierra veredicto), pero
        # jamás inventamos un HEALTHY por defecto: sin veredicto -> UNVERIFIED.
        apply_verdict(e, "UNVERIFIED", "sonda terminó sin veredicto explícito")
    return e


# ============================================================================
# FASE2 — Confirmación de caída (2 ciclos) en ESTADO SOMBRA (no runtime)
# ============================================================================

def update_fase2_cycle_counters(results, prev=None, now=None, cycles=FASE2_CONFIRM_CYCLES):
    """FASE2 (modo sombra): contador de ciclos NO-HEALTHY consecutivos por servidor.

    Mínimo compatible con FASE3: por servidor guarda
      {'consec_bad': int, 'last_verdict': str, 'last_ts': iso}
    La caída queda CONFIRMADA sólo cuando consec_bad >= cycles (FASE2_CONFIRM_CYCLES=2).
    NO dispara avisos, NO toca el estado runtime vivo (STATE FASE1) y devuelve el
    dict de estado sombra sin escribirlo a disco (el caller decide, y en tests se
    puede inyectar prev). HEALTHY reinicia el contador (input a la recuperación).
    """
    if prev is None:
        prev = {}
    if now is None:
        now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    st = {"ts": now, "confirm_cycles": cycles, "servers": {}}
    for r in results:
        name = r.get("server")
        verdict = r.get("verdict")
        if not name or verdict not in STATES:
            continue
        s = dict(prev.get("servers", {}).get(name) or {})
        if verdict == "HEALTHY":
            s["consec_bad"] = 0
        else:
            s["consec_bad"] = int(s.get("consec_bad") or 0) + 1
        s["last_verdict"] = verdict
        s["last_ts"] = now
        s["confirmed_down"] = bool(s["consec_bad"] >= cycles)
        st["servers"][name] = s
    return st


def load_fase2_shadow_state(path=None):
    """Lee el estado sombra FASE2 (fichero separado del runtime FASE1)."""
    p = Path(path or FASE2_SHADOW_STATE)
    try:
        return json.loads(p.read_text()) or {}
    except Exception:
        return {}


def write_fase2_shadow_state(st, path=None):
    """Escribe el estado sombra FASE2. Devuelve (ok, detalle).

    Falla DE FORMA DETECTABLE si el fichero/directorio no es escribible por el
    usuario real del proceso (permisos denegados, etc.) — nunca silencia el fallo
    con 'pass' (esa es la detección de estado no escribible de FASE2).
    """
    p = Path(path or FASE2_SHADOW_STATE)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(st, ensure_ascii=False, indent=1))
        return True, ""
    except OSError as ex:
        return False, f"{type(ex).__name__}: {ex}"[:200]


# ============================================================================
# FASE3 — Antispam de avisos (lógica pura; SIN envíos, SIN canales)
# ============================================================================

# Veredictos que SÍ cuentan como fallo hacia la confirmación de caída.
# UNVERIFIED queda EXCLUIDO por decisión conservadora documentada (ver
# cabecera FASE3): es verificación pendiente, no fallo confirmado.
FASE3_FAILURE_VERDICTS = ("FAILED", "DEGRADED")


def fase3_decide_notifications(prev, results, now=None,
                               recover_healthy=FASE3_RECOVER_HEALTHY,
                               reminder_secs=FASE3_REMINDER_SECS):
    """FASE3: decide qué avisos corresponden SIN enviar nada (lógica pura).

    Contrato ORIGINAL autorizado (plan msg 164222, recuperado 2026-09-30):
      * caída confirmada SOLO tras FASE2_CONFIRM_CYCLES ciclos de fallo
        (FAILED/DEGRADED) CONSECUTIVOS — UNVERIFIED no confirma (decisión
        conservadora documentada) — que aún no tuvo aviso en este episodio
        -> aviso 'down_alert' (UNO por episodio).
      * caída confirmada ya avisada con >= reminder_secs desde el último
        aviso (down o reminder) -> aviso 'reminder' (cada 24 h).
      * recuperación: FASE3_RECOVER_HEALTHY ciclos HEALTHY consecutivos tras
        un episodio CON aviso de caída -> UN aviso 'recovered' y cierre.
      * cambio de veredicto no-healthy dentro de la misma incidencia (p.ej.
        FAILED -> DEGRADED): NO re-arma el episodio, NO genera nuevo aviso.
      * UN aviso por servidor y ciclo como máximo (nunca dos tipos a la vez).

    Devuelve (avisos, estado_nuevo):
      avisos: lista de dicts {server, kind, ts, episode_id} — SOLO DATOS;
        separación explícita intención (decidido) vs notificado (nunca en
        esta fase: sin red, sin canal, sin mensaje externo).
      estado_nuevo: dict persistible con ciclo por servidor
        {'consec_healthy', 'episode_id', 'alerted', 'last_alert_ts',
         'last_reminder_ts', 'recovered', 'last_verdict'} + ts global.
    Nunca toca el STATE runtime FASE1 ni el sombra FASE2 (caller decide
    persistencia en el fichero propio FASE3_ANTISPAM_STATE).
    """
    if now is None:
        now = time.time()
    prev_srv = (prev or {}).get("servers", {}) or {}
    st = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z",
                              time.localtime(now)) if isinstance(now, float) else now,
          "recover_healthy": recover_healthy, "reminder_secs": reminder_secs,
          "servers": {}}
    avisos = []
    # Un único episode_id por ciclo para agrupar avisos coetáneos.
    episode_id = time.strftime("%Y%m%dT%H%M%S", time.localtime(now)) \
        if isinstance(now, float) else None
    for r in results:
        name = r.get("server")
        verdict = r.get("verdict")
        if not name or verdict not in STATES:
            continue
        s = dict(prev_srv.get(name) or {})
        consec_healthy = int(s.get("consec_healthy") or 0)
        alerted = bool(s.get("alerted"))
        last_alert = float(s.get("last_alert_ts") or 0)
        last_reminder = float(s.get("last_reminder_ts") or 0)
        old_episode = s.get("episode_id")
        prev_verdict = s.get("last_verdict")
        consec_bad = int(s.get("consec_bad") or 0)
        recovered_flag = False
        kind = None
        if verdict == "HEALTHY":
            consec_healthy += 1
            # Recuperación: sólo si HUBO aviso de caída en el episodio y se
            # alcanzan FASE3_RECOVER_HEALTHY ciclos HEALTHY consecutivos.
            if alerted and consec_healthy >= recover_healthy:
                kind = "recovered"
                # cierre del episodio: sin alerted, contador a 0
                alerted = False
                consec_healthy = 0
                recovered_flag = True
        elif verdict in FASE3_FAILURE_VERDICTS:
            consec_healthy = 0
            # Confirmación ESTRICTA por veredicto de fallo consecutivo:
            # se cuenta en el propio estado FASE3 (no en el sombra FASE2,
            # que incluye UNVERIFIED). Cambio de error dentro de la misma
            # incidencia (FAILED<->DEGRADED) sigue contando: misma
            # incidencia, sin nuevo aviso distinto del ya previsto.
            consec_bad += 1
            confirmed = consec_bad >= FASE2_CONFIRM_CYCLES
            if confirmed:
                if not alerted:
                    kind = "down_alert"          # UN aviso por episodio
                    alerted = True
                    last_alert = now
                elif (now - max(last_alert, last_reminder)) >= reminder_secs:
                    kind = "reminder"            # cada 24 h mientras persista
                    last_reminder = now
            # UNVERIFIED: verificación pendiente — NO rompe el contador de
            # fallos ya acumulado de fallos reales, NO confirma, NO avisa
            # (sí rompe rachas HEALTHY, tratado arriba).
        else:
            # UNVERIFIED u otro veredicto no-healthy no confirmable.
            consec_healthy = 0
        st["servers"][name] = {
            "consec_healthy": consec_healthy,
            "consec_bad": (0 if verdict == "HEALTHY"
                           else (consec_bad if verdict in FASE3_FAILURE_VERDICTS
                                 else int(s.get("consec_bad") or 0))),
            # [B2] orden de evaluación: si kind ya asignó un episode_id NUEVO
            # (down_alert/reminder de ESTE ciclo), priorizarlo sobre la
            # estabilidad del episodio previo; si no, mantener old_episode
            # mientras el episodio siga abierto (alerted) — nunca None.
            "episode_id": (episode_id if kind in ("down_alert", "reminder")
                           else (old_episode if (alerted and old_episode)
                                 else None)),
            "alerted": alerted,
            "last_alert_ts": last_alert if kind in ("down_alert",) else
                             (last_alert if alerted else 0.0),
            "last_reminder_ts": (last_reminder if alerted else 0.0),
            "recovered": recovered_flag,
            "last_verdict": verdict,
            "prev_verdict": prev_verdict,
        }
        if kind:
            avisos.append({"server": name, "kind": kind,
                           "ts": st["ts"], "episode_id": st["servers"][name]["episode_id"]})
    return avisos, st


def load_fase3_antispam_state(path=None):
    """Lee el estado antispam FASE3 (fichero propio, separado de FASE1/FASE2).

    Estado AUSENTE o CORRUPTO NO se enmascara como vacío sano: devuelve
    ({}, ok=False, detalle) vía load_fase3_antispam_state_reported() para que
    el caller trate el caso como fallo del monitor / estado desconocido.
    El doc original no define el comportamiento ante pérdida de estado:
    ante corrupción el dedup (UN aviso por episodio) NO puede garantizarse.
    """
    p = Path(path or FASE3_ANTISPAM_STATE)
    if not p.exists():
        return {}, False, "ausente"
    try:
        data = json.loads(p.read_text())
        if not isinstance(data, dict):
            raise ValueError("estado no es un objeto JSON")
        return (data or {}), True, ""
    except Exception as ex:
        # CORRUPTO: devolver vacío (comportamiento de episodio nuevo) pero
        # REPORTADO — el caller debe marcar fallo del monitor. Nunca fingir
        # que hay una notificación anterior ni una recuperación previa.
        return {}, False, f"corrupto: {type(ex).__name__}: {ex}"[:200]


def load_fase3_antispam_state_reported(path=None):
    """Compat: devuelve solo el estado (los reportes van por return triple)."""
    st, _ok, _det = load_fase3_antispam_state(path)
    return st


def _atomic_write_json(p, payload):
    """Escritura ATÓMICA JSON: tmp en el MISMO directorio + os.replace.

    Devuelve (ok, detalle). Un corte a mitad de escritura deja el fichero
    anterior intacto (os.replace es atómico en el mismo filesystem).
    """
    try:
        p = Path(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp",
                                        dir=str(p.parent))
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=1)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, str(p))
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        return True, ""
    except OSError as ex:
        return False, f"{type(ex).__name__}: {ex}"[:200]


def write_fase3_antispam_state(st, path=None):
    """Escribe el estado antispam FASE3 de forma ATÓMICA. Devuelve (ok, detalle).

    Contrato ORIGINAL: «El estado se guardará de forma atómica. Si no puede
    persistirse, se tratará como fallo del monitor, no se ignorará.»
    Fallo DETECTABLE (nunca silenciado con 'pass'); el caller debe reportarlo.
    """
    return _atomic_write_json(Path(path or FASE3_ANTISPAM_STATE), st)


def fase3_notify_gate(bad_results, antispam_state, decided_now=None):
    """GATING de aviso legacy FASE1: sólo alerta con caída CONFIRMADA y NO
    ya notificada en este episodio (contrato ORIGINAL: «Caída confirmada:
    un aviso», tras 2 ciclos consecutivos; «Cambio de error... sin nuevo
    aviso»).

    bad_results: resultados FASE1 con status != OK (candidatos a aviso).
    antispam_state: estado FASE3 (dict con 'servers').
    decided_now: avisos down_alert/reminder DECIDIDOS en ESTE ciclo por
      fase3_decide_notifications (intención fresca, nunca del estado
      persistido anterior) [B1]. Un down_alert decidido ahora es avisable
      ESTE ciclo — aunque la marca alerted de la decisión fresca ya esté
      puesta — para que el aviso de caída CONFIRMADA salga por stdout
      exactamente UNA vez (ciclo de confirmación), sin duplicarse en
      ciclos posteriores (ahí manda 'ya-notificado' del estado).

    Devuelve (avisables, suprimidos, motivo_supresion):
      avisables: subconjunto de bad_results cuyo servidor tiene caída
        confirmada (consec_bad >= FASE2_CONFIRM_CYCLES contando SOLO
        FAILED/DEGRADED) y SIN down_alert ya decidido en este episodio,
        MÁS los down_alert decididos en este mismo ciclo [B1].
      suprimidos: lista [(server, motivo)].
      motivo_supresion: string agregado ('confirmacion-pendiente' /
        'ya-notificado' / None si no hubo supresiones).

    FASE3 NO ENVÍA NADA: este gate sólo filtra qué pasaría al bloque de
    salida local stdout del cron (mismo canal que ya usa FASE1). Sin
    canales, sin red, sin mensaje externo.
    """
    srv = (antispam_state or {}).get("servers", {}) or {}
    _now_alerts = {(a.get("server")) for a in (decided_now or [])
                   if a.get("kind") == "down_alert"}
    avisables, suprimidos = [], []
    motivos = set()
    for r in bad_results:
        name = r.get("server")
        s = srv.get(name) or {}
        consec_bad = int(s.get("consec_bad") or 0)
        if consec_bad < FASE2_CONFIRM_CYCLES:
            suprimidos.append((name, "confirmacion-pendiente"))
            motivos.add("confirmacion-pendiente")
        elif s.get("alerted") and name not in _now_alerts:
            suprimidos.append((name, "ya-notificado"))
            motivos.add("ya-notificado")
        else:
            avisables.append(r)
    return avisables, suprimidos, (sorted(motivos)[0] if motivos else None)


def acquire_probe_lock(path=None):
    """Bloqueo anti-solape por proceso (flock exclusivo, no bloqueante).

    Devuelve el file handle si se obtuvo (caller lo retiene/cierra), o None si
    otra instancia del watchdog sigue corriendo. Tests usan path tmp.
    """
    import fcntl
    p = Path(path or LOCK_PATH)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = open(p, "w")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return None
        fh.write(f"{os.getpid()}\n{time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
        fh.flush()
        return fh
    except OSError:
        return None


def _with_global_timeout(coro, name, attempt):
    """FASE2: límite GLOBAL por servidor e intento (acotado; último recurso)."""
    return asyncio.wait_for(coro, timeout=GLOBAL_TIMEOUT)


async def evaluate_with_retry(name, spec, expand, timeout=GLOBAL_TIMEOUT):
    """FASE2: probe con límites explícitos por etapa + reintento en conexión NUEVA.

    * Timeout GLOBAL por intento (GLOBAL_TIMEOUT) y límites por etapa dentro de
      probe()/evaluate_on_session() (STAGE_TIMEOUTS).
    * Si el primer intento termina FAILED o DEGRADED (transitorio posible) se
      reintenta UNA vez con conexión COMPLETAMENTE NUEVA (probe() abre su propio
      transporte/sesión desde cero). UNVERIFIED no se reintenta: es determinista.
    * Veredicto final = el del reintento (evidencia más fresca); el del primer
      intento queda en first_verdict. HEALTHY del intento 1 no se re-evalúa
      (no se degrada un resultado sano por paranoia).
    """
    e1 = await _with_global_timeout(probe(name, spec, expand, timeout=timeout), name, 1)
    if e1.get("verdict") not in FASE2_RETRY_VERDICTS:
        return e1
    e2 = await _with_global_timeout(probe(name, spec, expand, timeout=timeout), name, 2)
    e2["first_verdict"] = e1.get("verdict")
    e2["first_reason"] = e1.get("reason", "")
    e2["retried"] = True
    return e2


def stage_timeout(kind):
    """FASE2: timeout explícito para una etapa ('initialize'|'list_tools'|'call_tool')."""
    return STAGE_TIMEOUTS[kind]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--no-heal", action="store_true")
    a = ap.parse_args()

    import yaml
    cfg = yaml.safe_load(open(CFG_PATH)) or {}
    servers = cfg.get("mcp_servers") or {}
    if not servers:
        print("mcp-fleet-probe: sin mcp_servers en la config — nada que sondear")
        return 0
    expand = make_expander(load_dotenv(ENV_FILE))
    only = set(a.only.split(",")) if a.only else None
    targets = [n for n in sorted(servers) if not only or n in only]

    # FASE2: bloqueo anti-solape — si otra instancia sigue corriendo, no solapar.
    lock_fh = acquire_probe_lock()
    if lock_fh is None:
        print("mcp-fleet-probe: otra instancia en curso (lock %s) — salgo sin solapar"
              % LOCK_PATH)
        return 0

    fixed, badperm = ([], []) if a.no_heal else heal_token_perms()

    results = []
    for n in targets:
        try:
            spec = servers[n] or {}
            if _needs_oauth(n) and not (spec.get("headers") or {}):
                # OAuth sin header estático: validar con el cliente real.
                # El handshake sólo prueba conexión+catálogo, NO operación ->
                # sin evidencia operativa el veredicto veraz es UNVERIFIED.
                r = probe_via_cli(n)
                # F4: handshake CLI = conexión+catálogo, no operación real.
                r["verdict"], r["reason"] = _oauth_handshake_verdict(r)
                results.append(r)
            else:
                # FASE2: límites explícitos por etapa + reintento en conexión NUEVA.
                results.append(await evaluate_with_retry(n, spec, expand))
        except Exception:
            results.append({"server": n, "status": "CRASH", "tools": None,
                            "detail": traceback.format_exc()[-200:], "secs": 0, "probe": None,
                            "verdict": "FAILED", "reason": "excepción del propio watchdog en la sonda"})

    # Contrato ORIGINAL: los candidatos a aviso son fallos reales
    # (FAILED/DEGRADED). UNVERIFIED es verificación pendiente: NO es prueba
    # de caída y NO entra al bloque de aviso (permanece visible en
    # --verbose y en el STATE).
    bad = [r for r in results
           if (r.get("verdict") or r["status"]) in FASE3_FAILURE_VERDICTS]
    prev_ts = None
    try:
        _prev = json.loads(STATE.read_text()).get("ts") or ""
        prev_ts = (_prev[:10] + " " + _prev[11:19]) if len(_prev) >= 19 else None
    except Exception:
        prev_ts = None
    parks_n, parks_srv = new_park_lines(prev_ts)

    if a.json:
        print(json.dumps({"results": results, "parks": {"lines": parks_n, "servers": parks_srv},
                          "perm_fixed": fixed, "perm_failed": badperm}, indent=2, ensure_ascii=False))
        return 0

    if a.verbose:
        for r in results:
            print(f"{r['server']:20s} {r.get('verdict') or r['status']:10s} "
                  f"tools={str(r['tools']):>4} {r['secs']:>5}s  {r['probe'] or ''}"
                  + (f"  [{r.get('reason', '')}]" if r.get('reason') else ""))
        print(f"== {len(results) - len(bad)}/{len(results)} sin fallo · parques hoy: {parks_n} ==")

    out = []
    # Aviso legacy FASE1 SUPRIMIDO: la cabecera y los bullets de fallo ya no
    # se construyen aquí; el único aviso por fallo sale del GATING abajo
    # (confirmación 2 ciclos + dedup por episodio). `bad` sigue usándose para
    # la firma anti-repetición y el resumen --verbose.
    if fixed:
        out.append(f"🔧 Permisos de token auto-sanados (root→hermes): {', '.join(fixed)}")
    if badperm:
        out.append(f"⛔ No pude reparar permisos de: {', '.join(badperm)}")
    sig = ",".join(f"{r['server']}:{r['status']}" for r in bad)
    prev = {}
    try:
        prev = json.loads(STATE.read_text()) or {}
    except Exception:
        prev = {}
    now = time.time()
    # Anti-repetición: el mismo fallo no se avisa más de una vez cada 6 h.
    repeat = bool(bad) and prev.get("bad_sig") == sig and \
        (now - float(prev.get("bad_alert_ts") or 0)) < 6 * 3600
    # Mismo anti-repetición para los parques transitorios: el gateway re-parka
    # los mismos servidores en cada reconnect; si la firma no cambia, callar 6 h.
    park_sig = ",".join(parks_srv)
    park_repeat = bool(parks_n) and prev.get("park_sig") == park_sig and \
        (now - float(prev.get("park_alert_ts") or 0)) < 6 * 3600
    if parks_n and not park_repeat:
        nota = ""
        if parks_srv and not ({*parks_srv} & {r["server"] for r in bad}):
            nota = " — sonda directa OK (reconexión transitoria, sin acción)"
        out.append(f"ℹ️ {parks_n} parques 'parking until a reconnect' hoy en errors.log"
                   + (f" — servidores: {', '.join(parks_srv)}" if parks_srv else "")
                   + nota)
    healthy = not out  # out vacío = nada nuevo que avisar

    # FASE1 STATE: escritura ATOMICA (contrato msg 164222: «El estado se
    # guardará de forma atómica. Si no puede persistirse, se tratará como
    # fallo del monitor, no se ignorará» — antes era write_text + except
    # OSError: pass, es decir, no atómica Y error ignorado [O1]).
    _st_ok, _st_det = _atomic_write_json(STATE, {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "results": results, "parks": parks_n,
        "bad_sig": sig,
        "bad_alert_ts": (now if (bad and not repeat) else float(prev.get("bad_alert_ts") or 0)),
        "park_sig": park_sig,
        "park_alert_ts": (now if (parks_n and not park_repeat) else float(prev.get("park_alert_ts") or 0))})
    if not _st_ok:
        # Fallo de persistencia DETECTABLE: nunca silenciar con 'pass'.
        print("mcp-fleet-probe: FALLO DEL MONITOR — estado FASE1 NO escribible: %s" % _st_det)

    # [B1] Decisión FASE3 RECIEN CALCULADA para ESTE ciclo (secuencia única
    # decisión→gate→persistencia), ANTES del gate: el estado que consume el
    # gate ya refleja la decisión de este ciclo (incluida la marca alerted del
    # ciclo que confirma) — jamás el estado persistido del ciclo ANTERIOR, que
    # desfasaba el gate un ciclo (off-by-one) y suprimía para siempre el aviso
    # de caída confirmada (down_alert jamás salía por stdout). Nota
    # contractual: el gate decide QUÉ es avisable según intención/estado; los
    # avisos FASE3 son DATOS, la ENTREGA real no existe en esta fase (FASE3 no
    # envía; stdout no verifica Discord — eso corresponde a FASE5/6). Fallo de
    # decisión => gate corre con {} y el fallo queda VISIBLE (nunca silencioso).
    _shadow = {"servers": {}}
    try:
        _shadow_prev = load_fase2_shadow_state()
        _shadow = update_fase2_cycle_counters(results, prev=_shadow_prev)
        ok_w, det_w = write_fase2_shadow_state(_shadow)
        if not ok_w:
            # Estado no escribible: fallo DETECTABLE en salida (no silencioso),
            # sin abortar la corrida (los resultados FASE1 ya están impresos).
            print("mcp-fleet-probe: FASE2 estado sombra NO escribible: %s" % det_w)
    except Exception as _ex:
        print("mcp-fleet-probe: FASE2 estado sombra error: %s: %s"
              % (type(_ex).__name__, _ex))
        _shadow = {"servers": {}}  # FASE3 degrada sin consec_bad, nunca truena

    _f3_gate_state = {}
    _f3_avisos = []
    try:
        _f3_prev, _f3_ok, _f3_det = load_fase3_antispam_state()
        if not _f3_ok and _f3_det != "ausente":
            # Estado FASE3 corrupto: tratarlo como FALLO DEL MONITOR (contrato
            # ORIGINAL: no ignorar). Sin fingir dedup: el próximo episodio no
            # puede garantizarse sin duplicado; se reporta la incertidumbre.
            print("mcp-fleet-probe: FALLO DEL MONITOR — estado FASE3 %s: "
                  "dedup de avisos NO garantizado (posible duplicado)" % _f3_det)
        # results extendidos con consec_bad del sombra FASE2 recién calculado
        _f3_srv = _shadow.get("servers", {})
        _f3_results = [dict(r, consec_bad=(_f3_srv.get(r.get("server"), {})
                                           or {}).get("consec_bad"))
                       for r in results]
        _f3_avisos, _f3_state = fase3_decide_notifications(_f3_prev, _f3_results)
        _f3_gate_state = _f3_state
        ok3, det3 = write_fase3_antispam_state(_f3_state)
        if not ok3:
            print("mcp-fleet-probe: FASE3 estado antispam NO escribible: %s" % det3)
    except Exception as _ex3:
        print("mcp-fleet-probe: FASE3 estado antispam error: %s: %s"
              % (type(_ex3).__name__, _ex3))
        _f3_gate_state = {}  # gate degrada a 'confirmacion-pendiente' visible

    # GATING del aviso legacy FASE1 (contrato ORIGINAL msg 164222): el aviso
    # por stdout sale sólo con caída CONFIRMADA (2 ciclos consecutivos de
    # fallo real) y NO ya avisada en este episodio. Nunca antes: el aviso
    # legacy a 1 ciclo violaba el plan y está suprimido aquí. Consume el
    # estado FASE3 recién calculado arriba [B1: sin doble lectura del estado
    # persistido del ciclo anterior].
    avisables, suprimidos, motivo_gate = fase3_notify_gate(
        bad, _f3_gate_state, decided_now=_f3_avisos)
    if suprimidos and a.verbose:
        for _nm, _mt in suprimidos:
            print(f"FASE3 aviso suprimido ({_mt}): {_nm}")
    # [B1] `not repeat` eliminado: el anti-repeat FASE1 a 6 h duplicaba el
    # dedup del gate y suprimía TAMBIÉN el aviso del ciclo de confirmación
    # (el ciclo 1 estampa bad_alert_ts sin haber avisado -> ciclo 2 ve
    # repeat=True y calla para siempre). El dedup real manda en el gate:
    # down_alert UNA vez por episodio (estado FASE3), reminder cada 24 h.
    if avisables:
        gated = [r for r in out if not r.startswith("⚠️ MCPs con fallo")]
        print("🩺 mcp-fleet-probe · " + time.strftime("%Y-%m-%d %H:%M %Z"))
        if gated:
            print("\n".join(gated))
        print(f"⚠️ MCPs con caída CONFIRMADA y sin aviso previo "
              f"({len(avisables)}/{len(results)}):")
        for r in avisables:
            print(f"• {r['server']} — {r.get('verdict') or r['status']} · "
                  f"tools={r['tools']} · {r['probe'] or 'sin sonda'}"
                  f"\n    {r.get('reason', '') + (' — ' if r.get('reason') else '')}{r['detail']}")
    elif suprimidos:
        # Silencio contractual: fallo aún NO confirmado (1er ciclo) o ya
        # notificado (reminder contractual cada 24 h sólo por el bloque
        # FASE3 de abajo). Sin aviso legacy, sin duplicar aviso.
        pass

    # SIN ACTIVACIÓN: los avisos decididos NO se envían; quedan como datos
    # (visibles en --verbose) para la fase de activación posterior. La marca
    # alerted NO prueba entrega real (intención ≠ entrega).
    if _f3_avisos and a.verbose:
        for _av in _f3_avisos:
            print("FASE3 aviso DECIDIDO (NO enviado): %s" % _av)

    if lock_fh is not None:
        try:
            lock_fh.close()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
