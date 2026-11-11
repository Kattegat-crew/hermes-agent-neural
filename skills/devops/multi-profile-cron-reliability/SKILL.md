---
name: multi-profile-cron-reliability
description: "Use when a profile cron fails with drift_skip or symlinks."
tags: [cron, hermes, perfiles, drift-skip, symlinks, fallback, watchdog, fiabilidad]
version: 1.0.0
author: Roshi
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [cron, hermes, profiles, drift-skip, symlinks, fallback]
    related_skills: [hermes-gateway-ops, provider-manager, guardado-doble-memoria]
---

# Multi-Profile Cron Reliability

Diagnoses and hardens recurring Hermes cron jobs across profiles. Covers the two most
common silent-failure modes observed in production (a cron that SHOULD run but doesn't):
unpinned jobs skipped by `drift_skip`, and broken skill-catalog symlinks that make the
job's `skills:` fail to load. Also captures the anti-rate-limit / fallback pattern for
fleet-wide cron matrices.

## When to Use
- A profile cron shows `last_status: error` or `failure_streak > 0` with a confusing `last_error`.
- A cron output says `Skill(s) not found and skipped: <names>`.
- Provisioning/reviewing crons for several profiles at once (e.g. a marketing bot fleet).
- Reading a cron-scheduler health check (Vigía-style watchdog).

## Prerequisites
- Read access to `<profile_home>/cron/jobs.json` and `<profile_home>/cron/output/<jobid>/*.md`.
- `hermes --profile <name> cron edit ...` for pinning.
- Only consider the cron's actual run output — `jobs.json` `last_error` is not always the true cause.

## How to Run
1. Load the failing job: read `cron/jobs.json`, note `last_status`, `failure_streak`, `last_error`, `script`, `skills`.
2. Trigger a manual run (`cronjob action=run`) and read the emitted `<timestamp>.md` in `cron/output/<jobid>/`.
   - The real error frequently lives ONLY in that output file (or in `errors.log`), not in `jobs.json`.
3. Apply the matching fix below, then re-run and confirm `last_status: ok`.

## Quick Reference

### Pitfall A — `drift_skip` masks itself as a permission error
Symptom: `last_error` shows `Permission denied ... .output_*.tmp` **or** a generic
`RuntimeError: [drift_skip]`. Real cause: the job is **unpinned** and the global
inference config drifted (e.g. provider `nan-builders` → `custom`), so Hermes skips
the job to prevent unintended spend. UID/ownership checks often pass (both users can
write) — don't chase permissions first.

Fix (pin the job explicitly):
```
hermes --profile <name> cron edit <jobid> --provider "NaN-Builders" --model <model>
```
Any cron created without an explicit `--provider/--model` is unpinned → pin ALL fleet
crons at creation, not just on failure.

### Pitfall B — Broken skill-catalog symlinks
Symptom: cron output: `Skill(s) not found and skipped: <names>`. Cause: the profile's
`<home>/skills/` is full of symlinks pointing at `/opt/data/skills/<name>` — a path
that **does not exist**. The canonical catalog is `/root/hermes-agent-legacy-docker/data/skills/`
(+ `/root/hermes-agent-legacy-docker/data/skills-especialistas/`). Nested skills under a category dir
(e.g. `engram-memory-system/guardado-doble-memoria`) need their own **top-level**
symlink, because the cron skill loader resolves by flat name.

Fix: run `scripts/repuntar-skills.py` (idempotent re-point of broken links), then
verify: `for l in skills/*; do [ -L "$l" ] && [ -e "$l" ] || echo "ROTO $l"; done`.
Also confirm each listed cron skill has a resolvable top-level SKILL.md.

### Pitfall C — el paso del agente falla pero el SCRIPT ya hizo su trabajo
Symptom: el `<timestamp>.md` de la corrida contiene `Error: Refusing non-interactive
startup because <home>/config.yaml is invalid: [Errno 13] Permission denied` (el runner
del agente no pudo arrancar), mientras `jobs.json` reporta `last_status: ok`.
Clave: un job con `script` **primero ejecuta el script** y después le pasa la salida al
agente para redactar el mensaje. Si el script publicó/registró/generó, el trabajo YA está
hecho: lo que falló fue el formateo de la notificación. **No** reportar eso como servicio
caído antes de revisar el efecto real (la fila/elemento quedó marcado, el commit existe,
el archivo está en disco).
Cuántas veces pasó: `executions.db` (tablas `executions` y `cron_incidents`) da el conteo
por `job_id` y estado (`completed` / `failed` / `unknown`) — con eso se distingue un fallo
sistemático de un caso aislado.
Un `.md` de **0 bytes** es la corrida silenciosa normal de un job que no tenía nada que
reportar (no es un fallo); el silencio es el comportamiento esperado de los publicadores.

### Pitfall D — el publicador falló y `last_status: ok` lo tapó
Symptom: `jobs.json` con `last_status: ok` en un job `no_agent: true` (script .sh) mientras el
`.md` de la corrida termina en `… post:401` o `post:-32001`. El wrapper imprimía el error del
post pero salía 0 (el post no era el último comando / no se comprobaba `$?`), así que el
scheduler marcó verde.
Detección: leer el `cron/output/<jobid>/*.md` más reciente y grepear `post:`; agregar por
resultado (`sort | uniq -c`) para separar fallo sistemático de caso aislado.
Regla: `ncl-discord post` (o el curl) debe ser el ÚLTIMO comando del script y su exit code el
del script; probarlo con un canal inválido y exigir `rc≠0`. Para saber si el canal sirve en el
contexto del scheduler (otro uid/env que tu sesión), usar la sonda `env -i` de
`notification-delivery-reliability`.

### Pitfall E — publicador sin `?thread_id=` genera un hilo nuevo por corrida (explosión de hilos)
Symptom: un canal-foro de Discord se llena de hilos duplicados que nacen solos
(`Informe de Vigia 02-nov`, `Latido flota Hermes`, `vigia-auditoria-2100`, …), con 0–1
mensaje cada uno. Causa: jobs cuya publicación usa `curl $WH` (webhook Discord) **sin
`?thread_id=<fijo>`** en la URL → cada corrida crea un hilo nuevo. No es un fallo del
webhook: es la URL sin ancla.
Detección: grep `thread_id` en el `jobs.json` de cada publicador (los hay con y sin);
en DEV (03/11) eran 3: `hermes-maintenance-night` (30 3), `vigia-informe-0800` (0 8),
`vigia-auditoria-2100` (0 21), todos en perfil vigia. Parchear SOLO uno deja la
explosión activa por los otros — cubrir TODOS los publicadores.
Fix: fijar `?thread_id=` en la URL del curl de cada job. Antes de cualquier limpieza
masiva (script con `--apply`), snapshot reversible:
```
D=/opt/data/cache/<tema>/backup-$(date -u +%Y%m%d-%H%M%S); mkdir -p $D
cp /opt/data/cron/jobs.json $D/jobs-default.json
for p in /opt/data/profiles/*/cron/jobs.json; do cp $p $D/jobs-$(basename $(dirname $(dirname $p))).json; done
```
Y en Discord, antes de borrar hilos "vacíos", verificar contra la API real (token en
`/opt/data/.env`): un hilo "de 1 mensaje" puede contener una ficha de tarea valiosa; si
son duplicados exactos, archivar el contenido a disco con sha256 antes de borrar.

### Cobertura — cada perfil tiene SU `jobs.json`
`/opt/data/cron/jobs.json` lista solo los jobs del perfil `default`. Un job que vive en
`/opt/hermes-agent-data/profiles/<perfil>/cron/jobs.json` (ej. vigía) es invisible para
cualquier auditoría que lea solo la ruta raíz: recorrer `profiles/*/cron/jobs.json` siempre.
Ese job tampoco ve `/etc/cron.d`: un `cron.d` + un job Hermes para la misma tarea = dos
barridos y dos posts el mismo día (caso real: 08:30 root + 09:00 Hermes, lunes).

## Procedure (full diagnostic)
1. `ps` to confirm which process serves the profile: multiplexed gateway vs
   `hermes --profile X serve --isolated`. This influences who the cron runner is — but
   treat ownership as a hypothesis, not a conclusion; `drift_skip` is the common true cause.
2. Read the latest job output md in `cron/output/<jobid>/` top-to-bottom — check for
   "drift_skip" and "Skill(s) not found" lines specifically.
3. If skills missing → repoint links (Pitfall B) and add top-level symlinks for nested skills.
4. If drift_skip → pin (Pitfall A).
5. Re-run, verify `last_status: ok` and no "not found" warning in the new output.
6. Report the REAL root cause to the team — a wrong diagnosis (perms vs drift) wastes
   a whole work cycle.

## Anti-rate-limit / fallback pattern (fleet matrices)
- Do NOT point several concurrent bots/crons at the same primary model — one API key
  usually equals one concurrency bucket (real cluster failure: `429 max 5 simultaneous`).
- Give each bot a distinct primary model, and **stagger** cron times (6-min grid) so the
  nightly burst doesn't stack requests.
- Fallback cascade (all HTTP, no CLI): primary provider → a free-tier API fallback
  (e.g. B.AI `deepseek-v4-flash`) → an execution fallback (e.g. OpenCode-Go `mimo-v2.5`).
  Configure via `fallback_providers:` in each profile config; verify by reading config back.

## Pitfalls
- Never claim "fixed" from `chmod`/`chown` alone — the permission error can be a red
  herring for `drift_skip`. Prove it with a manual run that goes green.
- Have a human run interactive `opencode auth login`; the CLI fallback wrapper never
  manages credentials itself — it should just detect presence and write machine-readable
  `estado.json` for a watchdog.
- Verify the cascade by re-reading each profile config; don't trust "remember it was set".

## Verification
- The job's `next_run_at` is still scheduled AND a manual `action=run` returns `ok`.
- `grep -c drift_skip` in the run output == 0; no "Skill(s) not found" warning.
- `repuntar-skills.py` reports 0 remaining broken links.

## Linked files
- `scripts/repuntar-skills.py` — idempotent repoint of `/opt/data/skills/*` symlinks to the canonical catalog.
- `references/drift-skip-y-symlinks.md` — live diagnostic transcript from prod (26/08).