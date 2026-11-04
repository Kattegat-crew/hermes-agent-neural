#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Propaga la corrección del mito del curador a las memorias de la flota (F3).

Solo reescribe las afirmaciones FALSAS, conservando el trabajo pendiente útil.
La vía real de escritura del canon es el árbol montado; `hermes curator adopt`
no aplica a árboles de `external_dirs`.
"""
import shutil
import time
from pathlib import Path

R = Path('/root/hermes-agent-legacy-docker')
BK = R / 'data' / 'backups' / ('memorias_mito_%s' % time.strftime('%Y%m%d-%H%M%S'))
BK.mkdir(parents=True, exist_ok=True)

BRAGI = R / 'data' / 'profiles' / 'bragi' / 'memories' / 'MEMORY.md'
DEFAULT = R / 'data' / 'memories' / 'MEMORY.md'

# ── 1. bragi, línea 11 ──────────────────────────────────────────────────────
nuevo_bragi_11 = (
    'Skills user-owned en bragi: el bloqueo por «not curator-managed» era del código '
    'ANTERIOR al commit 1e6a94ee71 (20-sep 01:59); desde F3 (23-sep-2026) `patch`/'
    '`write_file`/`edit` son autónomos y la raíz de ESCRITURA de los 12 perfiles ES el '
    'canon versionado — editar una skill = un diff de git. neuralcrew-guion-series-ops, '
    'campaign-script-revision, neuralcrew-campaign-content: editables directo, SIN '
    '`hermes curator adopt` (que además no aplica a árboles de `external_dirs`).'
)

# ── 2. default, línea 132 ───────────────────────────────────────────────────
nuevo_default_132 = (
    'Curator/library ownership — MITO CORREGIDO 23-sep-2026 (verificado en vivo en el '
    'contenedor DEV): el claim «created_by=None ⇒ skill_manage RECHAZA patches» es FALSO '
    'desde el commit 1e6a94ee71 (20-sep 01:59). Hoy el guard de proveniencia solo aplica a '
    'delete/remove_file; `patch`/`write_file`/`edit` son autónomos por diseño (comentarios '
    'literales del código), igual que `_pinned_guard` y `_org_mirror_write_guard`, que '
    'también son solo-destructivos. Los rechazos «not curator-managed» del 11–19-sep son del '
    'código ANTERIOR a ese commit: no volver a citarlos como comportamiento vigente, y no '
    'depender de `hermes curator adopt` como vía de escritura. Desde F3 (23-sep-2026) la raíz '
    'de ESCRITURA de los 12 perfiles ES el canon montado y versionado; el job de higiene '
    '(cron 05:20) commitea cada edición con perfil y sesión de origen. Sigue vigente lo del '
    'CREATE: la `description` debe caber en la ventana de disparo del índice (57 caracteres '
    'para la primera frase) o la skill queda invisible.'
)

# ── 3. default, línea 154 ───────────────────────────────────────────────────
cabeza_154_vieja = (
    'Skill ingest-pipeline (research/): WRITES AUTÓNOMOS RECHAZADOS (verificado 15-sep-2026, '
    'skill_manage write_file → \'not curator-managed\', created_by=None) — añadir a la lista '
    'de no-editables; requiere `hermes curator adopt ingest-pipeline`. Trabajo pendiente tras '
    'adoptar:'
)
cabeza_154_nueva = (
    'Skill ingest-pipeline (research/): el rechazo que verifiqué el 15-sep-2026 («not '
    'curator-managed», created_by=None) es del código ANTERIOR al commit 1e6a94ee71; hoy '
    '`write_file`/`patch` son autónomos y NO requiere `curator adopt`. Trabajo pendiente:'
)

# ── 4. default, línea 199 ───────────────────────────────────────────────────
cabeza_199_vieja = (
    '18-sep: skill `typesafe-ai` (ai/) rechazada por created_by=None (biblioteca unmanaged '
    'desde el rebuild 12-sep) — al adoptarla inyectarle'
)
cabeza_199_nueva = (
    '18-sep: `typesafe-ai` (ai/) — el rechazo por created_by=None es del código anterior a '
    '1e6a94ee71 y NO requiere adopt; contenido pendiente de inyectar:'
)

# ── 5. default, línea 213 (audit del 21-sep, superado) ──────────────────────
nuevo_default_213 = (
    'Árbol de skills de la flota DEV — SUPERADO por F3 (23-sep-2026). ESTADO VIGENTE: el canon '
    '(repo /root/hermes-agent-legacy-docker/skills) ES el árbol del runtime — montado en /opt/hermes/skills y '
    'en las 12 raíces de ESCRITURA (/opt/data/skills + profiles/<perfil>/skills), un solo inodo, '
    '718 SKILL.md alcanzables == versionados en git, write-probe del runtime en verde. '
    '`skills.external_dirs` eliminado de los 12 configs: era justamente lo que dejaba al curador '
    'FUERA del canon (regla dura de agent/curator.py). Los agentes escriben en el canon y el job '
    'de higiene (cron 05:20, scripts/f3_higiene_diaria.py) versiona cada edición atribuyendo '
    'perfil + sesión desde los state.db. El audit del 21-sep (717 canon vs 719 copia, 12 '
    'montajes ausentes, curador sin universo) ya NO aplica. Procedimiento y pitfalls en '
    'skills/core/hermes-fleet-operations/references/migracion-raices-skills-al-canon.md. '
    'Pendiente: F5 (árboles externos: /root/.agents/skills con 2 crons de Meta Ads, '
    '/neuralcrew_agent y el /opt/data del host con 4 skills huérfanas).'
)


def reemplaza_linea(p, n, nuevo):
    lineas = p.read_text(encoding='utf-8').splitlines(keepends=True)
    viejo = lineas[n - 1]
    lineas[n - 1] = nuevo.rstrip('\n') + '\n'
    p.write_text(''.join(lineas), encoding='utf-8')
    return len(viejo), len(nuevo)


def reemplaza_sub(cadena, viejo, nuevo):
    if viejo not in cadena:
        return cadena, False
    return cadena.replace(viejo, nuevo, 1), True


shutil.copy2(BRAGI, BK / 'bragi_MEMORY.md')
shutil.copy2(DEFAULT, BK / 'default_MEMORY.md')
print('respaldo: %s' % BK)

a, b = reemplaza_linea(BRAGI, 11, nuevo_bragi_11)
print('bragi:11  %d -> %d chars' % (a, b))

a, b = reemplaza_linea(DEFAULT, 132, nuevo_default_132)
print('default:132  %d -> %d chars' % (a, b))

t = DEFAULT.read_text(encoding='utf-8')
t, ok1 = reemplaza_sub(t, cabeza_154_vieja, cabeza_154_nueva)
t, ok2 = reemplaza_sub(t, cabeza_199_vieja, cabeza_199_nueva)
DEFAULT.write_text(t, encoding='utf-8')
print('default:154 cabeza reemplazada:', ok1)
print('default:199 cabeza reemplazada:', ok2)

a, b = reemplaza_linea(DEFAULT, 213, nuevo_default_213)
print('default:213  %d -> %d chars' % (a, b))
