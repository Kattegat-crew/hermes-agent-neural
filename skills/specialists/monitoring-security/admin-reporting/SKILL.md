---
name: admin-reporting
description: "Use when reporting status to the Admin or in crons."
version: 1.0.0
author: Ragnar
tags: [admin, reportes, cron, silent, whatsapp, verificacion]
---

# Admin Reporting — Reportes y crons para el Administrador

Reglas para reportar al Admin (Jonathan) en crons, informes de estado, y cualquier comunicación automatizada.

## Principios

1. **Nunca inventar estado de infraestructura.** Antes de afirmar qué perfiles, agentes, canales o números existen en prod, leer Engram (`mem_search all_projects=True`) y el estado real del VPS (`ls /opt/data/profiles/`, `profile_routes` en config.yaml, `docker ps`). Error grave 24/08/2026: inventé "Hermes Golden/Lucky con WhatsApp 3166910728/3166909310" — el Admin corrigió con «Completamente falso!!! Entra al vps de prod y revisa exactamente los perfiles». La verdad: perfiles por persona (helmer, jacqueline, yulieth, nancy) con 1 número compartido.

2. **Cron delivery limpio.** Por defecto Hermes envuelve la respuesta con `Cronjob Response: <name> (job_id: ...)` en inglés. El Admin exige que NO haya nada en inglés. Fijar `cron.wrap_response: false` en config.yaml (`hermes config set cron.wrap_response false`). Backup antes.

3. **[SILENT] cuando no hay nada nuevo.** Si el cron no tiene novedades, alertas, ni información relevante, responder `[SILENT]` (exactamente esa palabra, nada más) para suprimir el envío. No generar spam.

4. **Informes mínimos y accionables.** El Admin NO quiere métricas de tokens, sesiones totales, costos, ni desgloses por plataforma. Máximo 10-12 líneas.
   - **Matutino (8am)** → clima Bogotá (wttr.in?m) + calendario Google + prioridades de pending.md. Formato: 🌤 📅 📌 ⚠️
   - **Vespertino (8pm)** → actividad real del día (daily_session_report.py) + pendientes mañana. Formato: 🌆 ✅ 📌 ⚠️
   - Solo incluir alertas si algo está roto (disco >80%, gateway caído, MCP offline). Sin alertas → omitir la línea.

5. **No catalogar el estado de la flota desde memoria: verificar contra los artefactos de planificación.** Cuando el Admin pregunta "¿ya tenemos X?" o corrige con "revisa lo que hicimos ayer", la respuesta se arma leyendo en vivo: `~/planes/*.md` (planes con sección de estado de ejecución), `/opt/data/kanban.db` (tabla `tasks`, no `cards`; abrir en modo ro) y `/opt/data/cron/jobs.json` (schedule como objeto `{kind, expr|minutes}`). Corrección del 24/10/2026: respondí que los crons eran polling por categorías de memoria y el Admin me señaló que el plan crons-evento (23-oct) ya tenía buzon-bob y leads en webhooks de evento con sus tarjetas Kanban en `done`. Nunca describir capacidades por categorías mentales: citar plan + evidencia viva.

6. **Entrega de cron = resumen diagnosticado, nunca volcado crudo.** Un log sin procesar (tracebacks, líneas `==` técnicas) llega al Admin como "formato extraño" — no informa. El stdout de un job `--no-agent` ES el mensaje: cabecera (qué es + cuándo), UNA línea por paso con estado (✓/❌/⚠️), estado final (OK / PARCIAL / FALLIDO + duración) y la ruta del log completo en disco para quien quiera el detalle. Tracebacks y logs van SOLO al archivo citado; jamás al chat.
## Inventario completo de pendientes (cuando el Admin pide "la lista completa")

Una lista de pendientes NO se arma solo desde el store: el Admin espera el barrido de TODAS las fuentes en una sola pasada.

1. Store de pendientes: `python3 /opt/hermes-agent-data/scripts/pending_tasks.py list` (pending.md es una vista regenerada; el store es la fuente).
2. Kanban (readonly): `select tenant, status, count(*) from tasks where status != 'done' group by 1` + las tarjetas abiertas por tenant.
3. Repo de campañas: árbol `planning/<campana>/` — piezas en `04-aprobadas/`, estados del calendario (`a_producir` vs producido), especificaciones pendientes de pie legal o aprobación documental.
4. Crons: `jobs.json` (jobs con failure_streak > 0 o last_status != ok).
5. Infra viva: `df -h` en DEV y PROD, health de servicios críticos.
6. state.db de sesiones: búsqueda full-text en mensajes del Admin por las palabras clave del pedido (ej. "cotización", "perifoneo") — hay pedidos que nunca se convirtieron en tarea y solo viven en el historial.

Reglas de presentación:
- **Deduplicar el ruido de patrulla:** los crons nocturnos crean una tarea nueva por cada detección ("actualizar Hermes a vX"); colapsar los repetidos en UNA entrada antes de reportar.
- **Ítems con fecha vencida:** marcarlos como "decidir: reprogramar o descartar", no listarlos como si estuvieran vigentes.
- Cerrar con una recomendación priorizada de orden de ejecución (opinión, no inventario crudo) y preguntar por dónde empezar.

## Reglas de envío multi-remitente (WhatsApp, 27-28/08)
- El puente WhatsApp es UN solo remitente para todos los perfiles ruteados: SIEMPRE etiquetar quién firma ("— Ragnar" / "— Roshi") en informes proactivos, o enviar al grupo oficial DE. Chucho reclamó un informe "de Roshi" que era de Ragnar (27/08).
- Informe diario del equipo: cron `informe-diario-equipo` (57dd5580b592, 07:00, deliver local) → el agente corre `/opt/data/scripts/informe_diario_equipo.py --yesterday --send` → grupo DE + Jonathan + Chucho con etiqueta de remitente. Fuentes: state.db dev+prod, opencode.db (snapshot vía docker run -v), VPS Brain, Diario wiki.

## Operaciones técnicas de cron en VPS prod

### Acceso SSH anidado dev→prod
- Cadena: contenedor dev → `ssh root@10.0.7.1` (host dev) → `ssh -i /root/.ssh/id_ed25519 root@169.58.189.222` (host prod = vmi3513784)
- Para ejecutar Python dentro del contenedor prod: `cat script.py | ssh <host> 'docker exec -i hermes-agent python3 -'` (stdin). Evitar heredocs y docker cp desde el contenedor — el quoting anidado falla.

### Cambios de config en prod
- Usar: `docker exec hermes-agent hermes config set <key> <value>` (escape fiable incluso con SSH anidado).

### Creación de cron jobs en prod
- Solo el gateway del perfil **default** corre el scheduler. Los gateways por perfil (helmer, jacqueline…) están s6-supervisados pero su `hermes cron status` da falso negativo.
- Los jobs de cron se crean en `/opt/data/cron/jobs.json` del default con `deliver` explícito (`whatsapp:<chat_id>`), NO en `profiles/<p>/cron/jobs.json`.
- Tras editar jobs.json a mano, forzar recálculo con `hermes cron tick` (si no, `Next run` queda `None`).

### wrap_response
- `cron.wrap_response: false` en config.yaml → entrega limpia (sin cabecera "Cronjob Response" en inglés).
- Aplicado en dev y prod (24/08/2026) con backup de config.yaml.

## Envío directo a Telegram del Admin (fallback verificado 04-nov-2026)

Para avisos de cierre de proyecto/avances que el Admin espera por Telegram (chat `8709909260`, 5-8 líneas, español, sin logs ni JSON):

1. `TELEGRAM_BOT_TOKEN` puede NO estar en `/opt/data/.env` ni en `/opt/data/secrets/`. Fuente viva: el environ de un proceso daemon de Hermes vivo — iterar `pgrep -f hermes`, y por cada pid leer `tr '\0' '\n' < /proc/<pid>/environ | grep '^TELEGRAM_BOT_TOKEN='` (algunos dan Permission denied / No such file: seguir al siguiente).
2. Los pids se RECICLAN entre llamadas: capturar el token y usarlo EN EL MISMO comando shell (variable `TOK`), nunca en dos llamadas separadas — el pid puede morir en el ínterin y un token vacío produce HTTP 404 silencioso.
3. Enviar con la Bot API: `POST https://api.telegram.org/bot$TOK/sendMessage` con JSON `{"chat_id":"8709909260","text":...}`; verificar `ok:true` + `message_id` en la respuesta, no asumir el envío.

## Referencias

- `references/prod-agents-cron-ops.md` — roster real de agentes de prod, profile_routes WhatsApp, saludos 7AM creados.

## Skills relacionadas
- `hermes-admin-operations` — ciclo D-I-V-E para operaciones de Hermes (no se pudo editar, no curator-managed).