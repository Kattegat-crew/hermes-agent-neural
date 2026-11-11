---
name: orca-fleet-delegate
description: Use when delegating parallel work to agent engines (codex, agy, opencode) on DEV with isolated git worktrees, SDD/adhoc modes, and unified logs.
---

# orca-fleet-delegate — Delegación canónica paralela a motores de agente

Lanza trabajo paralelo a motores externos de agente en DEV con un solo comando, con aislamiento por worktree, modo de trabajo explícito (SDD/adhoc), logging unificado y registro JSONL.

## Script canónico

`/opt/data/fleet/fleet-run` (v1.1.0, chmod +x).

## Motores y carriles (resueltos, no improvisar)

- **codex** → SIEMPRE vía `ssh root@127.0.0.1` (BatchMode, key auth ya configurada). Binario: `/root/.local/bin/codex`. Modelo default `gpt-6.1-sol`, effort `high` (override: `--model`, `--effort`, o env `FLEET_CODEX_MODEL`/`FLEET_CODEX_EFFORT`). Flags obligatorias: `--dangerously-bypass-approvals-and-sandbox --skip-git-repo-check`. Lanzar con `nohup setsid` para que sobreviva al SSH.
- **agy** (Antigravity CLI) → local `/usr/local/bin/agy`. Auth vive en `/opt/data/.gemini/antigravity-cli/antigravity-oauth-token`. CRÍTICO: dos instancias con el mismo HOME se matan entre sí — el script clona un HOME aislado por job (`/opt/data/fleet/agy-home-<job>`). Modelo default `gemini-3.8-flash-high`.
- **opencode** → local `/usr/local/bin/opencode run`.
- **hermes subagent** → NO va por fleet-run: se delega con la tool `delegate_task` de Hermes directamente.

## Reglas de aislamiento

- `--repo <ruta>` (tarea de código): preflight obligatorio `git status` + `git pull --ff-only` (reportar dirty state), luego `git worktree add -b fleet/<engine>-<tarea>` en `/opt/data/fleet/worktrees/<repo>/...`. NUNCA trabajar sobre el working tree del repo vivo; NUNCA clonar en /opt/data (los worktrees son ramas reales del repo, no clones desechables).
- `--dir <ruta>` (tarea de medios/misc): trabajar directo en ese dir.
- Sin `--repo` ni `--dir`: sandbox automático `/opt/data/fleet/sandboxes/<job>/`.

## Modos de trabajo

- `--mode sdd`: el prompt inyecta el protocolo completo — leer AGENTS.md/.agents/rules/PROJECT_MEMORY.md antes de editar, spec → diseño técnico con rollback → tareas atómicas → TDD (RED→GREEN) → verificación, Conventional Commits, PROHIBIDO push sin aprobación humana, PROHIBIDO atribución IA en commits.
- `--mode adhoc` (default): inspección previa + verificación de resultado, sin ceremonia.
- En ambos: sin APIs pagas, sin subidas a internet sin autorización.

## Comandos

```
fleet-run run --engine codex --repo /opt/mi-repo --mode sdd --task "..."
fleet-run run --engine agy --dir /tmp/media --model gemini-3.8-flash-high --task "..."
fleet-run status [JOB_ID]      # RUNNING / RUNNING(root) / FINISHED
fleet-run tail JOB_ID [N]
fleet-run list-worktrees
```

Registro: `/opt/data/fleet/registry.jsonl` · Logs: `/opt/data/fleet/logs/<job>.log`

## Observación en Orca IDE

Orca IDE (v1.4.205) corre como servicio del usuario `orca` en `http://100.86.8.81:6768` (Tailscale DEV) — tablero visual de sesiones de agentes. fleet-run es la vía headless; Orca es el tablero.

## Supervisión de fases SDD con motores flash (lección 23-oct, Pixel/CAPI Golden+Lucky)

- Un motor flash-class (gemini-3.8-flash-high) NO sirve para diseño técnico complejo supervisado por fases: re-introduce los mismos patrones rechazados en cada ronda (confiar en headers de proxy no verificados, cookies con atributos inválidos, queries de cola sin locks/attempts/consent) pese a correcciones específicas. Cap duro: máx 2 rondas de revisión por fase; si vuelve a fallar, el orquestador corrige los puntos complejos directamente (invariantes vinculantes exactos en el prompt) y solo delega al flash tareas pequeñas, acotadas y verificables.
- Antes de proponer subir de modelo (p.ej. Argon), verificar costo/disponibilidad con el Admin: en esta sesión Argon estaba agotado y se optó por corrección directa del orquestador.
- Prompts largos multi-línea para `agy -p`: NO pasarlos como argumento shell directo (error de quoting → exit 2 sin ejecutar). Patrón confiable en un solo comando: `python3 -c 'import os; p="""..."""; os.execvp("agy",["agy","--continue","--model","gemini-3.8-flash-high","--effort","high","--mode","plan","--print-timeout","15m","--add-dir","/opt/repo","-p",p])'` lanzado con `background=true, notify=true`. `--continue` mantiene el contexto de sesión entre rondas de revisión.
- Toda entrega del motor termina con marcador explícito (`STOP_FOR_RAGNAR_REVIEW FASE_N`) y la aprobación de fase es SIEMPRE del orquestador: verificar contra el código real (paths/líneas, git status, HEAD) antes de autorizar la siguiente fase; nunca aceptar auto-aprobación del motor.

## Verificación de regresión sin suite completa (paridad base↔parche, lección 25-oct)

- El `.venv` del repo suele ser inutilizable (deps opcionales ausentes, jiter corrupto en 3.14, permisos no escribibles por hermes): montar un venv propio de flota — `UV_PROJECT_ENVIRONMENT=/opt/data/fleet/venvs/<nombre> uv sync --frozen --no-install-project --link-mode=copy` (el hardlink falla entre filesystems) — y añadir pytest si falta (`uv pip install pytest`). Con ese venv mínimo la suite masiva falla en masa por ambiente (miles de fallos de integración/wire) — eso NO es regresión.
- Método de paridad para demostrar cero regresión: (1) extraer la lista exacta de fallos del cache de pytest (`.pytest_cache/v/cache/lastfailed`), clasificar causas y aislar los tests del área tocada; (2) correr ese subconjunto en el árbol parcheado y en el árbol base (repo vivo, HEAD sin parche) con el MISMO venv; (3) exigir conjuntos de fallos idénticos byte a byte. Documentar los fallos pre-existentes ambientales como tales.
- Lista de tests reutilizable entre ejecuciones: volcar los test-ids a un archivo y pasarlo a pytest con argfile (`pytest @/tmp/tests.txt`) — evita comandos kilométricos.
- Cambios transversales (puntos únicos de salida, flags de scaffolding) deben cubrir sus listas hermanas: si se agrega un flag efímero a `session_persistence`, verificar la lista gemela en `conversation_compression` (compaction) con test que afirme pertenencia en ambas.

## Delegación a Bob vía buzón (PROD) — agent_exchange.py

Cuando la delegación es a Bob (agente de PROD), el canal NO es fleet-run sino el buzón de archivos `/opt/data/inbox/` operado por `/opt/data/scripts/agent_exchange.py` (solo stdlib, escrituras atómicas, nunca escribe fuera de `/opt/data/inbox/`).

- **agente → Bob:** `/opt/data/inbox/<agente>/pending/ticket-*.json`, reclamado por el cron `escalation-watcher` cada ~5 min. Agentes válidos: `ragnar`, `rochi`, `bob`. `--deliver` válidos: `/opt/data/`, `whatsapp:`, `bot-chat:`, `telegram:`.
- **Bob → agente:** respuesta en `{done,failed}/<ticket>.json`; mensajes libres en `from-bob/msg-*.json`. Log del watcher: `/opt/data/inbox/watcher.log` (líneas `CLAIMED ragnar/ticket-...`).
- **Webhook best-effort:** cada depósito dispara POST firmado (HMAC-SHA256) a `http://100.86.8.81:8644/webhooks/buzon-bob` (gateway DEV); `send`→`buzon.nuevo`, `reply`→`buzon.respuesta`, `notify`→`buzon.mensaje`. HTTP 202 = notificación aceptada, NO garantiza claim.
- **Tareas largas:** NO pasar `--tarea` multi-párrafo como argumento shell (quoting frágil). Patrón probado: escribir el texto en scratch local → `scp` a `prod:/tmp/tarea-<n>.md` → `ssh prod 'python3 /opt/data/scripts/agent_exchange.py send ... --tarea "$(cat /tmp/tarea-<n>.md)"'`.
- **Loop de verificación (cierre de turno):** (1) leer el JSON en `pending/` y comprobar `id`, `estado=pending` y `tarea` íntegra (len + primeros/últimos chars); (2) esperar el ciclo del watcher con `sleep` en foreground (~240 s, nunca en background) y confirmar `CLAIMED` en `watcher.log` (el ticket pasa a `processing/`); (3) la respuesta aterriza en `done/` y por webhook. Solo reportar "enviado" tras (1) y (2).
- **Pitfalls:** los tickets depositados por root quedan `root:root` en directorios `10000:10000` — el watcher los reclama igual, no "arreglar" permisos. `pending/` se vacía en masa cada ciclo: revisar `watcher.log` antes de concluir fallo. Numeración de tickets independiente por emisor: referenciar siempre el `ticket_id` completo.
- **Verificar el artefacto ajeno, no el acuse:** al acusar recibo de trabajo de otro agente, comprobar el artefacto vivo (código, `sha256sum`, tamaño, mtime) y no solo su acuse. Caso real (03-nov): el registro `fase0_limpieza-sha-final-*.json` quedó stale 3 minutos después de creado (el script se parcheó después y el hash registrado ya no existía en disco) — señalar el drift antes de que se apruebe un artefacto inexistente.

## Lecciones aprendidas

- **Codex puede colgarse en silencio (verificado 25-oct, job DSML-GUARD)**: un job de codex puede quedar atrapado en su modo "collab" y morir sin producir NADA — `.fleet-final.md` inexistente, log reducido al `PID=...`, sin commits ni archivos en el worktree, sin error fatal visible. Regla: al terminar un job de codex, verificar el ENTREGABLE contra el disco (worktree existe, `git log` del worktree, archivos de tests/código esperados) antes de reportar avance; la ausencia de error NO es éxito. No reintentar a ciegas (riesgo de otras 2 h con el mismo fallo opaco): máx 2 rondas y luego el orquestador implementa directamente en el worktree del job (que ya existe y sirve). El `.fleet-task.txt` del job guarda el prompt; sesiones en `/tmp` muestran hasta dónde llegó codex.
- Causa real de muertes "colgadas" de codex (25-oct): codex detecta escrituras concurrentes en el worktree — si el orquestador empieza a implementar por su cuenta mientras el job está activo, codex se detiene por protocolo preguntando si adopta esos archivos y el job muere sin `.fleet-final.md`. Nunca escribir en el worktree de un job codex en marcha; decidir de una (esperar o matar) y luego actuar.
- Revisión fría del entregable: tras commit del motor u orquestador, despachar un subagente independiente (`delegate_task`) que revise el diff completo con severidades y test nuevo por hallazgo; integrar los hallazgos altos con tests GREEN y un commit `fix(...)` adicional. Funcionó: 3 hallazgos altos legítimos (durable-row sync, flags efímeros, ejecución de bloques truncados) detectados así.
- El usuario `hermes` NO tiene sudo ni docker: toda operación root va por SSH key `root@127.0.0.1`.
- `models_cache.json` de codex (644) revela el catálogo de modelos sin auth; auth.json es 0600 root.
- El modelo "sol 6.1" del Admin = slug `gpt-6.1-sol` (GPT-6.1-Sol) en codex; "Gemini 3.8 flash high" = `gemini-3.8-flash-high` en agy.
- ssh con comando en background: el cliente SSH local puede colgar hasta timeout aunque el remote ya esté en marcha — el `LAUNCHED_PID` se imprime antes y `setsid` garantiza supervivencia; verificar con `ssh root@127.0.0.1 ps -p <pid>`.
