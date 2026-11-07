---
name: hermes-gateway-lifecycle-forensics
description: "Use when the Hermes gateway crashes or its config corrupts."
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
Matiz: "revivir" no es "saludable". s6-svstat puede decir `up` mientras el gateway
sigue en boot y sin bindear su puerto de health; la prueba viva es `curl` al
`/health` del perfil, no el estado de s6.

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
eso gateway (tool_executor: "Blocked: command or referenced script cannot restart,
ese gateway (tool_executor: "Blocked: command or referenced script cannot restart,
stop, or uninstall the gateway from inside the gateway process", exit 1). Vía válida:
cron one-shot futuro o `s6-svc` desde fuera del proceso gateway. Ver
`hermes-multiprofile-gateway-ops` (Ley 1) para detectar el servicio s6 padre real vía
ps-tree antes de reiniciar.

**Excepción útil: reinicio CRUZADO entre perfiles.** Desde una sesión servida por otro
perfil, `hermes --profile <p> gateway restart` sí funciona: drena las corridas en vuelo y
el supervisor lo relanza (`✓ Gateway relaunched by its supervisor (PID n)`). Es la vía a
usar cuando `systemctl restart` pide autenticación interactiva dentro del contenedor o el
host no es alcanzable — no bloquea el trabajo. Verificación obligatoria después (las 4,
en este orden): `systemctl is-active <unit>`, `ExecMainStartTimestamp`/`NRestarts`
cambiados, líneas `✓ <adaptador> connected` en `gateway.log` (telegram, discord,
whatsapp, webhook, api_server, a2a), y `grep -c 'cannot parse'` del log = 0 tras el
arranque nuevo.

## config.yaml corrupto: gateway vivo pero degradado

Síntoma distintivo (no hay caída): el proceso sigue `active`, pero funciones que releen
config en cada uso fallan — `WARNING gateway.run: Session hygiene auto-compress failed:
terminal policy unavailable for this profile: cannot parse <ruta>/config.yaml: while
parsing a block mapping`. Lo que se rompe no es el gateway entero sino las lecturas
nuevas (política de terminal, auto-compress, listas de plugins).

- **El daemon no relee plugins/hooks hasta reiniciar**: un fix en disco no cambia la
  config viva. Si el YAML se corrompió DESPUÉS del arranque, el reinicio es parte del fix;
  si estaba roto ANTES, el arranque habría fallado en bootstrap.
- **Validar TODOS los perfiles en un solo barrido, no solo el reportado.** Un script de
  flota que añade un plugin suele haber tocado varios perfiles con el mismo error:
  ```bash
  for f in /opt/hermes-agent-data/config.yaml /opt/hermes-agent-data/profiles/*/config.yaml; do
    echo "$(python3.12 -c "import yaml;yaml.safe_load(open('$f'));print('OK')" 2>&1 | tail -1) | $f"
  done
  ```
  Validar con un intérprete que SÍ tenga PyYAML (`python3.12` en este host, o el del cron):
  el python del kernel de `execute_code` puede no incluirlo.
- **Pitfall que invalida el archivo completo:** una línea de lista añadida a mano con 2
  espacios en vez de 4 dentro de `plugins.enabled:` (`  - <plugin>`) cierra el bloque y
  rompe TODO el YAML. El mensaje de error apunta a la línea de la clave siguiente
  (`entries:`), no a la culpable — leer las 5 líneas alrededor de la columna reportada.
  Variante del mismo bug: la línea duplicada (una a 4 espacios y otra a 2) — se borra la
  de 2 espacios, no se reindenta la buena.
- **Reparar con respaldo, nunca reescribiendo el archivo:** copiar a
  `<config>.bak-yamlfix-<timestamp>`, reindentar/eliminar la línea, revalidar el lote
  completo y confirmar la lista efectiva con `hermes --profile <p> plugins list | grep
  <plugin>`. `write_file`/`patch` del agente se rechazan sobre config de Hermes
  ("Refusing to write to Hermes config file"): usar `hermes config set` o edición por
  línea con respaldo previo.

## Silenciar los avisos de ciclo de vida (apagado / reinicio)

"⚠️ Hermes se está apagando — tu tarea actual se interrumpirá" y el heads-up de
auto-resume ("envía cualquier mensaje y continuaré") son notificaciones del gateway, NO
crons ni scripts. Se gatean por plataforma con `gateway_restart_notification` (default
`true`), que cubre también el aviso previo al shutdown:

```bash
hermes --profile <p> config set gateway.platforms.telegram.gateway_restart_notification false
hermes --profile <p> config set gateway.platforms.whatsapp.gateway_restart_notification false
```

- El CLI avisa y **reubica la clave**: como el bloque top-level `platforms:` outranks
  `gateway.platforms`, termina guardada como
  `platforms.<plataforma>.gateway_restart_notification: false`. Verificar con
  `grep -n gateway_restart_notification <config>` antes de decir que quedó.
- Se aplica al SIGUIENTE apagado/reinicio de ese perfil (el aviso se emite al apagar).
  Primera prueba real = el próximo restart del propio perfil: si hay silencio, aplicó.
- `langfuse` y `langfuse-fleet` son plugins distintos: deshabilitar uno no toca al otro;
  confirmar cuál se quería con `plugins list` antes de "arreglar" el YAML.

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

## Auto-heal que mata un boot lento (bucle caído-arrancando)
Síntoma: el watchdog marca el perfil DOWN ciclo tras ciclo, relanza el gateway, y
nunca llega a servir `/health`. Causa: el gateway multiperfil (`gateway-default`)
multiplexa ~13 perfiles y decenas de servidores MCP; el arranque completo tarda 3-4
minutos y el puerto HTTP de health bindea al FINAL del boot (:3000 default;
:3001/:3002 son los standalone golden-game/lucky-club). Un auto-heal que reinicia al
primer `/health` fallido convierte un boot lento en un bucle infinito.

Reglas para el watchdog y para el diagnóstico:
- Antes de auto-heal, leer el uptime del proceso con `s6-svstat`: si lleva menos de
  ~300s vivo es boot, no caída — esperar y re-chequear en vez de relanzar.
- Exigir 2 fallos consecutivos de `/health` antes de reiniciar; el umbral de
  "caído" debe medirse desde el arranque del proceso, no por sondeo aislado.
- Verificar la recuperación con `curl http://127.0.0.1:<puerto>/health` DENTRO del
  contenedor hermes-agent: el mismo puerto desde el host puede dar exit 7 si no está
  publicado, lo que simula una caída que no existe.

Toolbox de diagnóstico dentro del contenedor (s6, sin tooling de red):
- `s6-svstat` no está en PATH: usar `/command/s6-svstat /run/service/gateway-<perfil>`.
- No hay `ss`/`netstat`/`lsof`: probar si un puerto local escucha con un one-liner de
  python que haga connect a 127.0.0.1:<puerto> y lea el errno (0 = escuchando,
  111 = rechazado).
- `ps aux | grep 'hermes gateway'` puede no matchear por el launcher de site-packages;
  el cmdline real vive en `/proc/<pid>/cmdline` usando el pid que da `s6-svstat`.
- Zonas horarias: `/opt/data/logs/gateway.log` escribe en hora LOCAL;
  `gateway-exit-diag.log` y `gateway-shutdown-diag.log` en UTC. No mezclar
  timestamps al reconstruir la secuencia del incidente. `docker logs hermes-agent`
  solo trae el preinit de s6-overlay, nunca el ciclo del gateway.
- Warning NO fatal de boot: `AttributeError: partially initialized module
  'tools.terminal_tool_sudo' ... has no attribute '_sudo_password_cache_lock'` en
  `gateway/turn_thread_reset.py` (import circular) — el reset de hilos falla y retira
  un thread, pero el gateway queda arriba y sirve tráfico. No tratarlo como causa
  raíz de una caída.

## Proceso vivo pero colgado (hang silencioso, sin crash ni reinicio)
Síntoma: el humano reporta el bot "desconectado" en Discord, pero NO hay crash,
ni ledger entry, ni bucle de reinicios. El estado intermedio que la secuencia de
arriba no detecta porque nada murió.

Test de vida real: la edad de la ÚLTIMA escritura de logs, no el estado del proceso.
```bash
# proceso vivo + lock sostenido
ls -l --time-style=+%H:%M /opt/data/logs/agent.log /opt/data/logs/gateway.log
cat /opt/data/gateway.lock   # pid, kind, argv, start_time
ls -l /proc/<pid>            # existe? threads en /proc/<pid>/status
```
Diagnóstico = proceso vivo (lock vigente, cientos de threads) + logs sin una línea
nueva durante horas + contenedor Up con RestartCount=0 → hang, no caída. Para Discord
el socket muerto es indistinguible de un bot apagado; el humano ve lo mismo.

- Correlar la última actividad con el primer evento anómalo del día en agent.log
  (p.ej. un adaptador que falla y dispara un ciclo de reconexión) ANTES de nombrar
  causa; marcar la causa como hipótesis si no hay reproducción.
- Reinicio por hang: `s6-svc -r /run/service/gateway-<perfil>` desde fuera del
  proceso gateway (ver guardrail de plataforma) y SOLO con OK del Admin en PROD.
- Verificación post-restart: línea nueva `[Discord] Connected as <bot>#<disc>` en
  agent.log. Proceso vivo o exit de s6-svc NO prueban reconexión; un boot que toma
  el lock y no completa adaptadores reproduce el hang (mirar sección de boot lento).

## Convención de reporte al Admin
- Título: qué pasó + que ya está arriba (no alarmar con lo ya resuelto).
- Evidencia: hora exacta, señal (SIGTERM/s6), PIDs nuevos, canales verificados.
- Separar SIEMPRE lo medido (ledger, logs) de lo inferido (causa probable).
- Cada hallazgo lleva su dato concreto: valores exactos, alcance y qué NO se pudo
  comprobar. Un reporte que solo nombra categorías sin las cifras que las sostienen
  el Admin lo lee como ambiguo y lo rechaza — la cifra es la evidencia, no el adjetivo.
- Cerrar con la decisión pendiente real (p.ej. "¿quieres monitor de RAM?") en vez de
  ejecutar cambios sin OK — los cambios de infra requieren confirmación (D-I-V-E).

## Downgrade de checkout: auto-exit + crash-loop por dependencia faltante
Síntoma distintivo: `gateway.log` termina con
`gateway.runtime_downgrade_exit: This gateway loaded <hash_nuevo>, but its checkout is
now at <hash_viejo>, a release that predates the gateway runtime...` y luego el unit
systemd crash-loopea cada RestartSec con `ModuleNotFoundError` (p.ej. `yaml` en
`hermes_cli/config.py:423`).

- Causa: `/opt/hermes-agent` es el checkout DE PRODUCCIÓN que el gateway corre en vivo.
  Un `git checkout`/cherry-pick que mueva el árbol a una rama con base anterior a la
  release desplegada dispara el auto-exit; al reiniciar, el launcher
  (`~/.local/bin/hermes` → `.hermes/bin/hermes`, runtime `python-3.14.x` con
  `sys.path=/opt/hermes-agent`) no encuentra las deps del árbol viejo → crash-loop
  (~5 s/ciclo) → TODOS los canales caídos sin error de LLM ni de token.
- Recuperación verificada (04-nov-2026): respaldar HEAD+status a un manifest, luego
  `git checkout <rama de producción>` (el commit de la feature queda a salvo en su
  rama). NO hace falta `systemctl restart`: el próximo intento de systemd arranca solo.
  Verificar con `systemctl is-active` + `journalctl -u hermes-agent.service` (ojo:
  `gateway.log` puede quedarse sin escrituras nuevas tras el shutdown del proceso
  viejo; el log vivo del proceso nuevo está en journal).
- Prevención dura: el trabajo de features sobre `/opt/hermes-agent` se hace SOLO vía
  `git worktree` (los de la flota viven en `/opt/hermes-agent-data/fleet/worktrees/`).
  Nunca cambiar el checkout de producción de rama: el gateway corre desde ese directorio.

## gateway_replace_ownership_unproven: guard fail-closed del --replace
Síntoma: el unit arranca (aplica secrets, imprime el banner), sale con código 1 y systemd lo releva
cada ~20 s indefinidamente. `gateway_state.json` queda `startup_failed` +
`exit_reason: gateway_replace_ownership_unproven`, y el log del gateway NO muestra SIGTERM ni
shutdown: muere en el bootstrap, antes de levantar adaptadores.

- Dónde: `gateway/run_bootstrap.py::_start_gateway_replace_existing_instance` →
  `gateway/run.py::_replace_target_belongs_to_other_profile`. Es un guard anti cross-profile:
  **nunca señaliza un PID que no pueda probar como suyo**; si no puede probarlo, falla cerrado.
- Qué exige probar (lee `$HERMES_HOME/gateway.pid`): (1) el registro nombra **el mismo PID** que la
  instancia viva; (2) **mismo `start_time`**; (3) mismo `hermes_home`, comparado con
  `_canonical_hermes_home` → `Path.resolve()`, así que `/opt/data` y `/opt/hermes-agent-data`
  **sí** son equivalentes (el symlink no es la causa). Cualquier desajuste = refuse.
- Causa típica: varios gateways compitiendo por el mismo home (unmanaged `--idle-exit` lanzados por
  workers kanban, dashboard o CLI durante una ventana de arranque). El registro queda apuntando a un
  PID/start-time que ya no es el vivo → "ownership unprovable" → el `--replace` se niega a desalojar
  → el servicio muere y systemd lo reintenta en bucle.
- Recuperación verificada (04-nov-2026): eliminar al competidor que retiene el lock
  (`cat $HERMES_HOME/gateway.lock` te da pid + start_time). SIGTERM y, si se queda en su drain
  (SIGTERM ignorado ~10 s), **SIGKILL**. Sin instancia viva el guard no se ejecuta: el siguiente
  intento de systemd arranca, reescribe `gateway.pid`/`gateway.lock` y abre 8642/8644/9900.
- Verificación: owner de los puertos == `systemctl show -p MainPID hermes-agent.service`,
  `NRestarts` congelado, y `gateway.pid` con ese PID + su `start_time` + `hermes_home`.
- Prevención: no lanzar `gateway run` a mano (deja PPID 1 que roban el lock); una sola ruta canónica
  de HERMES_HOME; y el servicio debe estar arriba antes de que un cliente pida runtime.

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
