#!/usr/bin/env python3
"""guardar_diario_confirmar.py — confirma el éxito diario de la higiene de la flota.

Se ejecuta como job no_agent a las 00:10 y entrega al hilo «🔁 Higiene diaria · memoria +
reset de sesión (DEV/PROD)». Verifica DOS cosas en las DOS flotas:

  1. Memoria: cada perfil corrió `guardar-diario-memoria` en la ventana nocturna (≥22:45,
     ≤12 h de antigüedad) con `last_status=ok`.
  2. Reset de sesión: en PROD, cuántas sesiones se cerraron con `end_reason='idle'` en las
     últimas 24 h y cuántas siguen abiertas por encima del umbral de 300 k tokens.

DEV se lee del disco local (11 perfiles). PROD se consulta en UNA sola llamada ssh
(`docker exec … python3 -`), que devuelve JSON: sin N llamadas ni N timeouts.

Desde el 11-nov-2026 distingue el MOTIVO de la falta de confirmación: un job pausado (la pausa
de emergencia del 9-nov dejó 19 crons congelados) no es lo mismo que uno que falló, ni que uno
habilitado que nunca corrió. Antes los tres salían como "sin confirmar" y el diagnóstico se
perdía con un `last_status=ok` viejo al lado.

Salida (una sola línea, límite 2000 chars de Discord):
  Éxito  -> "✅ Higiene 11-nov: DEV 11/11 · PROD 14/14 · reset 57 cerradas/24h, 0 sobre 300k"
  Fallo  -> "❌ Higiene 11-nov: DEV bragi (PAUSADO · …); PROD golden-game (FALLÓ · …); reset 3 sobre 300k"
"""
import datetime
import json
import os
import subprocess
import sys

JOB_NAME = "guardar-diario-memoria"
DEV_ROOT = "/opt/hermes-agent-data"

# Perfiles históricos (compatibilidad con el contrato previo de 3 perfiles).
JOBS = {
    "Ragnar": f"{DEV_ROOT}/cron/jobs.json",
    "Roshi": f"{DEV_ROOT}/profiles/roshi/cron/jobs.json",
    "Vigía": f"{DEV_ROOT}/profiles/vigia/cron/jobs.json",
}
EXCLUIR_DEV = {"default", "neural-admin-test", "test-onboarding-01"}

# Los jobs disparan a las 23:00 y este confirmador corre pasada la medianoche: el run válido
# es el de las 22:45+ de la jornada ANTERIOR.
WINDOW_MIN = 22 * 60 + 45
# Un tick atrasado 00:00–01:59 sigue siendo el guardado de la jornada anterior.
WINDOW_TOLERANCIA_MIN = 2 * 60
MAX_AGE_H = 12
UMBRAL_TOKENS = 300_000
LIMITE_DISCORD = 2000

ETIQUETAS = {
    "pausado": "PAUSADO",
    "fallo": "FALLÓ",
    "no_ejecutado": "NO EJECUTADO",
    "sin_job": "JOB AUSENTE",
    "error_lectura": "ERROR DE LECTURA",
    "pendiente": "PENDIENTE",
}
# Estados que NO son fallo: ok, y `pendiente` (job creado hace <24 h sin primera corrida).
NEUTROS = ("ok", "pendiente")
ORDEN_ESTADOS = ("error_lectura", "sin_job", "pausado", "fallo", "no_ejecutado")

# Sonda única a PROD: devuelve los jobs de memoria de cada perfil + evidencia de reset.
PROD_SNIPPET = r"""
import glob, json, sqlite3
salida = {"perfiles": {}, "reset": {"cerradas_24h": 0, "sobre_umbral": 0, "db_leidas": 0}}
rutas = glob.glob('/opt/data/profiles/*/cron/jobs.json') + ['/opt/data/cron/jobs.json']
for f in rutas:
    nombre = 'default' if f == '/opt/data/cron/jobs.json' else f.split('/')[-3]
    try:
        d = json.load(open(f))
        js = d.get('jobs') if isinstance(d, dict) else d
        j = next((x for x in js if x.get('name') == 'guardar-diario-memoria'), None)
        salida['perfiles'][nombre] = j
    except Exception as e:
        salida['perfiles'][nombre] = {'_error': '%s: %s' % (type(e).__name__, e)}
dbs = glob.glob('/opt/data/profiles/*/state.db') + ['/opt/data/state.db']
for db in dbs:
    try:
        c = sqlite3.connect('file:%s?mode=ro' % db, uri=True)
        salida['reset']['cerradas_24h'] += c.execute(
            "select count(*) from sessions where end_reason='idle' and ended_at > strftime('%s','now','-24 hours')"
        ).fetchone()[0]
        salida['reset']['sobre_umbral'] += c.execute(
            "select count(*) from sessions where ended_at is null and session_key is not null"
            " and coalesce(input_tokens,0) >= %d" % UMBRAL
        ).fetchone()[0]
        salida['reset']['db_leidas'] += 1
    except Exception:
        pass
print('@@JSON@@' + json.dumps(salida))
""".replace("UMBRAL", str(UMBRAL_TOKENS))


def _ts(job):
    valor = job.get("last_run_at")
    return valor if valor else "nunca"


def _parsear(ts, now):
    try:
        t = datetime.datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=now.tzinfo)
    return t


def clasificar(job, now, window_min=WINDOW_MIN, max_age_h=MAX_AGE_H):
    """Clasifica el estado del job. Devuelve ``(estado, detalle)``.

    Estados: ``ok`` · ``pausado`` · ``fallo`` · ``no_ejecutado``.
    El orden importa: pausado se evalúa ANTES que el status, porque un job pausado conserva
    el ``last_status=ok`` de su última corrida buena y reportarlo como fallo es justo el
    diagnóstico que se perdía.
    """
    if not isinstance(job, dict):
        return "sin_job", "job no encontrado"
    if job.get("_error"):
        return "error_lectura", job["_error"]

    estado_crono = str(job.get("state") or "").lower()
    motivo = job.get("paused_reason")
    enabled = job.get("enabled")
    if isinstance(enabled, str):
        enabled = enabled.strip().lower() in ("true", "1", "yes", "si", "sí")
    if enabled is not True or estado_crono in ("paused", "disabled"):
        return "pausado", f"motivo={motivo or 'sin motivo declarado'}, último guardado {_ts(job)}"
    nota = f"nota: paused_reason residual={motivo}, " if motivo else ""

    status = job.get("last_status")
    if status is None:
        creado = _parsear(job.get("created_at"), now)
        if creado is not None and (now - creado).total_seconds() < 24 * 3600:
            # Job recién creado: su primera corrida todavía no ha llegado. No es un fallo.
            return "pendiente", f"primera corrida programada {job.get('next_run_at') or 'sin fecha'}"
        registro = "sin status registrado" if job.get("last_run_at") else "nunca ejecutado"
        return "no_ejecutado", f"{nota}{registro}, último guardado {_ts(job)}"
    if status != "ok":
        return "fallo", (
            f"{nota}status={status}, err={job.get('last_error') or 'n/a'}, "
            f"último guardado {_ts(job)}"
        )

    ts = job.get("last_run_at")
    if not ts:
        return "no_ejecutado", f"{nota}último guardado {_ts(job)} (sin fecha registrada)"
    t = _parsear(ts, now)
    if t is None:
        return "no_ejecutado", f"{nota}último guardado {_ts(job)} (sin fecha legible)"
    edad_h = (now - t).total_seconds() / 3600
    if edad_h < 0 or edad_h > max_age_h:
        return "no_ejecutado", f"{nota}último guardado {_ts(job)} fuera de la ventana de {max_age_h}h"
    if t.hour * 60 + t.minute < window_min and t.hour * 60 + t.minute >= WINDOW_TOLERANCIA_MIN:
        return "no_ejecutado", (
            f"{nota}último guardado {_ts(job)} fuera de la ventana nocturna (22:45–01:59)"
        )
    return "ok", ""


def _limpiar(detalle, max_len=160):
    """Colapsa a UNA línea y acota: el stdout del job ES el mensaje entregado."""
    texto = " ".join(str(detalle).split())
    texto = texto.replace(";", ",").replace("(", "[").replace(")", "]")
    return texto if len(texto) <= max_len else texto[: max_len - 1] + "…"


def construir_mensaje(resultados):
    """``{perfil: (estado, detalle)}`` -> línea única (contrato heredado de DEV)."""
    if not resultados:
        return f"❌ {JOB_NAME}: no hay perfiles configurados para verificar."
    fallos = [(n, e, d) for n, (e, d) in resultados.items() if e not in NEUTROS]
    if not fallos:
        if len(resultados) == len(JOBS):
            return f"✅ Guardado con éxito en los {len(resultados)} perfiles."
        return f"✅ Guardado con éxito en {len(resultados)} perfil(es)."
    fallos.sort(key=lambda i: ORDEN_ESTADOS.index(i[1]) if i[1] in ORDEN_ESTADOS else 99)
    cuerpo = "; ".join(
        f"{n} ({ETIQUETAS.get(e, e.upper())} · {_limpiar(d)})" for n, e, d in fallos
    )
    return f"❌ {JOB_NAME} sin confirmar en: {cuerpo}"


def construir_reporte(dev, prod, reset, ahora=None, max_fallos=6):
    """Reporte de las dos flotas en UNA línea (≤2000 chars).

    ``dev``/``prod``: ``{perfil: (estado, detalle)}``. ``reset``: dict de la sonda PROD.
    Si todo está bien resume conteos; si algo falla lista los perfiles con su motivo, con
    prefijo de flota para no confundir un `bragi` de DEV con uno de PROD.
    """
    ahora = ahora or datetime.datetime.now().astimezone()
    fecha = ahora.strftime("%d-%b").lower()
    fallos = [("DEV", n, e, d) for n, (e, d) in dev.items() if e not in NEUTROS]
    fallos += [("PROD", n, e, d) for n, (e, d) in prod.items() if e not in NEUTROS]
    pendientes = sum(1 for _, (e, _) in list(dev.items()) + list(prod.items()) if e == "pendiente")
    reset_txt = ""
    if isinstance(reset, dict):
        cerradas = reset.get("cerradas_24h")
        sobre = reset.get("sobre_umbral")
        if cerradas is not None and sobre is not None:
            reset_txt = f" · reset {cerradas} cerradas/24h, {sobre} sobre {UMBRAL_TOKENS // 1000}k"
        elif reset.get("error"):
            reset_txt = f" · reset sin datos ({_limpiar(reset['error'], 60)})"
    if not fallos:
        extra = f" · {pendientes} pendiente(s) de primera corrida" if pendientes else ""
        return (
            f"✅ Higiene {fecha}: DEV {len(dev)}/{len(dev)} · PROD {len(prod)}/{len(prod)}"
            f"{reset_txt}{extra}"
        )
    fallos.sort(key=lambda i: ORDEN_ESTADOS.index(i[2]) if i[2] in ORDEN_ESTADOS else 99)
    partes = [
        f"{flota} {n} ({ETIQUETAS.get(e, e.upper())} · {_limpiar(d, 90)})"
        for flota, n, e, d in fallos[:max_fallos]
    ]
    resto = len(fallos) - len(partes)
    if resto > 0:
        partes.append(f"+{resto} más")
    mensaje = f"❌ Higiene {fecha}: " + "; ".join(partes) + reset_txt
    # Discord corta el contenido a 2000 chars: mejor truncar con marca que perder el reset.
    if len(mensaje) > LIMITE_DISCORD:
        sufijo = reset_txt if len(reset_txt) < 200 else ""
        mensaje = mensaje[: LIMITE_DISCORD - len(sufijo) - 2] + "…" + sufijo
    return mensaje


def _leer_job(ruta):
    """Devuelve el job ``guardar-diario-memoria`` o ``None`` si no está en el archivo."""
    with open(ruta, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        lista = data
    elif isinstance(data, dict):
        lista = data.get("jobs") or []
    else:
        lista = []
    if not isinstance(lista, list):
        lista = []
    return next(
        (j for j in lista if isinstance(j, dict) and j.get("name") == JOB_NAME),
        None,
    )


def perfiles_dev(root=DEV_ROOT):
    """``{perfil: ruta_jobs}`` de DEV, incluido el perfil admin (jobs en la raíz)."""
    rutas = {"Ragnar": f"{root}/cron/jobs.json"}
    try:
        nombres = sorted(
            d for d in os.listdir(f"{root}/profiles")
            if os.path.isdir(f"{root}/profiles/{d}")
            and os.path.exists(f"{root}/profiles/{d}/config.yaml")
            and d not in EXCLUIR_DEV
        )
    except OSError:
        nombres = []
    for n in nombres:
        rutas[n.capitalize()] = f"{root}/profiles/{n}/cron/jobs.json"
    return rutas


def estado_local(rutas, now):
    """Clasifica cada perfil leyendo su jobs.json del disco."""
    resultados = {}
    for nombre, ruta in rutas.items():
        try:
            job = _leer_job(ruta)
        except Exception as e:
            resultados[nombre] = ("error_lectura", f"{type(e).__name__}: {e}")
            continue
        if job is None:
            resultados[nombre] = ("sin_job", f"job '{JOB_NAME}' no encontrado en {ruta}")
            continue
        resultados[nombre] = clasificar(job, now)
    return resultados


def _runner_ssh(comando, timeout=90, entrada=None):
    """Ejecuta la sonda en PROD enviando el script por stdin. Inyectable para pruebas."""
    proc = subprocess.run(comando, input=entrada, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def estado_prod(now, runner=None, timeout=90):
    """``(perfiles, reset)`` de PROD en UNA llamada ssh; en error, todo a ``error_lectura``."""
    runner = runner or _runner_ssh
    comando = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "prod",
        "docker exec -i hermes-agent python3 -",
    ]
    try:
        rc, salida, err = runner(comando, timeout, PROD_SNIPPET)
    except Exception as e:
        return {}, {"error": f"{type(e).__name__}: {e}"}
    if rc != 0:
        return {}, {"error": f"ssh rc={rc}: {err.strip()[:120]}"}
    crudo = ""
    for linea in salida.splitlines():
        if linea.startswith("@@JSON@@"):
            crudo = linea[len("@@JSON@@"):]
    if not crudo:
        return {}, {"error": "respuesta sin JSON"}
    try:
        data = json.loads(crudo)
    except ValueError as e:
        return {}, {"error": f"JSON inválido: {e}"}
    perfiles = {}
    for nombre, job in (data.get("perfiles") or {}).items():
        if job is None:
            perfiles[nombre] = ("sin_job", f"job '{JOB_NAME}' no encontrado en PROD")
        else:
            perfiles[nombre] = clasificar(job, now)
    reset = data.get("reset") or {}
    return perfiles, reset


def ejecutar(rutas=None, now=None, prod_runner=None, con_prod=True):
    """Devuelve el mensaje final. No imprime ni sale del proceso.

    Con ``rutas`` explícitas se mantiene el contrato heredado (solo DEV, mensaje de 3
    perfiles): así los llamadores y pruebas antiguas no tocan la red.
    """
    now = now or datetime.datetime.now().astimezone()
    legacy = rutas is not None
    dev = estado_local(rutas if legacy else perfiles_dev(), now)
    if legacy:
        return construir_mensaje(dev)
    if not con_prod:
        return construir_reporte(dev, {}, {}, now)
    prod, reset = estado_prod(now, runner=prod_runner)
    return construir_reporte(dev, prod, reset, now)


def ran_ok_hoy(job, now):
    """Compatibilidad con llamadores previos: True solo si clasifica ``ok``."""
    return clasificar(job, now)[0] == "ok"


def main(argv=None):
    """CLI: `--no-prod` (solo DEV) y `--now ISO` (simular la hora del reporte)."""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-prod", action="store_true", help="no consultar PROD por ssh")
    ap.add_argument("--now", default=None, help="hora de referencia ISO (pruebas)")
    a = ap.parse_args(argv)
    ahora = datetime.datetime.fromisoformat(a.now) if a.now else None
    print(ejecutar(now=ahora, con_prod=not a.no_prod))
    return 0


if __name__ == "__main__":
    sys.exit(main())
