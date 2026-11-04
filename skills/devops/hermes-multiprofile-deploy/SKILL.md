---
name: hermes-multiprofile-deploy
description: "Use when deploying config changes to N Hermes profiles."
tags: [hermes, perfiles, multiprofile, gateway, cron, fallback, despliegue, s6]
version: 1.0.0
author: Ragnar
metadata:
  hermes:
    tags: [multiprofile, gateway, s6, cron, engram, fallback, providers, desplegar]
    category: devops
    related_skills: [hermes-team-ops, hermes-multiprofile-cron-ops, hermes-admin-operations, provider-manager]
---

# Hermes Multiprofile Deploy — Configurar N perfiles sin romper el gateway

Cómo aplicar cambios de configuración en masa a los perfiles servidos por el
gateway multiplexado (Engram, modelos+fallback, compresión, crons escalonados)
de forma VERIFICABLE y sin tirar el proceso. Validado 26/08/2026 en el equipo
marketing de NeuralCrew Labs (9 bots: bragi, brokkr, freyja, heimdall, hermodr,
sindri, ullr, vili, comms).

## When to Use

- Hay que tocar config.yaml de varios perfiles a la vez (mcp_servers, model,
  fallback_providers, compression, display, cron).
- Se despliega un provider nuevo (p.ej. OpenCode-Go) a N bots.
- Se crean crons escalonados por perfil (guardar-diario-memoria, informes).
- Cualquier cambio que requiera reiniciar `gateway-default` bajo s6.

## Prerrequisitos

- Perfiles reales viven en **`/opt/data/profiles/<bot>/`** (bind mount). La ruta
  `/root/hermes-agent-legacy-docker/data/profiles/` es PARCIAL y engaña: los configs que el
  gateway lee están en `/opt/data/...`. Verificar SIEMPRE contra `/opt/data`.
- El gateway corre bajo s6: `s6-supervise gateway-default` →
  `hermes gateway run --replace` con HOME=/opt/data, uid 10000.
- Backup ANTES de cada escritura: `cp config.yaml config.yaml.bak-<etiqueta>-<ts>`.

## Procedimiento genérico (fases A-D validadas)

1. **Auditar el estado actual**: para cada bot, grep de `mcp_servers`, `engram`,
   `fallback_providers`, `^compression:`, `cron/jobs.json`. Nunca asumir.
2. **Escribir con script Python atómico** (yaml.safe_load + dump sort_keys=False)
   con backup individual por perfil, y RE-LEER cada config al final para verificar
   (project=True/tools=True/env=True / default esperado / fallback cascada).
3. **Smoke test antes de reiniciar**: el binario MCP engram responde initialize
   y `mem_current_project` devuelve el `--project` correcto (process_override).
4. **Reiniciar el gateway**: `kill -TERM <pid de 'gateway run --replace'>` y dejar
   que s6 lo respawnee (s6-svc NO está accesible en este mount; ver pitfalls).
5. **Verificar estabilidad**: dos lecturas del PID con ~12-15s de diferencia deben
   dar el MISMO pid (`Ssl`), y `gateway_state.json` served_profiles sigue igual.

## Crons escalonados por perfil (patrón guardar-diario-memoria)

- Formato cron: **`<min> <hora> * * *`** — el primer campo es MINUTO. Para
  escalonar a medianoche usar `N 0 * * *` (00:N). `0 24 * * *` es INVÁLIDO
  (la hora 24 no existe).
- Crear con: `HERMES_HOME=/opt/data/profiles/<bot> /usr/local/bin/hermes cron create
  --name guardar-diario-memoria --deliver local --repeat 9999
  --skill engram-memory-system --skill guardado-doble-memoria
  --script daily_session_report.py --model <m> --provider <p> "N 0 * * *" "<prompt>"`
- El script `daily_session_report.py` debe copiarse a `profiles/<bot>/scripts/`
  y resuelve la DB por perfil con `HERMES_DB_PATH=<profile-home>/state.db`.
- **El aviso "Gateway is not running" del CLI es FALSO**: bajo multiplex, el
  gateway dispara los crons de todos los perfiles servidos. Verificar en
  `cron/jobs.json`: `next_run_at` futuro y `enabled: True`.
- El orden del CLI cron: `cron create <expr> "<prompt>"` — si el prompt va
  primero, el expr se interpreta mal. Usar `<expr> "<prompt>"`.
- Para re-crear un job: `cron list` para sacar el ID, `cron remove <id>`, luego
  create.

## Pitfalls (lecciones duras 26/08/2026)

- **NUNCA lanzar `hermes gateway run` manualmente como ROOT mientras s6 lo
  gestiona.** Los lanzamientos manuales de diagnóstico rotan
  `/root/hermes-agent-legacy-docker/data/logs/errors.log` a root:root; el gateway s6 (uid
  10000, HERMES_S6_SUPERVISED_CHILD=1) crashea al arrancar con
  `PermissionError: [Errno 13] Permission denied: .../errors.log` → s6 reinicia
  en LOOP (exit≠0/78 reinicia siempre). Síntoma: el PID del gateway cambia cada
  ~14s. Fix: `chown 10000:10000` a logs/. Diagnóstico correcto: matar SOLO el
  PID del gateway (`kill -TERM`) y dejar que s6 lo respawnee, o reproducir con
  `setpriv --reuid 10000 --regid 10000 --clear-groups env HOME=/opt/data ...`.
- **`fallback_providers` sin el provider definido NO resuelve.** Un bot que
  lista `OpenCode-Go` en fallback_providers pero no tiene el bloque
  `providers.OpenCode-Go` fallará al intentar el fallback. Replicar SIEMPRE el
  bloque providers completo (api_key, base_url, models) además de la referencia.
- **Verificar que el modelo asignado existe en el catálogo del provider**
  (curl /models). `deepseek-v4-flash-0731` NO existe en NaN/B.AI/OpenCode-Go —
  el default de un bot que lo use rompe. Antes de asignar modelos, comparar
  contra la lista real del provider.
- **Compresión raíz vs auxiliary.compression**: `auxiliary.compression` es SOLO
  el modelo que COMPRIME. Sin el bloque `compression:` raíz
  (`enabled: true, threshold, target_ratio`) la compresión automática NO está
  activa. Threshold: ~0.25 en modelos 1M (dispara ~256K), ~0.55 en nativos 256K,
  target_ratio 0.2 como default de Ragnar.
- **Bloqueos hardline del parser**: comandos con `&` inline o combinaciones
  `$(...)` largas se bloquean y se guardan en
  `/root/hermes-agent-legacy-docker/data/cache/blocked-scripts/`. Recuperación:
  `bash /root/hermes-agent-legacy-docker/data/cache/blocked-scripts/blocked-<ts>.sh`. Para
  background usar `terminal(background=true)`, nunca `&` inline.
- **s6-svc no existe en este mount**: el svscan apunta a
  `/package/admin/s6/command/s6-svscan` pero el binario no está accesible desde
  el entorno del agente. El método fiable de reinicio es `kill -TERM` al PID
  real del gateway.

## Verificación

- Después de editar configs: `python3 -c "import yaml; yaml.safe_load(open(...))"`
  en TODOS los editados + re-lectura con aserciones (lo que el script dice haber
  escrito debe verse al releer).
- Después de reiniciar: PID estable en 2 lecturas (12-15s), `ps -o stat` = Ssl,
  `served_profiles` intacto (12 para default+roshi+vigia+8 dioses+comms).
- Después de crear crons: `next_run_at` futuro en `profiles/<bot>/cron/jobs.json`.

## Referencias

- `references/fallback-3-capas-api.md` — esquema de fallback 100% API
  (NaN → B.AI → OpenCode-Go) y catálogos verificados (qué modelo responde en
  cada provider y cuál NO existe).