---
name: hermes-config-integrity
description: Use when changing config.yaml or creating code tasks.
---

# hermes-config-integrity — el config no se edita, se aplica

Nace de un incidente real (2026-11-05): un worker de kanban añadió `- langfuse-fleet` con indentación de 2 espacios dentro de una lista de 4, dejó `config.yaml` sin parsear y **tumbó toda la capa de herramientas** — incluido su propio proceso, que murió dos veces hasta `gave_up`. Las tools no arrancaban porque el runtime parsea el config antes de cada llamada.

## Regla 1 — nunca escribir el archivo vivo

Prohibido `sed -i`, `>>`, `tee`, `python -c open(...,'w')` o `patch` sobre `config.yaml`. Se aplica un **candidato**:

```bash
cd /opt/hermes-agent-data
python3.12 scripts/cfgctl.py snapshot --label antes-de-X     # respaldo con sha
cp config.yaml /tmp/candidato.yaml                            # se edita el candidato
python3.12 scripts/cfgctl.py validate /tmp/candidato.yaml     # falla = no se aplica
python3.12 scripts/cfgctl.py apply /tmp/candidato.yaml        # atómico + respaldo + revalidación
```

`apply` escribe un temporal, lo valida, y solo entonces `os.replace` sobre el real. Si el resultado no parsea, restaura solo. Un config roto **nunca** llega a disco.

Siempre `python3.12`: el `python3` del sistema no trae PyYAML.

## Regla 2 — las ventanas D-I-V-E no autorizan escritura cruda

`hooks/guard_config_model_mutation.py` bloquea escrituras a config/.env/profiles. Una ventana en `/opt/data/state/config_guard_override.json` **solo** permite comandos que invoquen `cfgctl.py`; una escritura directa sigue bloqueada aunque la ventana esté abierta. Ese era el punto ciego del 5-nov: la ventana de despliegue abrió la puerta a todo.

El `objetivo` de la ventana se compara como substring del comando — nombra el token que vas a usar (`cfgctl`), no una etiqueta libre.

## Regla 3 — centinela por inotify, no por cron

`hermes-config-guard.path` (systemd) observa el archivo con `PathModified`; al cambiar, `hermes-config-guard.service` valida y, si no parsea, restaura el respaldo válido más reciente y deja:

- copia del roto: `config.yaml.broken-<ts>`
- bandera: `ops/cfg/LAST_ROLLBACK.json`
- bitácora: `ops/cfg/config_guard.log`

Verificado end-to-end: archivo roto → restaurado en ≤5 s con sha idéntico al bueno. El informe matutino debe leer `LAST_ROLLBACK.json`; si existe con fecha de hoy, algo intentó romper el config.

## Regla 4 — toda tarjeta, en su worktree

`hermes kanban create` arranca en `scratch`. Para tarjetas de código usar el wrapper:

```bash
python3.12 scripts/kcard.py --title "..." --repo /opt/mi-repo --assignee default
```

Crea la tarjeta con `--workspace worktree:<toplevel>` y `--branch wt/<slug>`, y escribe el contrato de aislamiento en el cuerpo. Tres modos, todos explícitos — sin ninguno el script se niega (rc=2), porque el scratch implícito fue el agujero original:

- `--repo /ruta` → worktree git, rama `wt/<slug>`: código.
- `--dir /ruta` → directorio existente: medios, datos, documentos.
- `--scratch` → sandbox efímero declarado para tareas que no escriben archivos (investigación, decisión, revisión). El cuerpo queda anotado con el contrato: si aparece código, se recrea la tarjeta con `--repo`.

Rechaza rutas que no sean repo git.

## Regla 5 — forma ≠ semántica, y el config de perfil es standalone (10-nov-2026)

- **Listas como string citado**: `voice.stop_phrases: '["stop", "para", "corta"]'` parsea perfecto y revienta en runtime — el worker del perfil muere con `invalid_params` al iniciar la conexión al modelo (tumbó t_32594fbe en brokkr). `cfgctl validate` no lo caza: valida forma, no tipos. Detección masiva: `grep -rn "stop_phrases: '" /opt/data/config.yaml /opt/data/profiles/*/config.yaml` (afectó 10 de 12 perfiles; roshi y raíz ya estaban correctos). Regla general: cualquier valor que empieza con `'['` es sospechoso de lista-escrita-como-string.
- **El config de perfil NO hereda la raíz**: los bloques declarados solo en la raíz (p. ej. `kanban.max_in_progress: 3`) no llegan a los gateways de perfil — roshi logueó `kanban.max_in_progress unset` con la raíz declarándolo. Nunca asumir herencia raíz→perfil: verificar en el log del gateway que gana.
- **Los settings del dispatcher se resuelven UNA vez por boot**: `_kanban_dispatcher_boot()` llama `_resolve_dispatcher_settings(kanban_cfg, _kb)` y el bucle conserva esos settings toda la vida del proceso (`gateway/kanban_watchers.py`). Editar `kanban.*` en config.yaml (p. ej. `max_in_progress_per_profile: 1`) NO entra en vigor hasta reiniciar el gateway dueño del lock — verificado 10-nov: config escrito 17:23, gateway vivo desde 04:50, los workers seguían chocando con el valor viejo. Después de cambiar ajustes de kanban: reiniciar el gateway dueño del dispatcher y confirmar el efecto real, no dar por aplicado el edit.
- **Kanban dispatcher es singleton**: el lock `kanban/.dispatcher.lock` deja que SOLO un gateway despache (los demás loguean "another gateway already holds the dispatcher lock; this gateway will NOT dispatch"). Los `owner silent for 242s: Gateway starting: deadline` NO son 12 dispatchers compitiendo: es el worker pidiendo admisión mientras el gateway dueño del lock reinicia o atiende un turno largo. Diagnóstico: `grep "dispatcher lock\|Gateway starting" /opt/data/logs/gateway.log` + `hermes kanban dispatch --dry-run` (quién despacha y cuánto trabajo hay ready — 0 spawned puede ser board vacía, no dispatcher roto).
- **El dashboard no se arregla reiniciando**: `:9112` sirve un release pineado a commit (`releases/dashboard/releases/<hash>` vía symlink `current`), que puede quedar atrás del core (`0.22.0` vs `0.23.1` con el mismo pyproject `0.0.0`). Actualizar = promover release nuevo (`releases/dashboard/bin/promote-release`), no restart del proceso.

## Regla 6 — código de producción: worktree aislado + reviewers hasta PASS

Cuando el Administrator ordena cambios de código de flota, el ciclo verificado es:

1. **Worktree aislado** desde master (`git worktree add worktrees/<slug> -b <rama>`), nunca editar la copia viva. El directorio de scripts de crons está en .gitignore — el worktree es la ÚNICA forma de tener versionamiento del cambio.
2. **Un reviewer independiente por ronda** (subagente distinto del implementer), recibiendo: archivos, historial de hallazgos de rondas previas y qué se arregló. El reviewer NO modifica ni commitea: solo veredicto PASS o CAMBIOS REQUERIDOS con evidencia.
3. **Arreglar y commitar por ronda** (conventional commits); repetir hasta PASS. Un PASS sólido ejecuta los tests y hace SONIDAS ADVERSARIALES sobre los arreglos (¿el nuevo camino tolerante acepta un run viejo no relacionado? ¿queda algún falso verde?), no solo lectura del diff.
4. **Merge a master + verificación de identidad viva**: `md5sum` del archivo en master == worktree. Si el destino no es un repo git (scripts ignorados), verificar identidad por hash igual.
5. **e2e con el job real, no con el script suelto**: disparar el cron que invoca el script (`hermes cron run <id>` → `source=direct completed`) y leer la salida entregada. El rc=0 del script fuera del runner no prueba el wiring.

Regla dura: un fix que amplía tolerancia (ventanas, formatos aceptados) exige como mínimo un test del BORDE que debe seguir rechazándose — la tolerancia sin borde probado es el falso verde de mañana.

## Pitfalls

- **`shutil.copy2` conserva el mtime**: al ordenar respaldos, desempatar por nombre (que lleva el timestamp), no solo por mtime. El centinela ya lo hace.
- **Umbral de tamaño mínimo (2000 B)**: detecta truncamientos que sí parsean (un `model:` suelto es YAML válido).
- **Un config válido puede estar semánticamente roto** (p. ej. `langfuse` en `disabled` y en `enabled` a la vez): `cfgctl` valida forma, no intención. Revisar el diff antes de aplicar.
- **No borrar `config.yaml.bak-*`**: son la red del centinela.
- Si el config ya está roto y el centinela no está instalado, `cfgctl restore <bak válido>` funciona sin depender del parser del runtime, porque es un script externo.
- **Reemplazar un script no es desplegarlo**: al sustituir un script por una versión corregida, grep del nombre en TODOS los invocadores en el mismo cambio — crons, wrappers shell, `/opt/data/profiles/*/AGENTS.md`, `*/SOUL.md` y las skills que citan la ruta. Un invocador viejo sigue ejecutando el bug corregido aunque la versión nueva esté en disco.
- **Un parser YAML casero para un auditor aprueba por profundidad**: al extraer un bloque top-level, fijar la indentación de los hijos directos (la primera clave indentada tras la clave raíz) e ignorar todo lo más profundo — acumular cualquier línea indentada en un mismo dict hace que un `mode:` anidado en un sub-bloque apruebe un config que no declara modo alguno (falso OK que derrota el propósito del audit) y que un anidado posterior SOBREESCRIBA el valor real. Completar el set de falsos verdes del mismo auditor: des-quotear valores e ítems con `strip("\"'")` (aparecen ambas comillas), lista de resultados vacía = error con exit ≠ 0 (`all([])` es True y canta éxito sobre una ruta mal tipeada), y formas no-bloque (`{…}` inline, alias `*ancla`) se reportan como no soportadas, nunca se dan por buenas. Validar el parser contra `yaml.safe_load` sobre los configs REALES además de los fixtures — los fixtures no cubren las formas que la flota usa de verdad.
- **Todo parche por líneas va anclado al bloque contenedor**: un renombre por regex global (`^\s*modelo-x:\s*$`) pega el PRIMER match, que puede ser el bloque de otro proveedor con el mismo id. Anclar la búsqueda al bloque (línea del `provider:` hasta el siguiente key del mismo nivel) y en `--dry-run` imprimir, además del diff, un check estructural antes/después (modelos por proveedor parseados con `yaml.safe_load`) que demuestre que el cambio tocó solo el scope declarado. El dry-run no es decorativo: es el gate que caza el scope equivocado.
