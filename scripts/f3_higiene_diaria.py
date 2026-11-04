#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
F3 · Vigilancia e higiene diaria del árbol único de skills (23-sep-2026)
========================================================================

Reemplaza a `skills_sync_daily.sh`, que medía la paridad canon ⇄ copia. Desde
F3 esa copia NO EXISTE: la raíz de escritura de los 12 perfiles ES el canon
versionado. Medir una copia ausente no protege nada; lo que hay que vigilar es
otra cosa:

  V1  un solo árbol     mismo inodo en el canon y en las 12 raíces de escritura
  V1b censo vs montaje  todo perfil de disco tiene su raíz montada, y todo
                        destino del compose está en la lista que se mide
  V2  cero copias       `skills.external_dirs` ausente en los 12 configs
  V3  configs sanos     los 12 parsean (un YAML roto degrada el perfil entero
                        al config por defecto — incidente del 23-sep-2026)
  V4  catálogo íntegro  SKILL.md alcanzables == SKILL.md versionados en git
  V5  árbol limpio      ediciones de agente sin commitear
  V6  aduana            verify_skills.py
  V7  curador           estado y ledger (fuente de verdad de sus movimientos)
  V8  gate              ledger del hook: cuántas creaciones bloqueó/encauzó
  V9  recreaciones      ventanas de recreación del contenedor
  V10 fuera del repo    ninguna ruta de skills/perfiles/estado fuera del repo
                        (R16): lista negra de rutas retiradas + barrido acotado

HIGIENE (R4: toda edición de agente queda versionada)
  Si el árbol está sucio: atribuye cada ruta a perfil + sesión consultando los
  `state.db` de la flota, corre la aduana, commitea y empuja. La atribución es
  explícita sobre su confianza: si hay 0 candidatos o varios sesiones distintas
  en la misma ventana, la marca es «no concluyente» — nunca se inventa autoría.

USO
  python3 scripts/f3_higiene_diaria.py --dry-run     # solo reporta
  python3 scripts/f3_higiene_diaria.py               # reporta, commitea y empuja
  python3 scripts/f3_higiene_diaria.py --sin-push
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path('/root/hermes-agent-legacy-docker')
DATA = REPO / 'data'
CANON = REPO / 'skills'
CONT = 'hermes-agent'
PERFILES = ['bragi', 'brokkr', 'comms', 'freyja', 'heimdall', 'hermodr',
            'roshi', 'sindri', 'ullr', 'vigia', 'vili']
CONFIGS = [DATA / 'config.yaml'] + [DATA / 'profiles' / p / 'config.yaml' for p in PERFILES]
RAICES_CONT = ['/opt/data/skills'] + ['/opt/data/profiles/%s/skills' % p for p in PERFILES]
RUTAS_ESCRITURA = ('skill_manage', 'write_file', 'patch', 'edit',
                   'terminal', 'execute_code', 'apply_patch', 'str_replace_editor')
AHORA = time.time()

# ── Cargador YAML estricto (R7 ampliado a los configs) ──────────────────────
# Un config que dice dos veces la misma clave en el mismo nivel no rompe el
# parseo —y por eso pasa desapercibido—, pero describe dos intenciones a la vez.
try:
    import yaml
except Exception:                                   # pragma: no cover
    yaml = None

if yaml is not None:
    class _ClaveDuplicada(Exception):
        pass

    def _mapa_estricto(loader, node, deep=False):
        vistos = set()
        for k, _ in node.value:
            kk = loader.construct_object(k, deep=deep)
            if kk in vistos:
                raise _ClaveDuplicada('clave repetida en el mismo nivel: %r' % (kk,))
            vistos.add(kk)
        return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)

    class _LoaderEstricto(yaml.SafeLoader):
        pass

    _LoaderEstricto.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapa_estricto)
else:                                               # pragma: no cover
    _ClaveDuplicada = Exception
    _LoaderEstricto = None


# ── Notificación ────────────────────────────────────────────────────────────
# Destino: #sistema-servers del guild NeuralCrew Labs (canal de operaciones).
# Se publica con `hermes send`, que usa la API REST del bot de la flota (no abre
# sesión de gateway: darle el token al perfil vigia NO es opción, porque su
# gateway abriría una segunda sesión del MISMO bot y desconectaría la primera).
# El tema de las alertas es de Vigía (salud de infra), así que el mensaje va
# rotulado como suyo.
DISCORD_DESTINO = 'discord:1552059363500228618'
HERMES_BIN = '/opt/hermes/.venv/bin/hermes'
HERMES_HOME_ROOT = '/opt/data'
ROTULO = '🛰️ Vigía · salud de infra'


def log(msg=''):
    print(msg, flush=True)


def sh(cmd, cwd=None, timeout=180):
    try:
        return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        class R:
            returncode, stdout, stderr = 124, '', 'timeout'
        return R()


def dtexec(script, timeout=180):
    return sh('docker exec %s bash -lc %s' % (CONT, json.dumps(script)), timeout=timeout)


# ── V1 · un solo árbol ──────────────────────────────────────────────────────
def v1_inodo(informe):
    try:
        ino_host = '%d:%d' % (CANON.stat().st_dev, CANON.stat().st_ino)
    except Exception as e:
        informe['V1_inodo'] = {'ok': False, 'error': str(e)}
        return
    # Se miden las 12 rutas UNA POR UNA: si una desaparece (p. ej. su punto de
    # montaje se movió en el host), hay que decir CUÁL, no solo un conteo corto.
    # Lección del 23-sep: `mv data/skills` en el host arrancó el punto de montaje
    # de /opt/data/skills y el perfil default se quedó sin raíz de skills.
    medidas, distintas, ausentes = {}, [], []
    for p in RAICES_CONT:
        out = dtexec('stat -c "%%d:%%i" %s 2>/dev/null || echo AUSENTE' % p).stdout.strip()
        medidas[p] = out
        if out == 'AUSENTE' or not out:
            ausentes.append(p)
        elif out != ino_host:
            distintas.append('%s=%s' % (p, out))
    ok = not distintas and not ausentes and len(medidas) == len(RAICES_CONT)
    informe['V1_inodo'] = {'ok': ok, 'canon': ino_host, 'rutas': len(medidas),
                           'ausentes': ausentes, 'distintos': distintas}


# ── V2/V3 · configs ─────────────────────────────────────────────────────────
def v2_v3_configs(informe):
    try:
        import yaml
    except Exception:
        yaml = None
    con_ext, roto, sanos, dups = [], [], 0, []
    for p in CONFIGS:
        if not p.is_file():
            roto.append(str(p))
            continue
        txt = p.read_text(encoding='utf-8')
        if 'external_dirs' in txt:
            con_ext.append(str(p))
        if yaml is not None:
            try:
                if _LoaderEstricto is not None:
                    yaml.load(txt, Loader=_LoaderEstricto)
                else:
                    yaml.safe_load(txt)
                sanos += 1
            except _ClaveDuplicada as e:
                # parsea, pero dice dos cosas: se reporta aparte del YAML roto
                dups.append('%s: %s' % (p.name if p.parent.name == 'profiles'
                                        else 'root', e))
                sanos += 1
            except Exception:
                roto.append(str(p))
        else:
            sanos += 1
    informe['V2_external_dirs'] = {'ok': not con_ext, 'configs': con_ext}
    informe['V3_configs'] = {'ok': not roto, 'sanos': sanos,
                             'total': len(CONFIGS), 'rotos': roto,
                             'claves_duplicadas': dups}


# ── V4 · catálogo íntegro ───────────────────────────────────────────────────
def v4_catalogo(informe):
    en_git = sh('git ls-files "skills/**/SKILL.md"', cwd=REPO).stdout.split()
    cont = dtexec('find /opt/data/skills -name SKILL.md').stdout.split()
    nombres_git = sorted(x.replace('/SKILL.md', '') for x in en_git)
    nombres_cont = sorted(x.replace('/opt/data/', '').replace('/SKILL.md', '')
                          for x in cont)
    ok = nombres_git == nombres_cont
    faltan = sorted(set(nombres_git) - set(nombres_cont))
    sobran = sorted(set(nombres_cont) - set(nombres_git))
    informe['V4_catalogo'] = {'ok': ok, 'en_git': len(nombres_git),
                              'alcanzables': len(nombres_cont),
                              'faltan': faltan[:10], 'sin_versionar': sobran[:10]}


# ── V5 · árbol limpio ───────────────────────────────────────────────────────
def v5_arbol(informe):
    out = sh('git status --porcelain skills/', cwd=REPO).stdout
    lineas = [l for l in out.splitlines() if l.strip()]
    informe['V5_arbol'] = {'sucio': bool(lineas), 'n': len(lineas),
                           'rutas': [l[3:].strip() for l in lineas][:30]}


# ── V1b · censo de perfiles vs montajes ─────────────────────────────────────
def v1b_censo_montaje(informe):
    """V1 recorre RAICES_CONT: una lista ESCRITA A MANO. Un perfil 13 que nazca
    sin raíz montada no lo vería nadie, y escribiría en su carpeta local —una
    copia real—. Aquí se compara el censo de disco con la lista y con los
    destinos que declara el compose."""
    # los dot-dirs (.deleted y compañia) son servicio, no perfiles: se listan
    # aparte para que un perfil borrado no se confunda con un perfil sin montaje
    entries = [p for p in (DATA / 'profiles').iterdir() if p.is_dir()]
    censo = sorted(p.name for p in entries
                   if p.name != 'default' and not p.name.startswith('.'))
    servicio = sorted(p.name for p in entries if p.name.startswith('.'))
    sin_montaje = sorted(set(censo) - set(PERFILES))
    declarados_sin_perfil = sorted(set(PERFILES) - set(censo))
    comp = REPO / 'docker-compose.yml'
    destinos = []
    if comp.is_file():
        for l in comp.read_text(encoding='utf-8').splitlines():
            m = re.match(r'\s*-\s*\./skills:(/\S+)', l)
            if m:
                destinos.append(m.group(1))
    canon_lectura = '/opt/hermes/skills'
    no_medidos = sorted(set(destinos) - set(RAICES_CONT) - {canon_lectura})
    sin_destino = sorted(set(RAICES_CONT) - set(destinos))
    ok = not sin_montaje and not no_medidos and not sin_destino
    informe['V1b_censo'] = {'ok': ok, 'perfiles_en_disco': len(censo),
                            'dirs_de_servicio': servicio,
                            'sin_montaje': sin_montaje,
                            'declarados_sin_perfil': declarados_sin_perfil,
                            'destinos_compose': len(destinos),
                            'destinos_no_medidos': no_medidos,
                            'sin_destino': sin_destino}


# ── V10 · nada fuera del repositorio ────────────────────────────────────────
LEGADO_PROHIBIDO = ['/opt/data', '/opt/hermes/skills', '/root/.agents/skills',
                    '/opt/hermes/data']


CATALOGOS_AJENOS = REPO / 'docs' / 'skills' / 'catalogos-ajenos.json'


def v10_fuera_del_repo(informe):
    """R16: el host no tiene rutas de skills, perfiles o estado fuera del
    repositorio. Se comprueban dos cosas: la lista negra de rutas retiradas (su
    reaparición es un incidente) y los árboles de skills que NO estén en el
    catálogo de ajenos declarado (R10). Así el semáforo es útil —verde hoy— y
    cualquier árbol NUEVO bloquea."""
    reaparecidos = [p for p in LEGADO_PROHIBIDO if os.path.exists(p)]
    declarados = []
    if CATALOGOS_AJENOS.is_file():
        try:
            declarados = sorted(json.loads(
                CATALOGOS_AJENOS.read_text(encoding='utf-8')).get('catalogos', {}))
        except Exception as e:
            informe.setdefault('errores_vigilancia', []).append(
                'catalogos-ajenos.json ilegible: %s' % e)
    salida = sh('find /opt /root /srv /home -maxdepth 7 -name SKILL.md 2>/dev/null '
                '| grep -v "^/root/hermes-agent-legacy-docker/" '
                r'| grep -v "node_modules\|site-packages\|/.cache/\|.venv" '
                '| head -80').stdout.split()
    no_declarados = sorted({p for p in salida
                            if not any(p.startswith(r) for r in declarados)})
    informe['V10_fuera_repo'] = {'ok': not reaparecidos and not no_declarados,
                                 'rutas_retiradas_reaparecidas': reaparecidos,
                                 'catalogos_declarados': len(declarados),
                                 'no_declarados': no_declarados[:10],
                                 'n_skills_no_declaradas': len(no_declarados)}


# ── V6 · aduana ─────────────────────────────────────────────────────────────
def v6_aduana(informe):
    out = sh('python3 scripts/verify_skills.py', cwd=REPO, timeout=300).stdout
    err = re.search(r'Errores cr[ií]ticos:\s*(\d+)', out)
    adv = re.search(r'Advertencias menores:\s*(\d+)', out)
    ok = 'ADUANA SUPERADA' in out
    informe['V6_aduana'] = {'ok': ok,
                            'errores': int(err.group(1)) if err else None,
                            'advertencias': int(adv.group(1)) if adv else None}


# ── V7 · curador ────────────────────────────────────────────────────────────
def v7_curador(informe):
    est, led = CANON / '.curator_state', CANON / '.curator_ledger.jsonl'
    d = {}
    if est.is_file():
        try:
            d = json.loads(est.read_text(encoding='utf-8'))
        except Exception:
            d = {}
    n, ult = 0, None
    if led.is_file():
        lineas = [l for l in led.read_text(encoding='utf-8').splitlines() if l.strip()]
        n = len(lineas)
        if lineas:
            try:
                ult = json.loads(lineas[-1]).get('ts') or json.loads(lineas[-1]).get('timestamp')
            except Exception:
                ult = None
    informe['V7_curador'] = {'run_count': d.get('run_count'),
                             'last_run_at': d.get('last_run_at'),
                             'paused': d.get('paused'),
                             'ledger_entradas': n, 'ultimo_movimiento': ult}


# ── V8 · gate ───────────────────────────────────────────────────────────────
def v8_gate(informe):
    f = DATA / 'state' / 'autoskill_gate.jsonl'
    conteo = {'OMITIR': 0, 'EDITAR': 0, 'CREAR': 0}
    total24 = 0
    ultimo = None
    if f.is_file():
        for l in f.read_text(encoding='utf-8').splitlines():
            if not l.strip():
                continue
            try:
                r = json.loads(l)
            except Exception:
                continue
            v = r.get('veredicto')
            if v in conteo:
                conteo[v] += 1
            ts = r.get('ts', '')
            ultimo = ts or ultimo
            try:
                t = datetime.strptime(ts[:19], '%Y-%m-%dT%H:%M:%S').replace(
                    tzinfo=timezone.utc).timestamp()
                if AHORA - t > 86400:
                    pass
                else:
                    total24 += 1
            except Exception:
                pass
    informe['V8_gate'] = {'total': dict(conteo), 'ultimas_24h': total24, 'ultimo': ultimo}


# ── V9 · recreaciones ───────────────────────────────────────────────────────
def v9_recreaciones(informe):
    inicio = sh('docker inspect %s --format "{{.State.StartedAt}}"' % CONT).stdout.strip()
    ventanas_hoy = sorted(p.name for p in (DATA / 'state').glob('f3_ventana_*.json')
                          if time.strftime('%Y%m%d', time.localtime(p.stat().st_mtime)) ==
                          time.strftime('%Y%m%d'))
    informe['V9_recreaciones'] = {'contenedor_arrancado': inicio,
                                  'ventanas_hoy': ventanas_hoy}


# ── HIGIENE · atribución ────────────────────────────────────────────────────
def sesiones_que_tocaron(rel, nombre, errores=None):
    """Busca en los state.db de la flota qué sesiones escribieron esa ruta.

    Dos niveles: primero el camino relativo (preciso), luego el nombre de la
    skill (laxo). Devuelve (lista de candidatos, nivel). Los errores de consulta
    se acumulan en `errores` en vez de tragarse: un `except: continue` mudo fue
    justo lo que ocultó un bug de construcción de SQL el 23-sep-2026.
    """
    dbs = [DATA / 'state.db'] + sorted(DATA.glob('profiles/*/state.db'))
    ph = ','.join('?' for _ in RUTAS_ESCRITURA)
    sql = ("select session_id, tool_name, timestamp from messages "
           "where timestamp > ? and tool_name in (%s) "
           "and (ifnull(content,'') like ? or ifnull(tool_calls,'') like ?) "
           "order by timestamp desc limit 5") % ph
    for nivel, patron in (('ruta', rel), ('nombre', nombre)):
        cands = []
        for db in dbs:
            if not db.is_file():
                continue
            perfil = db.parent.name if db.parent.name != 'data' else 'default'
            try:
                c = sqlite3.connect('file:%s?mode=ro' % db, uri=True, timeout=8)
                params = [AHORA - 7 * 86400] + list(RUTAS_ESCRITURA) + \
                         ['%' + patron + '%', '%' + patron + '%']
                filas = c.execute(sql, params).fetchall()
                c.close()
            except Exception as e:
                # una db sin tabla `messages` no es un error: es una db vacía
                if errores is not None and 'no such table' not in str(e):
                    errores.append('%s: %s' % (db, e))
                continue
            for sid, tool, ts in filas:
                cands.append({'perfil': perfil, 'session_id': sid, 'tool': tool,
                              'ts': ts,
                              'hace_min': round((AHORA - (ts or 0)) / 60, 1)})
        if cands:
            cands.sort(key=lambda x: x['ts'] or 0, reverse=True)
            return cands, nivel
    return [], 'sin rastro'


def atribuir(rutas, errores=None):
    res = {}
    for rel in rutas:
        partes = Path(rel).parts
        nombre = partes[1] if len(partes) > 2 else Path(rel).stem
        cands, nivel = sesiones_que_tocaron(rel.replace('skills/', ''), nombre, errores)
        if not cands:
            res[rel] = {'origen': 'sin rastro en los state.db', 'confianza': 'ninguna'}
            continue
        top = cands[0]
        sesiones = {c['session_id'] for c in cands}
        confianza = 'alta' if (len(sesiones) == 1 and nivel == 'ruta') else \
                    'media' if len(sesiones) == 1 else 'baja'
        res[rel] = {'origen': '%s / %s' % (top['perfil'], top['session_id']),
                    'tool': top['tool'], 'hace_min': top['hace_min'],
                    'nivel': nivel, 'confianza': confianza,
                    'otras_sesiones': len(sesiones) - 1}
    return res


def higiene(informe, aplicar=True, push=True):
    rutas = informe.get('V5_arbol', {}).get('rutas') or []
    if not rutas:
        informe['higiene'] = {'accion': 'nada que versionar'}
        return
    atrib, err_atrib = {}, []
    atrib = atribuir(rutas, err_atrib)
    informe['atribucion'] = atrib
    if err_atrib:
        informe['atribucion_errores'] = err_atrib
    if not aplicar:
        informe['higiene'] = {'accion': 'dry-run: se habría commiteado',
                              'rutas': len(rutas)}
        return
    sh('git add -A skills/', cwd=REPO)
    aduana = informe.get('V6_aduana', {})
    marca = ''
    if aduana.get('ok') is False:
        marca = ' [ADUANA: %s errores / %s advertencias]' % (
            aduana.get('errores'), aduana.get('advertencias'))
    cuerpo = ['higiene diaria del árbol único — %s' % time.strftime('%Y-%m-%d %H:%M'),
              '', 'Rutas versionadas: %d%s' % (len(rutas), marca), '']
    for rel in rutas:
        a = atrib.get(rel, {})
        cuerpo.append('  · %s' % rel)
        cuerpo.append('      origen: %s (confianza %s%s)' % (
            a.get('origen', '?'), a.get('confianza', '?'),
            '' if a.get('confianza') == 'alta' else
            ', nivel %s%s' % (a.get('nivel', '?'),
                              '' if not a.get('otras_sesiones') else
                              ', %d sesiones más en la ventana' % a['otras_sesiones'])))
    msg = 'chore(skills): ' + '\n'.join(cuerpo)
    r = sh('git commit -F - <<"MSG"\n%s\nMSG' % msg, cwd=REPO)
    if r.returncode != 0:
        informe['higiene'] = {'accion': 'commit falló', 'salida': r.stdout[-300:] + r.stderr[-300:]}
        return
    head = sh('git rev-parse HEAD', cwd=REPO).stdout.strip()
    estado = {'accion': 'commiteado', 'commit': head[:12], 'rutas': len(rutas)}
    if push:
        sh('git push origin HEAD:main', cwd=REPO)
        remoto = sh('git ls-remote origin refs/heads/main', cwd=REPO).stdout.split()
        ok = bool(remoto) and remoto[0] == head
        estado['push'] = ok
        if not ok:
            estado['alerta_push'] = 'HEAD != origin/main tras el push'
    informe['higiene'] = estado


def mensaje_alerta(informe, motivos):
    """Cuerpo del aviso para el canal de operaciones."""
    L = [ROTULO, '', '⚠️ Requiere atención: %d motivo(s)' % len(motivos), '']
    for m in motivos:
        L.append('  · %s' % m)
    L += ['', 'Estado del árbol único:',
          '  V1 inodo único ....... %s' % informe.get('V1_inodo', {}).get('ok'),
          '  V1b censo vs montaje . %s' % informe.get('V1b_censo', {}).get('ok'),
          '  V10 fuera del repo ... %s' % informe.get('V10_fuera_repo', {}).get('ok'),
          '  V2 external_dirs ..... %s' % (not informe.get('V2_external_dirs', {}).get('configs')),
          '  V3 configs válidos ... %s' % informe.get('V3_configs', {}).get('sanos'),
          '  V4 catálogo == git ... %s (%s)' % (informe.get('V4_catalogo', {}).get('ok'),
                                               informe.get('V4_catalogo', {}).get('alcanzables')),
          '  V5 árbol sucio ....... %s' % informe.get('V5_arbol', {}).get('n'),
          '  V6 aduana ............ %s' % informe.get('V6_aduana', {}).get('ok'),
          '  V8 gate (24h) ........ %s decisiones' % informe.get('V8_gate', {}).get('ultimas_24h'),
          '  higiene .............. %s' % json.dumps(informe.get('higiene', {}), ensure_ascii=False)[:160],
          '', 'Informe: %s' % (DATA / 'state' / 'skills_higiene_last.json')]
    return '\n'.join(L)


def notificar(informe, motivos, aplicar=True, prueba=False):
    """Publica el aviso en Discord SOLO si algo se sale del guion (o si es prueba)."""
    if not motivos and not prueba:
        return {'enviado': False, 'motivo': 'sin novedad: no se notifica'}
    cuerpo = mensaje_alerta(informe, motivos) if not prueba else (
        ROTULO + '\n\n✅ Prueba del canal de alertas del job de higiene del árbol '
        'único (F3). Se publica solo ante desviaciones; este es el formato.')
    tmp = Path('/tmp/higiene_alerta.txt')
    tmp.write_text(cuerpo, encoding='utf-8')
    if not aplicar:
        return {'enviado': False, 'motivo': 'dry-run', 'cuerpo': cuerpo[:200]}
    # El binario de hermes vive DENTRO del contenedor y este job corre en el
    # host (cron): se ejecuta por docker exec con el cuerpo por stdin, sin
    # exponer credenciales fuera del contenedor.
    cmd = ('docker exec -i -e HERMES_HOME=%s -e HOME=%s %s %s send --to %s '
           '--subject "higiene diaria del arbol unico" --file - --json < %s'
           % (HERMES_HOME_ROOT, HERMES_HOME_ROOT, CONT, HERMES_BIN, DISCORD_DESTINO, tmp))
    r = sh(cmd, timeout=120)
    ok = r.returncode == 0
    res = {'enviado': ok, 'destino': DISCORD_DESTINO, 'rotulo': ROTULO,
           'rc': r.returncode, 'salida': (r.stdout or r.stderr or '').strip()[:300]}
    if not ok:
        log('  ⚠️ la notificación a Discord falló (rc=%s): %s' % (r.returncode, res['salida']))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--sin-push', action='store_true')
    ap.add_argument('--sin-notificar', action='store_true')
    ap.add_argument('--prueba-notificacion', action='store_true',
                    help='envía un mensaje de prueba al canal de alertas')
    ap.add_argument('--sin-adopt', action='store_true',
                    help='no adoptar skills nuevas (salta la coherencia del modelo F4)')
    a = ap.parse_args()

    informe = {'ts': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'host': sh('hostname').stdout.strip()}
    log('═══ VIGILANCIA E HIGIENE DEL ÁRBOL ÚNICO · %s ═══' % informe['ts'])
    planes = ((v1_inodo, 'V1_inodo'), (v1b_censo_montaje, 'V1b_censo'),
              (v2_v3_configs, 'V2_external_dirs'),
              (v4_catalogo, 'V4_catalogo'), (v5_arbol, 'V5_arbol'),
              (v6_aduana, 'V6_aduana'), (v7_curador, 'V7_curador'),
              (v8_gate, 'V8_gate'), (v9_recreaciones, 'V9_recreaciones'),
              (v10_fuera_del_repo, 'V10_fuera_repo'))
    for fn, clave in planes:
        try:
            fn(informe)
        except Exception as e:
            informe.setdefault('errores_vigilancia', []).append('%s: %s' % (clave, e))
        if clave == 'V2_external_dirs':
            log('  %-18s %s | configs %s' % ('V2/V3 configs',
                json.dumps(informe.get('V2_external_dirs', {}), ensure_ascii=False)[:110],
                json.dumps(informe.get('V3_configs', {}), ensure_ascii=False)[:150]))
        else:
            log('  %-18s %s' % (clave, json.dumps(informe.get(clave, {}),
                                                  ensure_ascii=False)[:230]))

    higiene(informe, aplicar=not a.dry_run, push=not a.sin_push)

    # Coherencia del modelo F4: el canon es curator-managed por declaración del
    # dueño. Si el job versiona skills nuevas y no las adopta, quedan fuera del
    # universo del curador sin que nadie lo note (deriva silenciosa).
    if (not a.dry_run and informe.get('higiene', {}).get('accion') == 'commiteado'
            and not a.sin_adopt):
        r = sh('docker exec -u 10000 -e HERMES_HOME=%s -e HOME=%s %s %s curator '
               'adopt --all-unmanaged --yes' % (HERMES_HOME_ROOT, HERMES_HOME_ROOT,
                                                CONT, HERMES_BIN), timeout=900)
        sal = [l for l in (r.stdout or r.stderr or '').strip().splitlines() if l.strip()]
        informe['higiene']['adopt'] = {'rc': r.returncode, 'salida': sal[-2:]}
        log('  adopt no gestionadas: rc=%s %s' % (r.returncode, sal[-1:] or ''))

    atencion = []
    if not informe.get('V1_inodo', {}).get('ok'):
        atencion.append('inodo único roto: %s' % informe.get('V1_inodo'))
    if informe.get('V2_external_dirs', {}).get('configs'):
        atencion.append('external_dirs reapareció: %s' % informe['V2_external_dirs']['configs'])
    if not informe.get('V3_configs', {}).get('ok'):
        atencion.append('configs con YAML roto: %s' % informe['V3_configs'].get('rotos'))
    if not informe.get('V4_catalogo', {}).get('ok'):
        atencion.append('catálogo divergente de git: faltan=%s sin_versionar=%s' % (
            informe['V4_catalogo'].get('faltan'), informe['V4_catalogo'].get('sin_versionar')))
    if informe.get('V1b_censo', {}).get('ok') is False:
        atencion.append('censo vs montaje: perfiles sin raiz=%s · destinos no medidos=%s'
                        % (informe['V1b_censo'].get('sin_montaje'),
                           informe['V1b_censo'].get('destinos_no_medidos')))
    if informe.get('V3_configs', {}).get('claves_duplicadas'):
        atencion.append('configs con claves duplicadas: %s'
                        % informe['V3_configs']['claves_duplicadas'])
    if informe.get('V10_fuera_repo', {}).get('ok') is False:
        atencion.append('rutas fuera del repositorio: reaparecidas=%s · arboles sin declarar=%s'
                        % (informe['V10_fuera_repo'].get('rutas_retiradas_reaparecidas'),
                           informe['V10_fuera_repo'].get('no_declarados')))
    if informe.get('V6_aduana', {}).get('ok') is False:
        atencion.append('aduana en rojo')
    inf = informe.get('higiene', {})
    if inf.get('push') is False or inf.get('accion') in ('commit falló',):
        atencion.append('higiene: %s' % inf)
    informe['requiere_atencion'] = bool(atencion)
    informe['motivos'] = atencion

    # Notificación a Discord (Vigía) solo si algo se sale del guion
    informe['notificacion'] = notificar(informe, atencion,
                                        aplicar=not a.dry_run and not a.sin_notificar,
                                        prueba=a.prueba_notificacion)

    destino = DATA / 'state' / 'skills_higiene_last.json'
    destino.write_text(json.dumps(informe, indent=1, ensure_ascii=False), encoding='utf-8')
    # continuidad del contrato anterior (lo que ya consumía el vigilante viejo)
    (DATA / 'state' / 'skills_sync_alert.json').write_text(json.dumps(
        {'ts': informe['ts'], 'requiere_atencion': informe['requiere_atencion'],
         'parity': informe.get('V4_catalogo', {}).get('ok'),
         'motivos': atencion, 'detalle': str(destino)}, indent=1, ensure_ascii=False),
        encoding='utf-8')

    log('')
    log('  higiene   : %s' % json.dumps(inf, ensure_ascii=False)[:300])
    log('  atención  : %s' % (atencion or 'nada — todo en guion'))
    log('  informe   : %s' % destino)
    return 0 if not atencion else 3


if __name__ == '__main__':
    sys.exit(main())
