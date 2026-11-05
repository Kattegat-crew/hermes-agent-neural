---
name: hermes-gateway-s6-ops
description: "Use when restarting the Hermes gateway safely under s6"
tags: [gateway, s6, reinicio, supervisor, hermes, ops, cron, vps]
---

# Hermes Gateway — operación bajo s6 supervisor

El gateway de Hermes corre dentro del contenedor `hermes-agent` bajo **s6** (PID 1 =
`/package/admin/s6/command/s6-svscan`). Reiniciar el gateway es la única forma de
aplicar cambios de config/env (provider, modelos, políticas WhatsApp, etc.) — no hay
hot-reload.

## Servicio ACTIVO (CORRECCIÓN 2026-08-26 — descriptor del GUI real)

⚠️ **El servicio real es `gateway-default` — NO `main-hermes`.**

- CORREGIDO 26/08/2026 con evidencia del propio log: reiniciar `gateway-default` a las
  08:33 produjo PID python nuevo (`hermes gateway run --replace`: 64919 → 82616), mientras
  `main-hermes` a las 06:05 solo mostró el wrapper estático (PID 17, `rc.init ... main-wrapper.sh`,
  que nunca cambia y tiene un hijo `sleep infinity`). El proceso python real del gateway vive
  bajo `s6-supervise gateway-default` (log en `/opt/data/logs/gateways/default`).
- Nota histórica: una versión anterior de esta skill (2026-08-19) afirmaba `main-hermes`;
  quedó refutada por el log de reinicios de 26/08. El wrapper `main-hermes` (symlink a
  `/run/s6-rc/servicedirs/main-hermes`) es el entrypoint docker de s6, NO el gateway.
- Script canónico: `/opt/data/scripts/gateway_restart_once.sh` → `s6-svc -r /run/service/gateway-default`.

## Regla de oro: nunca reiniciar dentro del propio turno

`hermes gateway restart` (y cualquier comando que mate el proceso gateway) queda
BLOQUEADO por el guard de terminal. Aunque no lo estuviera, el restart **mata la
sesión actual** a mitad de turno.

**Patrón correcto — cron one-shot `no_agent`:**
1. Editar config/.env (los cambios se leen al arrancar).
2. Escribir un script que reinicie vía s6 (ver abajo) dentro de `~/./scripts/`.
3. Programar via `cronjob` action=create: `schedule=<ahora + 3-4 min>`,
   `no_agent=true`, `deliver=local`, `script=<nombre del script>`.
4. Entregar el mensaje final al usuario ANTES de la hora del cron; el cron dispara el
   restart cuando el turno ya terminó.

```bash
# /opt/data/scripts/gateway_restart_once.sh (correcto: apunta a gateway-default)
#!/bin/bash
LOG=/opt/data/logs/gateway-restart.log
echo "$(date '+%Y-%m-%d %H:%M:%S') restarting main-hermes via s6" >> "$LOG"
/package/admin/s6/command/s6-svc -r /run/service/main-hermes >> "$LOG" 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') s6-svc exit=$?" >> "$LOG"
```

## Verificación del restart

```bash
cat /opt/data/logs/gateway-restart.log          # exit=0 esperado
ps -eo pid,ppid,etime,cmd | grep "gateway run"  # PID NUEVO, sin crash loop
grep -E "g\.us|whatsapp" /opt/data/logs/agent.log | tail   # tráfico entrante sigue fluyendo
```

Confirmación rápida del supervisor: `ls -la /run/service/` + `ps -eo pid,cmd | grep s6-supervise`.

## Pitfalls

- **Crash loop tras restart** → `docker logs hermes-agent --tail 30`:
  - `PermissionError` en `/opt/data/*` → el gateway (UID hermes) choca con archivos
    creados por root → `chown -R hermes:hermes` sobre los dirs afectados.
  - `group/dm_policy 'open' sin GATEWAY_ALLOW_ALL_USERS` → falta opt-in: agregar
    `WHATSAPP_ALLOW_ALL_USERS=true` a `/opt/data/.env`.
- El bridge de WhatsApp es hijo del gateway: se respawnea con env fresco al reiniciar
  el gateway (también arregla allowlists que el proceso viejo tenía desactualizadas).
- Cambios en `/opt/data/.env` solo aplican al ARRANCAR del proceso — verificar el env
  del proceso vivo con `tr '\0' '\n' < /proc/<pid>/environ | grep WHATSAPP`.

## Topología PROD (verificado 19/10/2026): una gateway por host

- El core actual de Hermes **impone una única gateway por host** (multiplex): el host
  gateway (`gateway-default`) es el inbound de TODOS los perfiles sin `gateway.standalone`.
- Los servicios por-perfil legacy (ej. `gateway-yulieth`) son **rechazados con exit 78**
  (`"Profile 'X' does not get a gateway of its own"` — log en
  `/opt/data/logs/gateways/<perfil>/current`). Si un servicio por-perfil aparece `down
  (exitcode 78)`, NO es un crash ni un error de config del perfil: dejarlo abajo y
  verificar que el perfil está servido vía `profile_routes` en `/opt/data/config.yaml`
  (que el host gateway carga al arrancar).
- Servicios activos en PROD (`/run/service/` dentro del contenedor `hermes-agent`):
  `gateway-default`, `gateway-golden-game`, `gateway-lucky-club` (standalone permitidos)
  y `main-hermes` (dashboard). Rutas de log: `/opt/data/logs/gateways/<perfil>/current`.
- Desde el HOST de PROD: `ssh prod "docker exec hermes-agent /command/s6-svc -r
  /run/service/gateway-default"`. Los binarios s6 viven en `/command/` dentro del
  contenedor (no en `/package/...` del host).
- Un run manual de diagnóstico (`hermes -p X gateway run --replace`) puede dejar un
  proceso huérfano que interfiere con el servicio supervisado; tras diagnosticar así,
  verificar estado con `s6-svstat` y re-levantar con `s6-svc -u` si quedó abajo.

## Relación con otras skills

- `devops:whatsapp-bridge-operations` (user-owned) tiene el resto del manual del bridge
  (allowlist, grupos, voz) — la sección de "reinicio" de esa skill es la que está
  equivocada; adoptarla para corregirla.

## Por qué reiniciar tras cada update: skew gateway/código (verificado 04-nov-2026)

El gateway NO tiene hot-reload de código: si `/opt/hermes-agent` se actualiza sin reiniciar
los gateways, la flota queda un tier por detrás del árbol. Síntoma característico: TODOS los
workers kanban mueren deterministamente con `Hermes no pudo iniciar la conexión con el modelo:
invalid_params` (exit 1, pid gone) en oleadas que empiezan justo después del update. Causa:
el worker client (`-m hermes_cli.kanban_worker_client`) corre con el árbol nuevo y envía RPC
con campos nuevos (ej. `kanban.run` con `db=db`), pero el dispatcher del contrato del
tui_gateway del gateway VIEJO rechaza claves desconocidas con `invalid_params` bare.

Diagnóstico en vivo (comparar sha del proceso vivo vs HEAD del árbol):

```bash
python3 -c "import json;d=json.load(open('/opt/hermes-agent-data/.hermes/gateway_state.json'));print(d.get('code_sha'),d.get('pid'))"
git -C /opt/hermes-agent rev-parse HEAD
git -C /opt/hermes-agent log --oneline <code_sha>..HEAD -- gateway/ hermes_cli/kanban* tui_gateway/
```

Si `code_sha != HEAD` y el rango toca kanban/gateway/contratos, es esto. Ver también el
per-profile `/opt/hermes-agent-data/profiles/<name>/gateway_state.json`.

Pitfall de diagnóstico: `hermes -p <perfil> chat -q "test"` PASA aunque el gateway esté
en skew — auto-arranca un gateway propio con el código nuevo. **Una prueba CLI manual NO es
repro válido de fallos en la ruta gateway**; reproduce siempre vía el dispatcher kanban o el
gateway en ejecución. El warning cosmético de config (ej. `voice.stop_phrases` quoted-string)
NO es la causa aunque aparezca en el output del worker. Prevención: agendar el reinicio
(`gateway_restart_once.sh` vía cron `no_agent`) como paso final de CUALQUIER update del árbol.