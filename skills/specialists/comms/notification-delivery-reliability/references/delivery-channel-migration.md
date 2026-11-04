# Migrar crons a un canal de entrega estable — caso 10/09/2026

Contexto: el paquete diario del calendario de contenido (aprobación de piezas Golden/Lucky) no llegaba por WhatsApp (~15% de envíos perdidos, 2 días seguidos con el job en `ok`). El usuario decide que los crons de contenido entreguen en el canal de Discord de su bot de contenido y que las aprobaciones se den ahí.

## Hallazgos que cambiaron el plan

1. **El webhook que dio el usuario estaba a un carácter de ser válido.** `GET`/`POST` a la URL → `401 {"message":"Invalid Webhook Token","code":50027}`. Pero el ID sí existía: `(id >> 22) + 1420070400000` daba una creación minutos antes. Receta que lo resolvió:
   - `GET /guilds/{guild_id}/webhooks` (bot con `MANAGE_WEBHOOKS`, o ADMIN) devuelve **también el token** de cada webhook.
   - Localizar el objeto cuyo `id` coincide con el de la URL y hacer diff carácter por carácter: `[(i,a,b) for i,(a,b) in enumerate(zip(real,dado)) if a!=b]` → el último carácter difería (`…WuzB` pegado vs `…WuzH` real).
   - Con el token real el `POST` devolvió **204** (entregado). Lección: un `50027` se diagnostica comparando tokens, no pidiendo otra URL; solo si el `id` no aparece en el guild es que no existe / es de otro servidor.
   - El `POST` al webhook funcionó con UA de navegador y con `DiscordBot (…,1.0)` — el pitfall del UA (403/1010) aplica a la REST del bot, no al webhook.
2. **Hermes no entrega crons a una URL de webhook.** El adaptador `webhook` es solo de entrada (no implementa `send_message`); `webhook` figura en `_KNOWN_DELIVERY_PLATFORMS` de `cron/scheduler.py` pero no es un destino saliente útil. Para publicar en un canal: `deliver: discord:<channel_id>`.
3. **Identidad vs. hilo.** El webhook publicaba como "Crons de posts" (nombre propio) pero un mensaje de webhook no arrastra hilo de sesión: el reply del usuario no llega con contexto. Con el bot, sí. ⇒ si el usuario aprobará en ese canal, bot; el webhook queda para avisos de solo lectura (o hay que postearlo desde el script del job con `deliver: local`).
4. **Ruteo de la respuesta.** El canal debe estar en `discord.free_response_channels` del perfil (config.yaml) para que el reply "Dale <ID>" entre al agente por routing normal. Con `require_mention: true` el bot responde a menciones, **replies a sus propios mensajes** y comandos `/`.
5. **Permisos antes de prometer el canal.** Resolver los IDs de `free_response_channels` a nombres con `GET /guilds/{g}/channels`; confirmar `SEND_MESSAGES = 1<<11` sobre el rol del bot (`/guilds/{g}/members/{bot}` → `roles` → `/guilds/{g}/roles`). En este guild el bot tenía rol con ADMIN (`2^54-1`), así que no hubo duda.

## Datos del servidor (NeuralCrew Labs, 10/09/2026)

- guild `1493354289266167808`; bot Ragnar app `1493385610797252758`, rol `Ragnar-admin` (ADMIN).
- Canales por especialista (lote `1542126604132552714`…`1542126612915691520`): `hermodr-connect`, `brokkr-web`, **`bragi-content` = `1542126606900920340`**, `freyja-social`, `ullr-leads`, `vili-ads`, `heimdall-analytics`, `sindri-producer`; más `general` = `1493354289773674760`. Los diez + general están en `free_response_channels` del perfil default.
- Webhook "Crons de posts" (`1547588110483726338`) vive en `#bragi-content`.

## Checklist al migrar el destino de N crons

1. Resolver el ID del canal a nombre y comprobar que el remitente puede escribir (`scripts/discord_verify_webhook.py` ayuda con webhooks; para el bot basta verificar el rol).
2. Saber qué jobs son del lote (por `name`/`prompt`/`script`) y separar los "dudosos" para **preguntar**, no para asumir.
3. Decidir con el usuario si el canal viejo queda como segundo target (redundancia) o se retira (sin duplicados).
4. Backup de `jobs.json`; aplicar con la tool de cron (`action=update job_id=… deliver=…`), no editando el JSON a mano.
5. Verificar por job: disparar a mano (`action=run`) y confirmar llegada real al canal; cerrar con una prueba end-to-end del flujo completo (aquí: aprobar una pieza y verla publicada).
6. Reportar al usuario qué jobs siguen entregando por el canal viejo, si alguno queda.
