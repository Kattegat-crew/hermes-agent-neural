---
name: hermes-gateway-lifecycle-forensics
description: "Use when the Hermes gateway appears to crash or restart."
tags: [gateway, s6, incidente, oom, reinicios, forense, disponibilidad]
version: "1.0.0"
author: Ragnar
metadata:
  hermes:
    tags: [gateway, s6, lifecycle, incident-triage, oom, whatsapp-ops]
    related_skills: [hermes-multiprofile-gateway-ops, service-availability-forensics]
---

# Hermes Gateway Lifecycle Forensics

Triage de incidentes de disponibilidad del gateway Hermes (blip percibido vs caída
real vs crash) en la flota multiperfil DEV/PROD. Cuando el Admin reporta "se cayó el
gateway", esta es la secuencia verificada (caso 2026-09-14).

## Regla de oro
s6 revive los gateways en <2 segundos: cuando llega el reporte humano, lo más probable
es que YA esté arriba. Primero confirmar estado vivo, después reconstruir causa.
Nunca iniciar la respuesta asumiendo que sigue caído.

## Secuencia de triage (barato → profundo)

1. **Estado vivo:**
   ```bash
   ps aux | grep 'hermes gateway'   # PIDs + columna de hora de arranque
   python3 -c "import json;d=json.load(open('/opt/data/gateway_state.json'));print(d['pid'],d['gateway_state'],list(d['platforms']))"
   ```
   `gateway_state.json` trae `platforms` con estado por canal (telegram/discord/
   whatsapp/webhook/a2a/api_server), `updated_at` y `needs_attention`. Responder por
   WhatsApp ya es prueba viva de que el canal funciona.
2. **Lifecycle ledger** (docker logs del contenedor): cada arranque registra la vida
   ANTERIOR:
   `gateway.lifecycle_ledger: Previous gateway life (pid=X, started_at=...) exited
   UNCLEANLY (no exit path ran — SIGKILL / OOM / VM death) ... last_mem={rss_kib,
   mem_available_kib, swap_used_kib} suspected_oom=False`
   - `last_mem` es la foto de memoria del instante de la muerte: leerlo directo.
   - `suspected_oom=False` NO descarta presión de memoria (14-sep: 182MB libres y
     swap de 4GB casi llenos al morir, sin flag de OOM).
3. **Descartar plataforma:** `docker inspect -f 'RestartCount={{.RestartCount}}
   StartedAt={{.State.StartedAt}}' hermes-agent` + `uptime`. RestartCount=0 y host con
   días de uptime = ciclo de vida del gateway, no de host/contenedor.
4. **Shutdown context:** línea `Shutdown context: signal=SIGTERM ... parent_name=
   s6-supervise parent_cmdline='s6-supervise gateway-<perfil>'` — dice QUIÉN ordenó la
   parada y con qué loadavg. Una línea por cada perfil (default/roshi/vigía) = reinicio
   de flota s6; una sola = evento de un perfil.
5. **Recurrencia:** si exits UNCLEANLY se repiten cada pocos días, correlar el
   `last_mem` de CADA ledger entry antes de proponer cambios. Proponer monitor
   RAM/swap solo con el patrón confirmado, no con un solo dato.

## Guardrail de plataforma
Las tools bloquean físicamente reiniciar/parar el gateway desde una sesión servida POR
ese gateway (tool_executor: "Blocked: command or referenced script cannot restart,
stop, or uninstall the gateway from inside the gateway process", exit 1). Vía válida:
cron one-shot futuro o `s6-svc` desde fuera del proceso gateway. Ver
`hermes-multiprofile-gateway-ops` (Ley 1) para detectar el servicio s6 padre real vía
ps-tree antes de reiniciar.

## Bucle de reinicios: dashboard duplicado del HOST (no es el gateway)

Síntoma: el humano dice "hay muchísimos reinicios" pero `Received SIGTERM` del gateway
solo aparece 2-4 veces/día. Existe un SEGUNDO bucle, invisible en los logs del gateway:
dos unidades systemd del host que ejecutan el MISMO comando y el MISMO puerto.

Detección (todo read-only, desde el contenedor con `/host` montado):
```bash
# 1) ritmo del bucle: contar arranques de la app por día
awk '/Dashboard binding/{print substr($1,1,10)}' /host/root/hermes-agent-legacy-docker/data/logs/gui.log | sort | uniq -c
#    normal = 1-12/día; bucle = miles/día (~1 cada 12s)
# 2) unit files del host que compiten por el puerto
grep -hE 'ExecStart|Restart' /host/etc/systemd/system/*hermes*
# 3) quién gana el puerto: edad real de cada proceso (starttime en ticks / HZ)
#    /host/proc/<pid>/cmdline  +  (uptime - starttime/100)/3600  en horas
```
Caso 2026-09-14→16 DEV: `hermes-serve.service` (`--port 9112 --no-open`) y
`hermes-dashboard.service` (`--port 9112`, con `After=hermes-serve.service`) ambos
`Restart=on-failure RestartSec=5` y ambos *enabled*. El primero gana el puerto; el
segundo arranca después por el `After=`, no puede bindear, sale con error y systemd lo
reinicia cada ~12s para siempre: 1.798 (14-sep desde 17:38:04) + 7.121 (15-sep) +
6.372 (16-sep) ≈ 15.300 arranques en 2 días, ~98% de 1 core quemado y re-init de MCPs
en cada ciclo (`soul-survey` fallando por f-string en survey_engine.py:260, `canva`
con OAuth parked). Ojo: `HERMES_HOME=/root/hermes-agent-legacy-docker/data` en esas unidades es el
MISMO directorio que `/opt/data` del contenedor (mismas inodes) → los logs se mezclan
y el "gui.log del contenedor" en realidad lo escribe el host.

Distinguir siempre las dos capas antes de reportar: (a) reinicios REALES del gateway
(SIGTERM de s6-supervise, deliberados o crash) y (b) bucles de unidades del host
(dashboard duplicado). El vigía `gateway-fleet-health.sh` NO reinicia: solo revive
slots caídos (`s6-svc -u`), así que no es causa de bucles.
Arreglo (requiere OK del Admin, toca systemd del host): deshabilitar la unidad
perdedora (`systemctl disable --now hermes-dashboard.service`) dejando la que el
Desktop usa, o moverla a otro puerto; añadir `StartLimitIntervalSec=60` +
`StartLimitBurst=5` para que un fallo no se vuelva bucle infinito.

## Convención de reporte al Admin
- Título: qué pasó + que ya está arriba (no alarmar con lo ya resuelto).
- Evidencia: hora exacta, señal (SIGTERM/s6), PIDs nuevos, canales verificados.
- Separar SIEMPRE lo medido (ledger, logs) de lo inferido (causa probable).
- Cerrar con la decisión pendiente real (p.ej. "¿quieres monitor de RAM?") en vez de
  ejecutar cambios sin OK — los cambios de infra requieren confirmación (D-I-V-E).

## Skills relacionadas (user-owned, no editar)
- `hermes-multiprofile-gateway-ops`: leyes 1-4 del gateway multiperfil (servicio s6
  real, config cacheada, canales Discord, sesiones por perfil). Esta skill la
  complementa con el flujo de incidente.
- `service-availability-forensics`: forensia general de servicios/watchdogs. Su
  secuencia de contenedores aplica a servicios docker normales, NO al gateway Hermes
  (s6 lo revive antes de que llegue el reporte).

## Casos
- 2026-09-14 DEV: SIGTERM de s6 a la flota completa a las 17:37:51 (2 líneas Shutdown
  context: roshi + default), ledger con exits UNCLEANLY de vidas previas (pid 176
  desde 08-sep, pid 330382 desde 12-sep), RestartCount=0, host 33 días uptime,
  memoria al kill: 182MB libres / swap 4GB llenos / loadavg 6.84. Veredicto: blip de
  flota s6 con presión de memoria como sospechoso, no confirmado (un solo evento).
