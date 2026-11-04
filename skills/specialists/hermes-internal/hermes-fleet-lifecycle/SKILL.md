---
name: hermes-fleet-lifecycle
description: "Use when profile gateways die after a container recreate."
tags: [hermes, fleet, gateway, multiplex, standalone, recovery]
version: 1.0.0
author: Ragnar
triggers:
  - roshi se cayó / gateway caído / bots muertos / se desconectó / no responde
  - todos los gateways / auto-arranque / fleet / multiplex vs standalone
  - recreate del contenedor / sync-upstream / sync nocturno / docker compose up
  - exitcode 78 / exit 78 / GATEWAY_FATAL_CONFIG / guard del multiplex
  - api_server port-binding / Skipping secondary profile / SecondaryPortBindingConfigError
metadata:
  hermes:
    tags: [hermes, fleet, multiplex, standalone, lifecycle, watchdog]
    related_skills: [hermes-admin-operations, hermes-s6-container-supervision]
---

# Hermes Fleet Lifecycle — recuperación y diagnóstico de gateways de perfil

Clase de conocimiento: qué pasa cuando un contenedor Hermes se recrea, por qué los gateways de perfil mueren, cómo recuperarlos, y qué no funciona aunque parezca obvio. No cubre configuración de providers (ver `hermes-admin-operations`) ni modificación de servicios s6 (ver `hermes-s6-container-supervision`).

## Disparadores

- «Roshi se cayó», «bots muertos», «se desconectó», «no responde en Discord».
- «todos los gateways deben arrancar solos», «auto-arranque del fleet».
- «el sync nocturno rompió algo», «docker compose up destruyó los bots».
- Exit 78, SecondaryPortBindingConfigError, skip de perfil secundario.

## Triaje: qué mirar primero

## Triaje: qué mirar primero

**LEY 0 (corrección del CTO, 03/09): el diagnóstico de topología de flota se hace contra el REPOSITORIO VIVO, nunca contra memoria ni contra el estado del multiplexor.** Un perfil puede tener un gateway STANDALONE activo que el log del default NO muestra. Fuentes que hay que abrir ANTES de afirmar "el perfil X lo sirve el multiplexor / su slot está down a propósito":

```bash
# 1) ¿standalone vivo? su log propio (el multiplex no escribe ahí):
tail -5 /opt/data/profiles/<p>/logs/gateway.log    # mtime reciente + "Connected as <Bot>#" = standalone ACTIVO
# 2) ¿quién sirvió el tráfico reciente del usuario? buscar el chat_id del bot en ambos logs:
grep -c "<chat_id>" /opt/data/logs/gateway.log      # 0 ⇒ el default NUNCA ve ese tráfico → es standalone
# 3) el flag down del slot NO prueba intención humana — el init lo REGENERa en cada recreate:
stat -c '%y %n' /run/service/gateway-<p>/down       # mtime == hora del recreate ⇒ artefacto del init, no decisión
grep "API_SERVER\|BOT_TOKEN" /opt/data/profiles/<p>/.env  # tokens propios = perfil APTO para standalone
```

Caso real 03/09: se planificó "quitar API_SERVER_KEY del .env" asumiendo topología todo-multiplex (memoria + s6-svstat), y existía un standalone de Roshi que atendió los DMs del usuario toda la mañana. El fix propuesto habría destruido la arquitectura que el equipo acababa de montar. Ver `references/2026-09-03-roshi-standalone-blindspot.md`.

**Doble conexión = contención**: standalone + multiplexor sirviendo el MISMO bot token a la vez → Telegram polling 409 entrelazado y caídas que "se arreglan solas". Si existen ambos, hay que excluir el perfil del multiplexor (profile_routes) o matar el standalone — decisión del equipo, no del técnico de guardia.

Cuando un usuario reporta un gateway caído:

0. **¿Proceso up pero perfil saltado?** `grep "Skipping secondary profile" /opt/data/logs/gateway.log | tail` — si aparece, el gateway default está sano y el perfil está excluido por config (ver RC3). Causa más común de "X se cayó" en flotas multiplex.
1. **¿Fue recreate del contenedor?** `docker inspect hermes-agent --format 'RestartCount={{.RestartCount}} Created={{.Created}} Started={{.State.StartedAt}}'`: RestartCount=0 + Created≠Started = recreado desde fuera (deploy/manual), no caída. `Received SIGTERM` bajo `s6-supervise gateway-default` en el log = restart INTENCIONAL externo (Desktop/SSH). Si hay recreaciones: `docker events --since '24h' --filter container=hermes-agent --filter event=create`.
2. **¿Qué dice el reconciler?** `tail -n 15 /opt/data/logs/container-boot.log`. La columna `action=registered` (no `started`) para perfiles nombrados = el reconciler los dejó DOWN.
3. **¿Qué exit code tiene el slot?** `s6-svstat /run/service/gateway-<name>`.
4. **¿El gateway intentó arrancar?** `tail -n 20 profiles/<name>/logs/gateway.log`. Si no hay nada después del recreate, el slot nunca arrancó.

## Root causes (con solución)

### RC1: Container recreate + multiplex_profiles = profiles DOWN

**Mecanismo**: el reconciler (`container_boot.py:207`) ejecuta `should_start = not multiplex_profiles and prior_state in {"running"}`. Con `gateway.multiplex_profiles: true` (el estándar), esto es SIEMPRE False para perfiles nombrados → se registra el slot con archivo `down`.

**Fuentes de recreate**: manual (`docker compose up -d`), nocturno (`/etc/cron.d/hermes-sync` ejecuta `sync-upstream.sh` a las 02:00), o `systemctl restart hermes-serve`.

**Solución aplicada (03/09, orden CTO — la válida hoy)**: `desired_state: "running"` en `profiles/<p>/gateway_state.json` → `container_boot.py` levanta ese slot en cada arranque/recreate SIN inyectar flag `down` (probado con `docker restart hermes-agent`: default+roshi arrancaron solos). Perfiles que NO deben tener proceso: mantener desired_state distinto/ausente (flag down del init es correcto ahí).

**Alternativa (si desired_state no existiera en tu versión)**: hook cont-init.d montado via compose (sobrevive recreates). Ejemplo: `./data/hooks/03-autostart-fleet.sh:/etc/cont-init.d/03-autostart-fleet.sh:ro`.

### RC2: Guard del multiplex bloquea standalone (exit 78)

**Mecanismo**: en v0.21+, cuando `multiplex_profiles: true` y el multiplex SÍ sirve un perfil (no está skipeado), intentar `hermes -p <profile> gateway run` muere con exit 78 (`_guard_multiplex_conflict`). El finish script lo traduce a 125 (permanent failure, no restart).

**Trigger no-obvio**: si desactivas `API_SERVER_ENABLED` en el `.env` de un perfil, el multiplex deja de skipearlo → lo sirve → el guard se activa → standalone muere. El fix paradójico: el perfil DEBE mantener habilitado `api_server` para que el multiplex lo skipee, permitiendo standalone.

**Alternativa**: pasar `--force` al run script del slot s6. No recomendado upstream; funciona si el perfil tiene tokens propios (sin double-bind).

### RC3: Perfil saltado por api_server — la defensa real es el PIN en config.yaml

**Mecanismo verificado en vivo (v0.21, 03/09)**: si hay `API_SERVER_KEY` utilizable en el
entorno del proceso gateway, el perfil secundario **enciende api_server AUNQUE su `.env`
diga `API_SERVER_ENABLED=false`** (la key presente gana — `gateway/config.py`). Un secundario
que bindea puerto es ilegal en multiplex → `SecondaryPortBindingConfigError` →
`Skipping secondary profile '<p>' due to port-binding config error: enables api_server`.
El perfil pierde TODAS sus plataformas (Telegram, Discord, rutas WhatsApp) de forma
SILENCIOSA: el proceso gateway sigue up y verde.

**La ÚNICA defensa efectiva** es el pin explícito en el **config.yaml del perfil** (no el .env):

```yaml
platforms:
  api_server:
    enabled: false
```

**Pitfall de regresión (causa raíz real de "Roshi se cae" 03/09)**: un re-salvado del
config.yaml vía Desktop/dashboard (rotar modelo, etc.) re-dumpea el YAML y **BORRA el pin**
→ el siguiente restart del gateway tira el perfil. Síntoma engañoso: el perfil funciona
tras el fix y cae solo en el NEXT restart, horas o días después. Protocolo: tras
CUALQUIER reescritura del config.yaml de un secundario,
`grep -A3 api_server profiles/<p>/config.yaml` para confirmar el pin. Fix idempotente con
backup + readback: `scripts/fix_api_pin.py`. Surte efecto en el próximo restart del gateway
default (ventana corta; programar como cron one-shot, no dentro del turno).

**Nota RC2**: el fix paradójico de mantener api_server encendido aplica SOLO a perfiles que
corren STANDALONE (_guard_multiplex_conflict). Para perfiles servidos por el multiplex (el
caso Roshi), el pin `enabled: false` es lo correcto — no hay conflicto.

### RC3b: El watchdog no distingue modo — necesita manifiesto de topología

Hoy el watchdog (`gateway-fleet-health.sh` + cron vigia-fleet-gateways) asume una topología única (todo-multiplex: solo revive `default`, verifica secundarios vía `served_profiles`). Si el equipo migra perfiles a standalone, el watchdog queda ciego a ellos (y viceversa: reavivar un slot que el multiplex excluye a propósito = loop de exit 78 + falsas alertas). Diseño acordado pendiente de implementación (03/09): manifiesto por perfil, p.ej. `/opt/data/gateway/fleet-mode.json` → `{roshi: standalone, comms: multiplex, ...}`; el watchdog verifica según modo: standalone = `s6-svstat` up + heartbeat `Connected as` en SU log; multiplex = presencia en `served_profiles` + `connected (profile: X)` sin `Skipping`. Alertar solo si la remediación falla (silencio = curado).

**Estado 03/09 15:00**: `gateway-fleet-health.sh` actualizado a topología híbrida → `ALWAYS_UP="default roshi"` (standalone-hermanos, orden CTO), revive con verificación de respawn post-`s6-svc -u`, heartbeat de log por gateway del set, y plataformas discord+telegram tras el último arranque del default. El manifiesto `fleet-mode.json` sigue pendiente: es prerequisito para generalizar a comms/vigia/dioses sin repetir el error de esta mañana (watchdog asumiendo topología vieja). Nota heartbeat: un gateway standalone SIN tráfico no escribe su log — umbral de 30 min genera falsos "zombies" (roshi lo disparó a los 40 min en reposo); subir a ≥6h o usar señal de polling viva.

### RC4: Timing de cron nocturno sync-upstream

**Mecanismo**: `/etc/cron.d/hermes-sync: 0 2 * * * root /root/hermes-agent-legacy-docker/scripts/sync-upstream.sh`. El script hace `git pull` + `docker compose up -d --build`. DESTRUYE y RECREA el contenedor cada noche. Si el usuario dice "se cayó a las 02:00-02:30", revisar `sync-upstream.log` primero.

**Impacto**: todos los gateways standalone mueren; watchdogs del contenedor mueren; watchdog del host (cron.d) sobrevive.

### RC5: multiplex_profiles: false = rutas INERTES + cron secundario huérfano (verificado en run.py, 03/09)

Al apagar el multiplexor para montar standalone hermanos hay DOS efectos colaterales que el log NO muestra:

1. **`gateway.profile_routes` queda muerto.** `_profile_name_for_source()` (run.py ~31208) hace `if not multiplex_profiles: return None` — ninguna ruta de chat a perfil se aplica. Consecuencia: mensajes del chat ruteado (p.ej. WhatsApp de Chucho) los atiende el perfil default (Ragnar), NO Roshi, aunque `profile_routes` luzca perfecto en config.yaml. No hay forma nativa de enrutar sin multiplex: `multiplex_profile_allowlist` solo estrecha el set servido CUANDO multiplex está ON, y una ruta a perfil no-servido se RECHAZA. Opción real para enrutamiento por chat = volver a multiplex ON y sacrificar el standalone (o bridge WhatsApp dedicado por perfil).
2. **El ticker de cron de perfiles secundarios desaparece.** `run.py` (~34418) solo pasa `profile_homes` al InProcessCronScheduler cuando `multiplex_cron` es True. Con OFF, cada gateway tick-ea SOLO sus propios jobs → los jobs de perfiles cuyo slot s6 está down (p.ej. vigia con 5 jobs y deliver discord, sin token propio en su .env — antes heredaba el secreto del default vía multiplex) NUNCA se ejecutan.

**Chequeo obligatorio tras cualquier cambio de topología**: `multiplex_profiles` × `profile_routes` × slots down con jobs habilitados × tokens propios por perfil. El pin `platforms.api_server.enabled: false` en config.yaml del perfil sigue siendo el backstop contra Desktop re-salvando configs (ver RC3).

## Patrones de recuperación

### Watchdog host-side (recomendado para perfiles always-up)

```
# /etc/cron.d/hermes-gateway-fleet (en host)
*/10 * * * * root docker exec hermes-agent /bin/bash /opt/data/scripts/gateway-fleet-health.sh
```

El script interno (`gateway-fleet-health.sh` dentro del contenedor):
- Para cada perfil en ALWAYS_UP: si `s6-svstat` dice down → `s6-svc -u` + reporta.
- Para otros slots: solo reporta si `down (unexpected` (no el down normal del reconciler).
- Sin output = todo OK (cron `--no-agent` no entrega nada con stdout vacío).

### Revive manual (cuando el watchdog no alcanza)

```bash
docker exec hermes-agent /command/s6-svc -u /run/service/gateway-<name>
docker exec hermes-agent /command/s6-svstat /run/service/gateway-<name>
```

## Forensics: reconstruir la línea temporal

```bash
# Docker events — cuándo se recreó el contenedor
docker events --since '24h' --until 'now' --filter container=hermes-agent --filter event=create
docker events --since '24h' --until 'now' --filter container=hermes-agent --filter event=kill

# Container boot log — qué decidió el reconciler
tail -n 20 /opt/data/logs/container-boot.log

# Gateway exit diagnostics
tail -n 10 profiles/<name>/logs/gateway-exit-diag.log

# Lifecycle ledger (último exit)
grep -A5 'previous_unclean_exit\|previous_exit' profiles/<name>/logs/gateway-exit-diag.log | tail -10

# S6 slot state
docker exec hermes-agent /command/s6-svstat /run/service/gateway-<name>
docker exec hermes-agent ls -la /run/service/gateway-<name>/down

# sync-upstream log (si el usuario dice 'cayó a las 02')
tail -n 30 /root/hermes-agent-legacy-docker/scripts/sync-upstream.log

# Procesos host que pueden interferir
docker run --rm --pid=host alpine ps aux | grep -E 'hermes|serve' | grep -v grep

# Actividad standalone de un perfil (ignorada por el log del multiplexor):
ls -la --time-style=full-iso profiles/<name>/logs/gateway.log
tail -5 profiles/<name>/logs/gateway.log
# Quién ve el tráfico de un usuario concreto (0 = otro proceso lo sirve):
grep -c "<chat_id>" /opt/data/logs/gateway.log
```