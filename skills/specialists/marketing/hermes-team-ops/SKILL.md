---
name: hermes-team-ops
description: "Use when who-owns-what, handoffs o ruteo Discord por perfil."
tags: [roster, equipo, crons, handoff, perfiles, profiles, ownership, hermes, routing, buzones]
version: 1.1.0
author: Ragnar
metadata:
  hermes:
    tags: [roster, equipo, crons, handoff, perfiles, roshi, vigia, division-trabajo]
    category: communications
    related_skills: [hermes-multiprofile-cron-ops, admin-reporting, guardado-doble-memoria, hermes-production-deployment]
---

# Hermes Team Ops — Roster, propiedad de crons y handoffs entre agentes

Cómo operar el equipo de agentes de NeuralCrew Labs: quién es quién, quién es
dueño de qué (especialmente crons), y cómo traspasar trabajo/ownership entre
perfiles de forma verificable.

## When to Use

- Alguien pregunta "¿quién hace qué?" o "¿de quién es este cron?".
- Hay que migrar/traspasar crons de un perfil a otro (handoff de ownership).
- Se coordina trabajo en un grupo multi-agente (Ragnar/Roshi/Vigía/equipo marketing).
- Antes de reportar crons al Admin: verificar en qué perfil viven realmente.

## Roster del equipo (corregido por Jonathan 25/08/2026 — DIVISIÓN DE TRABAJO EXPLÍCITA)

- **Ragnar** = asistente personal de Jonathan. Orquestación, decisiones, alertas
  personales (pico y placa, informes 8am/8pm a Telegram). NO produce campañas.
- **Roshi** (slug interno: `roshi`, NO renombrar el slug) = asistente de Chucho. Operativo: documentos, reportes, automatizaciones,
  QA de integridad de campañas, plantillas (campaign.yaml → 5 docs).
- **Vigía** = operaciones del sistema. DUEÑO de todos los crons de sistema/servicios:
  health checks, mantenimiento nocturno, páginas y servicios arriba. NO produce campañas.
- **Equipo Marketing/Contenido** = bots SEPARADOS por perfil (Content/Social/Ads/Funnel,
  posiblemente por cliente: golden-marketing, lucky-marketing). Es UN EQUIPO APARTE,
  no Ragnar/Roshi/Vigía.

Regla derivada: nunca reportar crons de sistema como "míos" (Ragnar) — pertenecen
a Vigía. Verificar con `docker exec -e HERMES_HOME=/opt/data/profiles/vigia hermes-agent hermes cron list`.

## Propiedad de crons (estado verificado 25/08/2026)

| Cron | Perfil dueño | Delivery |
|------|-------------|----------|
| context-report-morning (8am) | Ragnar (default) | telegram:8709909260 |
| context-report-evening (8pm) | Ragnar (default) | telegram:8709909260 |
| alerta-pico-y-placa (6am) | Ragnar (default) | telegram:8709909260 |
| guardar-diario-memoria (23:00) | **UNO POR CADA AGENTE** (default, roshi, vigia, y prod: helmer, jacqueline, nancy, yulieth, neural-admin-test) | local |
| hermes-maintenance-night (3:30) | Vigía | discord |
| vigia-health-2h | Vigía | discord |
| vigia-informe-0800 | Vigía | discord |
| vigia-auditoria-2100 | Vigía | discord |

Regla de memoria: CADA agente tiene su PROPIO guardar-diario-memoria que guarda la
memoria de ESE agente — nunca un job central que guarde por todos.

## Handoff de crons entre perfiles (receta validada 25/08/2026)

Pasos para traspasar ownership de crons de un perfil origen (ej. default) a un
perfil destino (ej. vigia):

1. **Verificar scripts en el perfil destino**: los scripts (`--script`, `--monitor-script`)
   se resuelven contra `~/.hermes/scripts/` del perfil DESTINO. Copiar:
   ```bash
   docker exec hermes-agent sh -c 'mkdir -p /opt/data/profiles/<dest>/scripts && \
     cp /opt/data/scripts/<script>.py /opt/data/profiles/<dest>/scripts/'
   ```
2. **Crear los jobs en el destino** (con `HERMES_HOME` DENTRO del contenedor):
   ```bash
   docker exec -e HERMES_HOME=/opt/data/profiles/<dest> hermes-agent hermes cron create \
     --name <nombre> --deliver <discord|local|...> --skill <skill> \
     --monitor-script <script.py> --model <modelo> --provider <provider> \
     --repeat 9999 -- "<schedule>" "<prompt completo>"
   ```
   Notas: `--repeat 9999` para que sea indefinido; `--monitor-script` hace que el
   agente solo corra si cambia la salida (ahorro de tokens); el CLI NO soporta
   `--enabled-toolsets` (el job hereda todos los toolsets del perfil).
3. **Remover los duplicados del origen**:
   ```bash
   docker exec -e HERMES_HOME=/opt/data hermes-agent hermes cron remove <job_id>
   ```
4. **Verificar AMBOS lados**: `hermes cron list` en destino y origen. El aviso
   "Gateway is not running" al crear en un perfil NO es bloqueante si el gateway
   multiplexado del default dispara los crons de todos los perfiles servidos.

## Pitfalls

- **`hermes config set` sin `--profile` puede escribir en un perfil distinto del default.** El binario `/opt/hermes/bin/hermes` (dentro del contenedor) tiene su propio perfil activo por defecto — verificado 26/08/2026: `hermes config set display.show_reasoning false` sin flags escribió en `/opt/data/profiles/sindri/config.yaml`, NO en el default. Para tocar el default (Ragnar) usar `HERMES_HOME=/opt/data /opt/hermes/bin/hermes config set ...`, y SIEMPRE leer la salida "✓ Set ... in <ruta>" para confirmar el archivo tocado (fuente de verdad de dónde escribió).
- **Ocultar el razonamiento (thinking) de un perfil:** `display.show_reasoning: false` a nivel raíz (cubre CLI/TUI/Discord) + `display.interim_assistant_messages: false` + explícito por plataforma si se quiere. El default de Hermes es `show_reasoning: true` (config_defaults.py) — un perfil sin bloque `display` muestra TODO el pensamiento. Aplicado 26/08/2026 a roshi (bloque display nuevo) y default (raíz + platforms).
- **No editar skills user-owned** (created_by=None): el curator las rechaza. Si una
  skill de este territorio necesita cambios y es user-owned, recomendar
  `hermes curator adopt <skill>` — no intentar patch repetido.
- El CLI del host `hermes` es wrapper docker exec SIN `-e HERMES_HOME` → crea en
  default aunque hagas cd al perfil. Siempre pasar HERMES_HOME dentro del contenedor.
- No confundir "AP caído" con "AP movido": verificar en el VPS correcto (AP vive en
  prod junto a Twenty desde ~25/08; en dev :8088 no responde porque ya no corre ahí).
- Perfiles nuevos (o recién creados desde Desktop) pueden nacer sin bloque
  providers/ → 'Unknown provider' al correr crons. Copiar providers + chown 10000.

## Verificación

- Después de un handoff: `cron list` en ambos perfiles, y el job destino debe tener
  `state: scheduled` con `next_run_at` futuro.
- Para confirmar quién es dueño de qué cron: leer `cron/jobs.json` de cada perfil
  (`/opt/data/profiles/<p>/cron/jobs.json`, default usa `/opt/data/cron/jobs.json`).

## Ruteo Discord por perfil y buzones de handoff (auditado en vivo 03-nov-2026)

- **Config:** bloque `profile_routes` en `/opt/hermes-agent-data/config.yaml` (rutas `- name:` con platform/chat_id/profile; canales sin ruta caen al perfil default). Hilos de foro: la ruta del `parent_chat_id` aplica a los hilos hijos.
- **Despertar por buzón:** vigía `buzon-<agente>` (`*/1 * * * *`) corre `scripts/buzon_handoff_gate.sh <agente>` → `{"wakeAgent": true}` + prompt estructurado SOLO si hay novedad en `/opt/data/inbox/<agente>/from-*/pending`; dedupe por archivo de state. La segunda corrida sobre lo mismo debe dar `false`.
- **Dos stores de cron:** el default tiene SU vigía (`buzon-ragnar`) en el store central (`/opt/hermes-agent-data/cron/jobs.json`), los demás perfiles en `profiles/<p>/cron/jobs.json` — revisar AMBOS antes de concluir que falta un vigía.
- **`deliver: discord:<chat_id>` de un cron es entrega de mensajes, NO ruteo de conversación:** un cron del default que entrega al canal de otro perfil es válido; el dueño de la ruta es quien RESPONDE si un humano escribe ahí.
- **Trampas:** (a) `_log` del gate escribe con `|| true` — si `logs/buzon_handoff.log` queda root:root 644, el gate como hermes no puede escribir y la trazabilidad muere EN SILENCIO (probar `echo test >> <log>` como hermes); (b) el gateway REESCRIBE config.yaml en runtime (estado runtime) — tras un cambio de rutas, re-contar las rutas para confirmar que sobrevivieron; (c) perfiles `gateway.standalone: true` (roshi/vigia) NO son servidos por el gateway multiplexado (warning `gateway.run` en agent.log); (d) ruteo probado sintéticamente ≠ despertar real: la aceptación exige un handoff real observable.
- **Receta completa de auditoría** (parseo real con `gateway.profile_routing`, 17 casos de matching, prueba de gate con dedupe y limpieza, verificación de vigías y repo): `references/auditoria-routing-handoffs.md`.

## Buzón agente→Bob en PROD: agent_exchange.py (verificado 03-nov-2026)

Canal bidireccional Ragnar/Rochi ↔ Bob sobre el filesystem compartido de PROD.
Script: `/opt/data/scripts/agent_exchange.py` (correr vía `ssh prod`, solo stdlib).

- **Comandos:** `send` (agente→Bob, crea ticket), `reply` (Bob cierra ticket), `notify` (mensaje libre), `read`/`list`.
- **send:** `--from ragnar --tarea "..." --asunto "..." [--prioridad alta|normal] --archivo /opt/data/...`. El `--archivo` DEBE existir en PROD bajo `/opt/data/` (validado por el script): escribir antes el adjunto vía SSH, no pasar rutas locales de DEV.
- **Ciclo:** `inbox/<agente>/pending/` → el cron `escalation-watcher` de PROD lo reclama en ≤5 min → `processing/` → respuesta en `done/|failed/<ticket>.json`. Cada depósito emite webhook best-effort al gateway DEV (ruta `buzon-bob`, HMAC `X-Hub-Signature-256`, `event_type` buzon.nuevo/respuesta/mensaje).
- **Pitfall (propietario de archivos):** si envías el ticket corriendo el script como root por SSH, el JSON queda `root:root`; hacer `chown 10000:10000` del ticket en `pending/` (el watcher corre como uid 10000 y necesita poder moverlo/borrarlo). Verificar con `ls -la` tras el send.
- **IDs no se reciclan:** `_next_id` escanea pending+processing+done+failed — si un día se parchea para mirar solo `pending/`, un id cerrado se reutilizaría y sobrescribiría la respuesta anterior.
- **Las respuestas de Bob (y sus artefactos) aterrizan SOLO en PROD (verificado 03-nov-2026):** el `.md`/JSON de verificación vive en `/opt/hermes/data/inbox/ragnar/from-bob/` de PROD; el buzón local de DEV (`/opt/hermes-agent-data/inbox/ragnar/from-bob/`) queda VACÍO. El webhook `buzon-bob` entrega el JSON del mensaje, pero los archivos referenciados hay que leerlos vía `ssh prod` con la ruta PROD. No concluir "no hay respuesta" desde el buzón local de DEV.

## Push atómico de archivos DEV→PROD (patrón verificado 03-nov-2026)

El usuario `hermes` de DEV tiene `~/.ssh/id_ed25519` autorizada como `root@100.73.30.29` (alias `ssh prod`); canal ya en uso diario por `informe_diario_exacto.py` (línea ~358) — no es teoría, es infraestructura existente.

```bash
cat local.json | ssh -o BatchMode=yes -o ConnectTimeout=20 root@100.73.30.29 \
  "cat > /opt/data/<dir>/f.json.tmp \
   && mv /opt/data/<dir>/f.json.tmp /opt/data/<dir>/f.json \
   && chown 10000:10000 /opt/data/<dir>/f.json \
   && ln -sfn f.json /opt/data/<dir>/latest.json"
```

- `cat > .tmp && mv` en el mismo filesystem = **atómico**: el consumidor (ej. Bob, uid 10000) nunca lee un archivo a medio escribir.
- Escribir como root obliga al `chown 10000:10000` posterior; `ln -sfn` para un symlink `latest` con nombre estable.
- Los directorios nuevos en `/opt/data/` que consuma Bob crearlos con `install -d -o 10000 -g 10000 -m 775`.
- Probar siempre contra `/tmp` (o dir sandbox) antes de tocar el directorio real; validar lectura de regreso (`cat` del archivo remoto) en el mismo comando.
- **775 vs 755 en dirs `hermes:hermes` de `/opt/data` es cosmético (03-nov-2026):** el grupo `hermes` solo contiene al uid 10000, así que 775 no concede escritura a nadie nuevo; lo que importa es la propiedad (`-o 10000 -g 10000`), no el bit de grupo. No "corregir" 755→775 por homogeneidad sin motivo real.

## Referencias

- Skills relacionadas (user-owned, requieren adopt para editar): `hermes-multiprofile-cron-ops`
  (técnica por-perfil), `admin-reporting` (formato reportes), `guardado-doble-memoria`
  (patrón de memoria por agente).
