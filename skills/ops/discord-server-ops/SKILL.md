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

| Acción | Llamada |
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
- `digital-expressions` (foro 1567216974113542184) tiene 5 hilos temáticos: 🛒 ventas 1567247121365860405, ↩️ devoluciones 1567247124272521352, 📦 inventario 1567247126596030514, ⚠️ incidencias 1567247128496177234, 📊 p&l 1567247130068914350, 💸 fees 1567247132044435488.
- **Entrega múltiple SÍ existe:** `--deliver "whatsapp:<jid>,discord:<hilo>"` — el scheduler hace `deliver.split(",")` (`cron/scheduler_delivery.py`). Sirve para copiar un informe al equipo sin quitarle el mensaje al cliente. Verificado end-to-end con un job de prueba que apareció en dos hilos.
- Los scripts `no_agent` que publican por su cuenta (webhook o API) **no necesitan** `deliver`: si el hilo está vacío, primero verificar si el script publica solo (ej. `radar_prod.sh --discord-copia` usa webhook propio; `amazon_au_watch.py` tiene `SALES_CHANNEL`/`REFUND_CHANNEL` hardcodeados).
- Para partir un informe combinado por marca: clonar el wrapper `.sh` con el filtro (`--empresa golden|lucky`, `--marca "Golden Game"|"The Grand Paradise Club"`), crear los 2 jobs y **pausar** el combinado (`hermes cron pause <id>`) en vez de borrarlo.

## Verificación antes de declarar hecho

Releer el guild por API y mostrar el mapa final (categoría → canales), más el conteo de `deliver` rotos (debe dar 0).
