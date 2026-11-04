---
name: hermes-multiprofile-gateway-ops
description: "Use when debugging a multi-profile Hermes gateway."
tags: [hermes, gateway, s6, perfiles, discord, whatsapp, multiplex, ops]
---

# Hermes Multiprofile Gateway Ops

Operación y troubleshooting de un gateway Hermes que sirve **varios perfiles enrutados**
(8 especialistas, bots de cliente, etc.) vía `gateway.profile_routes` con multiplexing.
Este skill es la referencia **verificada el 2026-08-26** y corrige afirmaciones obsoletas
de skills user-owned (ver «Conflicto con skills user-owned»). Cuando el usuario corra
`hermes curator adopt` sobre esas skills, absorberlas aquí.

## Ley 1 — El layout s6 cambió: verificar el servicio real con ps, nunca asumir

El proceso real del gateway es `…/python3 … hermes gateway run --replace`. **Su padre
s6 varía entre fechas/configuraciones:**

- 19/08: el servicio real era `main-hermes` (restart cambiaba PID).
- 26/08: el proceso real (PID 64919) corre bajo **`s6-supervise gateway-default`**
  (PPID 174). `main-hermes` solo lanza un `s6-ipcserverd` (wrapper): **reiniciarlo NO
  cambia el PID del gateway ni aplica configs**. Dos crons one-shot del 26/08 apuntando
  a `main-hermes` dejaron el PID intacto — prueba contundente.

**Fuente de verdad SIEMPRE:**
```bash
ps -eo pid,ppid,cmd --forest | grep -A1 -B1 "gateway run"
# leer el PPID del proceso python y buscar qué s6-supervise lo tiene como hijo
```

Reinicio correcto hoy: `/package/admin/s6/command/s6-svc -r /run/service/gateway-default`.
Nunca fijarse en fechas ni en el nombre documentado: el ps-tree manda.

## Ley 2 — La mayoría de cambios de config.yaml aplican SIN reinicio (caché por mtime)

`hermes_cli/config.py::read_raw_config()` cachea por `(st_mtime_ns, st_size)` del archivo.
Al editar `config.yaml`, la caché se invalida y **el proceso vivo lee el valor nuevo por
turno** (verificado 26/08: el fix de la key de compresión quedó activo sin reiniciar;
`read_raw_config()` devolvió la key corregida al instante).

Regla práctica: editar → verificar con `python3 -c "import sys; sys.path.insert(0,'/opt/hermes'); from hermes_cli.config import read_raw_config; print(read_raw_config()['auxiliary']['compression'])"`.
Solo reiniciar si el comportamiento no cambia o el ajuste se hornea al arrancar (adapters,
routing table, env del proceso).

## Ley 3 — Canales Discord dedicados por bot: require_mention + free_response_channels

Con `discord.require_mention: true` (default), el gateway **ignora mensajes en canales que
no estén en `discord.free_response_channels`** salvo mención al bot. Para canales dedicados
a un perfil (p.ej. `hermodr-connect`), el channel ID DEBE estar en `free_response_channels`
o el mensaje ni llega: 0 logs del canal, 0 sesiones, y el usuario percibe "el bot no tiene
memoria / no responde".

```yaml
discord:
  require_mention: true
  free_response_channels: "1493432785245962250,<canal-bot-1>,<canal-bot-2>"
```

## Ley 4 — Sesión y memoria por perfil (fix interno #88532)

Con `multiplex_profiles: true`, el gateway escribe las sesiones del perfil enrutado en
**`profiles/<name>/state.db`** (NO el raíz). Implementación:
`gateway/session.py::_open_session_db_for_active_scope` resuelve por el HERMES_HOME override
del turno; el Desktop lista cada perfil vía `web_server.py::_open_session_db_for_profile`
(abre `<home>/state.db`). Clave de sesión Discord: `platform:chat_id` → hilo persistente
por canal (retomar conversación = misma clave).

## Ley 5 — Perfil con celular propio NO va en el multiplex: standalone con `--force` + backstop

Verificado en PROD el **2026-09-21** (`golden-game` :3001 y `lucky-club` :3002). Un perfil al que
el cliente le dio **su propio número de WhatsApp** no puede servirse desde el gateway multiplexado:

1. `gateway/run_adapters.py:983` — bajo multiplex **no se arrancan adaptadores WhatsApp de perfiles
   secundarios** ("a secondary would retry-loop"). El celular del cliente nunca conecta.
2. Sin `--force`, la unidad s6 de un perfil servido por el multiplexer sale con **exit 78** y s6
   **deja de reintentar**: el celular queda sordo **en silencio** (así estuvo `lucky-club` ~27 h).
3. `hermes_cli/container_boot.py:114` (`should_start = not multiplex_profiles and ...`) deja **todo**
   slot de perfil en `down` y **re-renderiza el `run` sin `--force`** en cada boot del contenedor:
   el arreglo manual se pierde solo ⇒ el backstop tiene que vivir **fuera** del contenedor.
4. El slot debe quedar **propiedad de `hermes`** (`run`, `finish`, `log/`, `supervise/control`) y con
   `API_SERVER_PORT` propio (8643/8644) para no chocar con el listener compartido 8642.

Backstop (cron del host cada 5 min, `exit 0` siempre, **silencioso si está sano**):
`/etc/cron.d/hermes-casino-gateways` → `/usr/local/bin/hermes-casino-gateways.sh` →
`docker exec … python3 /opt/data/scripts/casino_gateways_watchdog.py` (re-registra slot, re-añade
`--force`, quita `down`, `s6-svc -u`, verifica el bridge) → notificador Discord.

El aviso a Discord va en **capa aparte** (`hermes-casino-gateways-notify.py` + `.env` 0600 root +
`state.json` con dedup y repetición máx. cada 6 h): 🟠 auto-sanado · 🔴 SIN REPARAR (menciona al
Admin) · 🟢 recuperado. Runbook completo, contrato del notificador y prueba E2E sin downtime:
`references/2026-09-21-casino-standalone-gateways.md`.

**Probar reparaciones sin downtime:** editar `/run/service/gateway-<perfil>/run` (quitar `--force`)
**no reinicia el servicio** — se puede ejercitar la ruta de reparación en producción sin corte.

Pitfalls añadidos: no crear cron jobs **dentro** de esos dos perfiles (el ticker del multiplexer y el
suyo los duplicarían); el multiplexer los sigue listando en `served_profiles` y en v0.21.3 no existe
lista de exclusión (`multiplex_profile_allowlist` retirado) — sacarlos de `profiles/` rompería
`hermes -p <perfil>` y su cron.

## Diagnóstico rápido: "bot no responde / no recuerda / Desktop vacío"

1. `grep -c <channel_id> /opt/data/logs/agent.log` → **0 = el mensaje nunca se procesó**
   (require_mention gating o reinicio que no aplicó — Ley 1/3).
2. `tail profiles/<bot>/logs/agent.log` → si la última actividad es un smoke-test CLI,
   el tráfico Discord nunca llegó al perfil.
3. Inspeccionar `profiles/<bot>/state.db` (tabla `sessions`, col `chat_id`): si solo hay
   `source='cli'`, no hubo inbound enrutado.
4. Revisar el config vivo (`read_raw_config`, Ley 2) y el PID real del proceso (Ley 1).

## Script de reinicio auto-detectable

Ver `scripts/gateway_restart_auto.sh` — detecta el servicio padre real vía ps en vez de
hardcodear `gateway-default`/`main-hermes`. Usarlo con el patrón cron one-shot `no_agent`
programado 3–4 min en el futuro (nunca reiniciar dentro del turno actual).

## Conflicto con skills user-owned (NO editar; recomendar `hermes curator adopt`)

- `hermes-gateway-s6-ops` (user-owned): contiene "el servicio real es main-hermes — NO
  gateway-default" (corrección del 19/08). **DESACTUALIZADA desde el 26/08** — el layout
  cambió y ahora el proceso real corre bajo `gateway-default`. Si esta skill se vuelve a
  cargar, verificar primero con ps-tree.
- `hermes-profile-routing` (user-owned): sólida en routing, pero no cubre el gating de
  Discord ni la persistencia por perfil — este skill la complementa.
- `hermes-gateway-ops` (user-owned, author neuralcrew-ops): ya dice correctamente que el
  servicio real es `gateway-default` — coincide con la Ley 1 del 26/08.

## Pitfalls

- No reiniciar nunca dentro del turno actual: programar cron one-shot y entregar respuesta.
- Tras un reinicio, verificar PID NUEVO y estabilidad, no solo "exit 0" del s6-svc.
- `profiles/<bot>/logs/agent.log` puede terminar en un smoke-test y NO reflejar el tráfico
  real: distinguir `source=cli` de `source=discord` en state.db antes de concluir.
- El gateway real a veces muestra autenticación degradada (warnings `auth.json` creado por
  root) — no bloquea el enrutado; es un pendiente de permisos aparte.