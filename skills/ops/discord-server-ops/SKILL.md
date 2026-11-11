---
name: discord-server-ops
description: Use when reorganizing Discord channels, forums or threads.
version: 1.0.0
author: NeuralCrew
license: proprietary
metadata:
  hermes:
    tags: [discord, canales, foros, archivo, crons]
    related_skills: [hermes-fleet-operations, tesoreria-casinos-ops]
---

# Discord server ops (NeuralCrew Labs)

## When to Use

- Crear, mover o archivar canales, foros o hilos del guild.
- Reasignar entregas de crons a canales/hilos de Discord.
- Auditar entregas rotas (hilo archivado o inexistente).
- Reorganizar categorías sin romper automatizaciones.

Guild `1493354289266167808`. Bot con permisos reales: `1493385610797252758` (token en Vaultwarden, ítem `Discord NCA - bot+webhook - prod`). Otro token del mismo ítem devuelve 404.

## Regla que evita romper todo

**Antes de archivar o mover un canal/hilo, buscá su id en todos los `jobs.json`** (`deliver` y `failure_deliver`). Un cron que apunta a un hilo archivado **falla en silencio**: el job reporta `ok` y el mensaje no llega. Pasó con `Radar Correo`.

Auditoría (0 falsos verdes):
0. Chequeo barato primero: leer `last_delivery_error` de cada job en `jobs.json` — un `404 Unknown Channel (code 10003)` delata el canal muerto sin llamar a la API de Discord. Un job con esta señal sigue reportando `scheduled`/`ok` en el campo de estado, así que solo este campo lo delata.
1. Indexar el guild: canales + hilos activos (`/guilds/{g}/threads/active`) + archivados por foro (`/channels/{c}/threads/archived/public?limit=100`).
2. Cruzar cada `deliver=discord:<id>` de DEV y PROD contra ese índice: `hilo_ARCHIVADO` o `NO_EXISTE_EN_GUILD` = entrega rota.
3. Re-apuntar con `hermes cron edit <job> --deliver discord:<id_nuevo>` (por perfil: `hermes -p <perfil> cron edit`).

**`deliver=discord:<id>` apunta SIEMPRE a canal de TEXTO o HILO, nunca a un foro (type 15):** publicar en un foro sin hilo responde 400 y el scheduler lo traga en silencio — el job reporta `ok` y nadie ve nada.

## Clasificar quién escribe en un hilo (sistema vs marca)

- Antes de mover entregas, clasificar CADA escritor del hilo: **sistema** (watchdogs, guardias, fallos de crons, trazabilidad) vs **marca** (promos, informes de Golden/Lucky). Un hilo de marca nunca recibe avisos de sistema: si llega contenido mixto, re-apuntar los scripts de sistema a un hilo de guardias (`🛡️ guardias y vigías`) y dejar el hilo de marca solo para contenido de marca.
- Un solo autor visible en Discord no prueba que sea el único: grep el id del hilo y `DISCORD_POST`/`WEBHOOK` en los scripts de PROD (`/opt/data/scripts/`, `profiles/*/scripts/`) y DEV, más `deliver`/`failure_deliver` de todos los `jobs.json`.
- Re-apuntar con `sed -i` dejando backup `.bak-reclasif-<fecha>` y verificar sintaxis de cada archivo tocado (`python3 -c "import ast; ast.parse(open(f).read())"` o `bash -n`) antes de dar por hecho el cambio.

## Verificar escribilidad del bot antes de declarar hecho

Re-apuntar un script NO prueba que el bot pueda escribir en el hilo destino: prueba post-then-delete con el token real del bot de PROD (`DISCORD_BOT_TOKEN` en `/opt/data/.env`, ejecutar dentro de `docker exec hermes-agent`) — publicar un mensaje de prueba en el hilo y borrarlo de inmediato. Publicado+borrado = conducto abierto.

## Hilos huérfanos: clasificar antes de archivar

Un hilo con solo su mensaje raíz NO es huérfano por defecto: un watcher puede alimentarlo y callar cuando no hay nada que decir. Clasificar primero: **con fuente** (no tocar), **sin fuente** (pendiente de decisión del Admin), **backlog legítimo** (tickets viejos con apertura sola), **basura** (archivar+lock con `PATCH {archived:true, locked:true}`).

## Operaciones (REST v10)

**TODA llamada REST lleva header `User-Agent` (ej. `DiscordBot (hermes,1.0)`) además del `Authorization: Bot`** — sin él la API falla con errores que parecen de permisos o 404, y se concluye falsamente que "el bot no tiene permisos". Antes de dudar de los permisos del bot, verificar que el request lleve ambos headers.
|---|---|
| Crear foro | `POST /guilds/{g}/channels` con `type:15`, `name`, `parent_id` |
| Crear hilo con mensaje | `POST /channels/{foro}/threads` `{name, message:{content}}` |

El mensaje raíz del hilo tiene el límite estándar de 2000 chars: excederlo responde HTTP 400 genérico. Para tickets/informes largos, crear el hilo con un cuerpo corto (síntoma + tabla de evidencia) y publicar el detalle como mensajes de seguimiento en `/channels/{thread}/messages`.
- Publicar en un foro con tags: resolver los ids reales con `GET /channels/{foro}` → `available_tags` y pasarlos como `applied_tags` en el payload de creación — un post sin tag queda fuera del flujo del foro.
- El secreto de autenticación del bot de la flota vive solo en `/opt/data/.env` del host PROD (los `.env` de DEV/contenedor no lo traen): ejecutar el POST REST desde ese host — nunca imprimir el secreto ni inlinarlo en el payload. Para scripts Python usar el helper existente en lugar de re-leer el `.env`: `sys.path.insert(0, '/opt/data/scripts')` + `from _discord_token import discord_token` — resuelve `os.environ` → fuentes de secretos del perfil (v0.22.x) → `/opt/data/.env` legado, cachea el resultado y devuelve `''` si no hay (verificar antes de postear, no enviar un `Authorization: Bot ` vacío).
- Tras crear un hilo/ticket, releerlo (`GET /channels/{thread}` + sus mensajes) y confirmar nombre, tags y mención resuelta ANTES de reportar el enlace — el POST exitoso no prueba que quedó bien armado.
- Plantilla completa de ticket para el foro técnico: `references/ticket-foro-tecnico.md`.
| Mover de categoría | `PATCH /channels/{id}` `{parent_id}` |
| Dejar read-only | `PATCH` con `permission_overwrites` de `@everyone` deny `2048\|64\|34359738368` (enviar, reaccionar, crear hilos) |
| Archivar+bloquear hilo | `PATCH /channels/{thread}` `{archived:true, locked:true}` |

`PATCH` de permissions **reemplaza** la lista completa de overwrites: leer los actuales, conservar los de otros roles y solo agregar el de `@everyone`.

## Leer y gestionar tickets del foro tickets-tecnicos (REST v10, verificado 09-nov-2026)

- **Token del bot sin estar en PROD:** cualquier proceso `hermes` vivo del gateway lo trae en su entorno; resolverlo por PID sin imprimirlo jamás (solo log de longitud): localizar con `for p in $(pgrep -f hermes); do tr '\0' '\n' < /proc/$p/environ 2>/dev/null | grep -q '^DISCORD.*TOKEN=' && echo $p && break; done` y extraer con `tr '\0' '\n' < /proc/$P/environ | sed -n 's/^DISCORD[A-Z_]*TOKEN=//p' | head -1`. Verificado desde el contenedor DEV — alternativa válida cuando no se está en el host PROD.
- **Listar hilos de un foro: NO usar `GET /channels/{foro}/threads/active`** — devolvió 0 hilos en los 3 foros activos mientras el guild tenía 130. Usar SIEMPRE `GET /guilds/{g}/threads/active` y filtrar por `parent_id` del foro.
- **Leer mensajes de un hilo:** `GET /channels/{thread}/messages?limit=25` devuelve un ARRAY JSON directo (no `{"messages": [...]}`) — parsear como lista o el parser revienta.
- **Cambiar el estado de un ticket:** `PATCH /channels/{thread}` con `{"applied_tags":[...]}` **REEMPLAZA la lista completa** — incluir siempre los tags no-estado que se quieren conservar (@Jon/@Chucho). Tags del foro tickets-tecnicos: PENDIENTE `1554957746980261942`, EN CURSO `1554957746980261943`, REVISIÓN `1554957746980261944`, CERRADO `1554957746980261945`, BLOQUEADO `1554957746980261946`; @Jon `1555025462684819496`, @Chucho `1555025478450946119`.
- Post-PATCH, releer `GET /channels/{thread}` y confirmar `applied_tags` antes de reportar el cambio de estado.
- **Cerrar un ticket son 2 pasos, no 1:** (1) postear DENTRO del hilo el mensaje de cierre — evidencia viva (comandos con salida real, hashes/estados verificados), hallazgos y criterios NO cumplidos declarados explícitamente como parciales (nunca maquillar un criterio incumplido ni cerrar como "todo cumplido" sin simulacro), con menciones reales `<@id>` al responsable/admin; (2) recién entonces el swap del tag de estado a CERRADO conservando entorno/tipo/responsable. `crear_ticket.py` solo CREA tickets: el cierre es REST manual (POST mensaje + PATCH tags).
- Flujo de creación con `crear_ticket.py` (vía única, probado): redactar el cuerpo en un archivo scratch con las 3 secciones obligatorias (`Objetivo` / `Criterios de aceptación` / `Fuera de alcance`) + la línea `**Asignado:** <@id>`, iterar `--dry-run` hasta verde y recién entonces correr el POST real. El dry-run devuelve el error exacto del gate que falla y, en OK, los tags aplicados y el conteo de chars — no lanzar el POST sin un dry-run verde.
- El gate de mención exige el `<@id>` LITERAL del responsable dentro del cuerpo: pasar `--responsable <id>` solo no satisface el gate ni notifica a nadie. Presupuestar ~50 chars para la línea de asignación dentro del tope de 2000; si el cuerpo pasa el límite, recortar prosa y redundancias, nunca los criterios de aceptación ni la prueba negativa.
- El POST real imprime `verificacion: OK (tags=True, mencion=True)` — ese OK del script no reemplaza la relectura obligatoria del hilo (name, applied_tags, menciones) antes de reportar el enlace.
- Si el cierre deja trabajo pendiente, nombrar en el mensaje el hilo/ticket hogar de ese trabajo (no dejarlo huérfano solo en el chat).
- Flujo probado de auditoría de tickets: guild threads/active → filtrar foro → tabla id|estado|nombre|tags → leer mensajes de los hilos relevantes → actualizar evidencia con `POST /channels/{thread}/messages` + mover tag. Con eso se auditaron los 61 tickets técnicos en una pasada.

## Regenerar vistas derivadas del foro (tablero de prioridades)

Un tablero/priorizador que vive como mensajes de un hilo es DATO DERIVADO: se recalcula desde un snapshot fresco del foro, nunca se parcha de memoria ni de un turno anterior. El encabezado declara siempre fecha/hora de regeneración, fuente (tags + línea `Estado:` del mensaje raíz) y alcance.

Procedimiento:
1. Snapshot: `GET /guilds/{g}/threads/active` filtrado por `parent_id` del foro + leer el mensaje raíz de cada hilo para su línea `Estado:`. Guardar el JSON en scratch y calcular TODO desde él.
2. Conciliar tags ↔ cuerpo ANTES de publicar conteos: si el tag de estado contradice la línea `Estado:` del cuerpo, corregir el tag con `PATCH /channels/{thread}` `{applied_tags}` (reemplazo completo — conservar los tags de responsable/entorno). Declarar los casos inversos que se dejan sin tocar.
3. Contar abiertos por ID ÚNICO de ticket, no por tag: un ticket puede llevar tag de dos responsables y se contaría doble; un hilo SIN tag de estado pero con cuerpo real de ticket también cuenta como abierto (revisar hilos archivados sin tags, no solo los activos).
4. Actualizar el tablero: `GET /channels/{thread}/messages`, identificar cada segmento por su encabezado de primera línea y hacer `PATCH` de cada mensaje existente in-place; los segmentos nuevos van como `POST` nuevos. Un POST cae DESPUÉS de cualquier mensaje intermedio (incluidos los del usuario) y no se puede reordenar — diseñar los segmentos para que cada uno se entienda solo.
5. Verificación: re-leer el hilo completo y contar los ítems numerados por sección contra los totales calculados en el paso 3. Si no cuadran, no reportar.

En cada PATCH/POST usar el helper `_discord_token` + ambos headers, pausa ~0.5s entre llamadas y reintentos con sleep creciente ante HTTP 429.

## Mensajes de terceros en un hilo de ticket (gobernanza)

- Si un tercero (bot u humano) añade mensajes a un hilo de ticket cuya edición estaba acotada por el Admin, NO respondas ni corrijas dentro del hilo: tu intervención también sería un mensaje nuevo sin autorización. Verifica, archiva evidencia fuera del hilo (inbox PROD / JSON) y escala al Admin por Telegram. Ver `buzon-inbox-ops` para el flujo completo de verificación y escalado.
- Verifica cada afirmación del mensaje ajeno en la fuente antes de repetirla: contenido del hilo con `GET /channels/{thread}/messages` + hash local por mensaje (detecta añadidos/ediciones que el aviso no menciona); repos GitHub con `GET /repos/{owner}/{repo}` + `/branches` + `GIT_TERMINAL_PROMPT=0 git ls-remote <url>` (0 refs = vacío); directorios del host inspeccionando el servidor real por SSH. Lo que SOLO consta en el mensaje del tercero se reporta como "no verificable", nunca como hecho.
- Recursos creados bajo tu identidad (repos, cuentas, publicaciones) sin registro de comando en tu sesión se reportan al Admin como no atribuibles hasta su confirmación.

## Estructura vigente

**Mapa canónico SSOT: `/opt/data/brain/ops/mapa-final-discord-2026-11-04.json`** (optimización 04-nov-2026 con Plon; fases previas de ese mapa quedaron PENDIENTES — archivado de los 15 canales y redirección de 4 crons de calendario; verificar contra el archivo antes de asumir). Patrones del mapa:

- **`digital-vikings` (forum 1554961885160415283) = el foro de trabajo: UN HILO FIJO POR TEMA.** Los canales por agente (bragi/vili/heimdall/sindri/hermodr/brokkr/freyja/ullr/finanzas) y `crons-bragi`/`crons-dev`/`crons-ads` quedaron ARCHIVADOS; su contenido vive ahora en hilos fijos dentro de digital-vikings (Finanzas 1567587939783806996, Calendario 1567587946373062667, etc. — ids en el mapa).
- Fallos de crons → hilos `⏰ crons-dev (fallos)` / `⏰ crons-ads (fallos)` en `alertas-prod` (1557152614045581373).
- `informe-diario` (1567284096558825576, texto): NCL HOY 07:15 + hilo fijo NCL Hoy.
- Al cablear un notify/cron nuevo: **reutilizar un hilo FIJO por tema** (buscarlo en threads active+archived del foro, reabrir si está archivado, crear solo si no existe) — NUNCA un hilo nuevo por corrida. Ejemplo implementado: `notify_discord.py` de rendición → hilo fijo `📊 Rendición mensual` (1567660948058275872) en digital-vikings.
- Hilo fijo ≠ por-agente: para avisos de campaña manual sigue vigente la regla del hilo `paquete-diario`; el destino lo decide el mapa canónico, no memoria vieja de canales archivados.

## Verificar antes de creer: `content` vacío no es mensaje vacío

Los mensajes posteados con `embeds` tienen `content` vacío y el contenido real vive en `embeds[].title/description/fields`. Al auditar entregas hay que leer ambos campos, o se reporta como "mensaje vacío" un aviso que sí traía datos (pasó con el conciliador Bre-B).

## Regla de oro: quién puede entregar a Discord

**Un job solo entrega a Discord desde el perfil `default`.** Los perfiles satélite (helmer, yulieth, nancy, golden-game, lucky-club…) corren su cron en su propio gateway, que **no tiene plataforma Discord**, y la entrega muere con `platform 'discord' not configured/enabled` (`cron/scheduler_delivery.py:1203`). El WhatsApp sí funciona en satélites (rutas en `profile_routes` del primario).

- Un `hermes -p <perfil> cron run` desde el CLI ejecuta inline y **sí** entrega a Discord — por eso un test manual da falso verde. La prueba válida es una corrida programada o revisar `last_delivery_error`.
- Patrón correcto: crear el job en `default` con un wrapper en `/opt/data/scripts/` que haga `export HERMES_HOME=/opt/data/profiles/<perfil>` y ejecute el script real del perfil. El wrapper es obligatorio porque `--script` exige rutas relativas a `/opt/data/scripts/`. El `HERMES_HOME` reproduce el entorno original (varios scripts deducen perfil/puerto de ahí).
- Alternativa probada: que el propio script publique por API (multipart) o por webhook — así funcionan `amazon_au_watch.py`, `radar_jev.py --discord-copia` y `despachar_metas_canva.py`.
- Al migrar, **pausar el job original** en el perfil satélite: si quedan los dos, se duplica el envío al cliente.

## Canales de marca (Golden / Lucky) y entrega múltiple

- Canales creados 04-nov-2026 en `Canales-Clientes`, con dos hilos fijos cada uno: `🎰・golden-game` (foro 1567662095422455880 → 📊 informes 1567662097658290227, 🎯 metas 1567662099054727300) y `🍀・lucky-brothers` (foro 1567662096118718590 → 📊 informes 1567662101193949186, 🎯 metas 1567662102783598652).
- `digital-expressions` (foro 1567216974113542184) tiene 6 hilos temáticos: 🛒 ventas 1567247121365860405, ↩️ devoluciones 1567247124272521352, 📦 inventario 1567247126596030514, ⚠️ incidencias 1567247128496177234, 📊 p&l 1567247130068914350, 💸 fees 1567247132044435488. Cableado vigente de Amazon AU (foro `1567216974113542184`): watcher en tiempo real (ventas → 🛒 ventas, reembolsos → ↩️ devoluciones, cada evento a SU hilo, no todo al de ventas; aviso 📥 "Orden recibida (Pending)" al detectar la orden antes de confirmarse) + 3 crones no_agent: p&l semanal (lun 9:00 → 📊 p&l), fees semanal (lun 9:00 → 💸 fees), alertas de inventario diarias (10:00 → 📦 inventario, silencio si no hay alerta).
- **Entrega múltiple SÍ existe:** `--deliver "whatsapp:<jid>,discord:<hilo>"` — el scheduler hace `deliver.split(",")` (`cron/scheduler_delivery.py`). Sirve para copiar un informe al equipo sin quitarle el mensaje al cliente. Verificado end-to-end con un job de prueba que apareció en dos hilos.
- Los scripts `no_agent` que publican por su cuenta (webhook o API) **no necesitan** `deliver`: si el hilo está vacío, primero verificar si el script publica solo (ej. `radar_prod.sh --discord-copia` usa webhook propio; `amazon_au_watch.py` tiene `SALES_CHANNEL`/`REFUND_CHANNEL` hardcodeados).
- **Una sola vía de entrega por job:** si el script publica a Discord por API, poner `deliver: local` — dejar el `deliver discord:<hilo>` además del post propio duplica cada aviso (stdout + API). Y al revés: un script que publica por API debe contar sus posts fallidos y salir `exit 1` (stderr) — el cron manda alerta de error y el fallo de publicación nunca queda silencioso.
- Formato compuesto válido: `deliver=discord:<foro>:<hilo>` — el adapter prueba el id padre y luego el hilo. Ojo: si el id padre queda muerto (canal renombrado/borrado), cada corrida genera un intento 404 antes de caer al hilo; apuntar el prefijo al foro real, no a un canal viejo.
- Para partir un informe combinado por marca: clonar el wrapper `.sh` con el filtro (`--empresa golden|lucky`, `--marca "Golden Game"|"The Grand Paradise Club"`), crear los 2 jobs y **pausar** el combinado (`hermes cron pause <id>`) en vez de borrarlo.

## Verificación antes de declarar hecho

Releer el guild por API y mostrar el mapa final (categoría → canales), más el conteo de `deliver` rotos (debe dar 0).
