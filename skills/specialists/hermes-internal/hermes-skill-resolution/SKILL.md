---
name: hermes-skill-resolution
description: "Use when a job runs without its skills (name collision)."
tags: [skills, resolucion, ambiguedad, colision, catalogo, cron, dedupe]
version: "1.0"
author: Ragnar (curator)
created: 2026-09-11
category: devops
metadata:
  hermes:
    tags: [skills, catalogo, resolucion, ambiguedad, cron, degradado, dedupe]
    related_skills: [cron-fleet-audit, hermes-skills-provisioning, hermes-skills-curator, skill-auditor]
---

# Resolución de skills en Hermes (nombres, rutas y catálogo ambiguo)

Clase de fallo: **una skill que existe en disco no carga** y el consumidor (cron o agente)
sigue funcionando *degradado y en silencio*. No hay error visible para el usuario; el único
rastro está en la cabecera del artefacto del job y en los logs.

## Cuándo usar

- Un cron o agente corrió **sin** sus skills y su artefacto empieza con
  `[IMPORTANT: The following skill(s) were listed for this job but could not be found and were skipped: ...]`.
- `skill not found` / "la skill no carga" **con la skill presente** en disco.
- `Ambiguous skill name '<n>': N skills match ...`.
- Vas a declarar `skills:` en un job (`cronjob_manage`, `hermes cron create|edit`) o a limpiar/auditar el catálogo.

## Mecánica real (lo que hay que entender)

**Orden de búsqueda en `skill_view()`** (`/opt/hermes/tools/skills_tool.py`), `all_dirs` se arma
así (`:1245-1250`) y se consultan **todos** los directorios, en este orden:

1. `get_project_skills_dirs()` → `<git-root>/.hermes/skills` y `<git-root>/.agents/skills`, solo si
   `skills.project_discovery != false` **y** el repo está en `skills.trusted_project_dirs`
   (`agent/skill_utils.py:835`, `:849`). Si hay candidatos de este tier, **ganan** sobre los demás
   (`:1345-1367`).
2. `_skills_dir()` = **`<HERMES_HOME>/skills`** (`:148-159`; `hermes_constants.py:114` decide el home).
3. `get_external_skills_dirs()` = `skills.external_dirs` expandidos, existentes, deduplicados y
   excluyendo el local (`skill_utils.py:534-614`).

**Estrategias de match por directorio** (`:1285-1343`): ruta directa `dir/<nombre>` (aquí funciona el
**prefijo de categoría**: `autonomous-ai-agents/hermes-agent`), forma categorizada para el fall-through
de namespace de plugin, y búsqueda recursiva por nombre.

**Ambigüedad:** el loader **no corta en el primer match**; acumula candidatos de todos los directorios y
todas las estrategias y, si hay más de uno, responde `Ambiguous skill name '<n>': N skills …`
(`:1375-1391`, mensaje en `:1379`) sin cargar nada. **No existe clave de config** para silenciarlo ni
para elegir ganador (solo renombrar o pasar la ruta categorizada).

**Carga en crons** (`cron/scheduler.py:4820` `_build_job_prompt`): lee `job['skills']` (con fallback al
legacy `job['skill']`), intenta expandir **bundle** primero y luego `skill_view(...)`; si falla →
`warning + skipped + continue` (`:5025-5033`) y aviso en el prompt (`:5052-5059`). **El job NO aborta:**
corre degradado. El único aborto duro es el escáner de inyección sobre el prompt ensamblado
(`:6086-6098`). Con éxito llama `bump_use()` para el curator (`:5036-5039`).

**Bundles y plugins (namespaces):** bundles = alias YAML en `<HERMES_HOME>/skill-bundles`
(`agent/skill_bundles.py:66-76`, override `HERMES_BUNDLES_DIR`); un job puede declararlos en `skills:`.
Skills de plugins se resuelven **solo** por nombre calificado `plugin:skill` (`tools/skills_tool.py:1127-1224`)
y **no** entran al árbol plano ni al índice del prompt.

## Verificar antes de culpar al job (receta)

```bash
HERMES_HOME=<home> HOME=<home> /opt/hermes/.venv/bin/python -c "
import json
from tools.skills_tool import skill_view
from agent.skill_utils import normalize_skill_lookup_name
for n in ['<nombre>', '<categoria>/<nombre>']:
    r = json.loads(skill_view(normalize_skill_lookup_name(n)))
    print(n, r.get('success'), r.get('error'))"
```

Esperado con duplicado: nombre pelado → `False` + `Ambiguous skill name`;
`<categoria>/<nombre>` → `True`. Con eso ya tienes causa raíz probada, no hipótesis.

## Arreglos

1. **Inmediato y no destructivo:** declarar la **ruta categorizada explícita** en el job
   (`skills: ["autonomous-ai-agents/hermes-agent", "research/competitor-news-monitor"]`),
   verificada con la receta de arriba. Es reparable hoy, sin tocar el catálogo.
2. **De fondo:** deduplicar el catálogo, **una copia por nombre** (inventario antes/después).
   Nunca a mano sobre cientos de carpetas: es un trabajo de curaduría con evidencia
   (`scripts/find_duplicate_skill_names.py` da el inventario; después se archiva la copia
   sobrante y se re-verifica que cada nombre siga resolviendo `success=True`).

## Inventario de duplicados

```bash
python3 scripts/find_duplicate_skill_names.py                 # raíces por defecto
python3 scripts/find_duplicate_skill_names.py /opt/data/skills /opt/data/home/.hermes/skills
# exit 1 si hay duplicados -> sirve como watchdog
```

## Rastro en logs

```bash
grep -a "Skill name collision" <home>/logs/errors.log* | tail -20
```

Da el histórico (nombres, fechas, las dos rutas que compiten) — sirve para saber **desde cuándo**
un consumidor viene degradado y si el problema es sistémico o de un nombre suelto.

## Cuántas skills ve REALMENTE cada agente (medir, no suponer)

Un perfil no "ve" o "no ve": lo normal en una flota multiprofile es que vea una **granja de symlinks
parcial y podrida** dentro de su propio `profiles/<p>/skills` (los enlaces apuntan al catálogo central
por **nombre plano**, así que se rompen en cuanto la skill se mueve a una categoría) y/o una copia
propia desactualizada.

- Medición mínima: contar `SKILL.md` reales + enlaces resueltos/rotos + probar un nombre conocido
  (`skill_view('<nombre-del-catalogo>')`). Un nombre que no resuelve **no** significa que el perfil
  esté ciego a todo.
- Un enlace roto + el nombre declarado en un job = degradado silencioso. Da la ruta **categorizada**
  al job y, si vas a unificar, elimina las granjas en vez de repararlas.
- Para ver el catálogo que un perfil usaría, resuelve con SU home:
  `HERMES_HOME=/opt/data/profiles/<p> HOME=/opt/data/profiles/<p> python -c "from tools import skills_tool;print(skills_tool._skills_dir());from agent.skill_utils import get_external_skills_dirs;print(get_external_skills_dirs())"`.
- **Antes de unificar el catálogo** (una sola ruta canónica para toda la flota):
  `references/catalogo-una-ruta-canonica.md` trae el inventario, el orden de fases obligatorio,
  los riesgos medidos (curator que re-divergen en vivo, granjas rotas, skills únicas que se pierden)
  y los criterios de aceptación.

## Pitfalls

- **Verifica `on_demand` antes de asumirlo:** en algunos builds la clave `skills.on_demand: true`
  existe en `config.yaml` pero **ningún** archivo de código la lee (`grep -rn 'on_demand' /opt/hermes --include=*.py`)
  y `DEFAULT_CONFIG` no la contiene → el índice completo se sigue inyectando. No la cites como
  mitigación de coste de contexto sin comprobarlo, y no intentes "buscar por tema" con una tool
  `skill_search` sin verificar que exista en tu build (`skills_list` acepta `category`/`task_id`).
- **Granjas de symlinks:** un perfil puede ver decenas de skills por enlaces que apuntan al catálogo
  por nombre plano; en cuanto el catálogo reorganiza en categorías, los enlaces se rompen **en silencio**.
  Cuenta resueltos vs rotos antes de concluir que una skill "no existe" para ese agente.
- **No confundir "no existe" con "no resuelve".** Si el `SKILL.md` está en disco,
  el problema es la resolución (nombre/ruta), no la instalación.
- **El skip es silencioso por diseño**: el job termina `ok`. Si auditas solo por `last_status`,
  nunca lo ves; hay que abrir el artefacto (`cron/output/<id>/*.md`) o los logs.
- **No renombrar/burgar el catálogo a la ligera**: otros jobs y agentes referencian rutas;
  un nombre roto falla del mismo modo silencioso. Prefiere pinnear la ruta explícita primero.
- **Declarar la ruta categorizada cambia la referencia**: si más adelante mueves la skill de
  categoría, el job vuelve a quedar degradado en silencio. Verifica después de cada reorganización.
- Las skills **bundled/hub** y las user-owned pueden estar fuera del árbol que crees: confirma la
  raíz real (`skill_view` te devuelve `path`/`skill_dir`) antes de concluir que falta.

## Referencias

- `references/ambiguity-2026-09.md` — caso real (11/09/2026): 73 nombres duplicados, 12 con
  colisión registrada en uso real, y los dos jobs que corrieron degradados por esto.
- `references/catalogo-una-ruta-canonica.md` — playbook de unificación del catálogo (varias raíces
  + granjas de symlinks) hacia **una sola ruta canónica** por flota, con fases reversibles y
  verificación por el loader.
- `scripts/find_duplicate_skill_names.py` — inventario de duplicados (watchdog-friendly).
- `cron-fleet-audit` — la clase "job que corre degradado" dentro de la auditoría de flota.
- `hermes-skills-provisioning` / `hermes-skills-curator` — instalar/organizar skills en perfiles.
