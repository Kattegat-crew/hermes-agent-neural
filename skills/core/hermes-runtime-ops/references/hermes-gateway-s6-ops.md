---
name: hermes-gateway-s6-ops
description: "Reinicio seguro del gateway de Hermes bajo s6 en el VPS."
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
# /opt/data/scripts/gateway_restart_once.sh (correcto: apunta a main-hermes)
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

## Relación con otras skills

- `devops:whatsapp-bridge-operations` (user-owned) tiene el resto del manual del bridge
  (allowlist, grupos, voz) — la sección de "reinicio" de esa skill es la que está
  equivocada; adoptarla para corregirla.

## Reload de MCP por perfil (16-sep-2026)

Hay **un servicio s6 por perfil** (`gateway-default`, `gateway-roshi`, `gateway-vigia`, …).
Estado normal del fleet: solo `default`, `roshi` y `vigia` corren; el resto queda
`down (not started yet)` por diseño (sus configs se aplican al arrancar).

Para aplicar cambios de `mcp_servers` de un perfil:
1. `docker exec hermes-agent /package/admin/s6/command/s6-svc -r /run/service/gateway-<perfil>`
   (para levantar uno que está down: `-u`).
2. Esperar 45–60 s y verificar PID nuevo: `s6-svstat /run/service/gateway-<perfil>`.
3. Evidencia MCP viva: `ps` → proxies stdio hijos del PID nuevo;
   `HERMES_HOME=/opt/data[-profiles/<p>] hermes mcp list`.
4. Bridge WhatsApp (default): `curl -s http://127.0.0.1:3000/health` dentro del contenedor
   → `connected` + `Allowed users` en bridge.log.
