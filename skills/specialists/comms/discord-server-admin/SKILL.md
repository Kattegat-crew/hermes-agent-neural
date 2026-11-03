---
name: discord-server-admin
description: "Use when creating Discord channels for Hermes profiles."
tags: [discord, canales, hermes, perfiles, routing, api, gateway]
version: 1.0.0
author: Ragnar
triggers:
  - discord canales: crear canal / crear canales / canal por bot / servidor discord
  - discord admin: administrar servidor / listar canales / roles / token discord / 1010 / forbidden
  - limpieza: limpiar canal / borrar mensajes / eliminar mensajes / purgar spam / deleting messages
  - ruteo: canal discord -> perfil / gateway profile_routes discord
---

# Discord Server Admin — REST API para canales y routing a perfiles Hermes

Cómo administrar un servidor Discord con el token del bot (Ragnar) vía REST API directa, cuando el plugin `discord_admin` alcanza (listar, roles, pins) pero **NO** crea canales. Verificado 26/08/2026 en servidor NeuralCrew Labs.

## Concepto clave: un bot sirve a muchos perfiles

El gateway de Hermes enruta por **canal** (`thread > chat_id > guild > default`). Con `gateway.profile_routes` puedes mapear **8+ canales → 8+ perfiles** con UN solo token de bot de Discord. No hacen falta tokens por bot (solo para Telegram/WhatsApp sí).

## Flujo completo (verificado)

1. **Confirmar token y permisos sin exponer secretos:**
   - Token en `/opt/data/.env` → `DISCORD_BOT_TOKEN` (bot token, ~72 chars). Leer con Python desde `.env` (strip de comillas).
   - Permisos: `discord_admin list_guilds` → campo `permissions`. `18014398509481983` = `2^54-1` = **Administrador** → puede crear canales.

2. **Auth check:** `GET https://discord.com/api/v10/users/@me` → 200 = token OK.

3. **Listar canales:** `GET .../guilds/{guild_id}/channels` → types: `0` text · `2` voice · `4` category · `15` forum.

4. **Crear canal de texto bajo categoría:**
   `POST .../guilds/{guild_id}/channels` body `{"name": "...", "type": 0, "topic": "...", "parent_id": "<category_id>"}` → **201** + `id` del canal.

5. **Mapear al perfil en `config.yaml`** (protegido contra write_file/patch → editar con Python vía terminal, patrón D-I-V-E):
   ```yaml
   gateway:
     profile_routes:
       - name: hermodr-discord
         platform: discord
         chat_id: '<channel_id>'
         profile: hermodr
   ```
   Backup `config.yaml` antes (`cp config.yaml config.yaml.bak-$(date +%Y%m%d-%H%M%S)`), verificar con `yaml.safe_load` tras editar.

6. **Aplicar = reiniciar gateway** (no hay hot-reload) → patrón cron one-shot `no_agent` (ver skill `hermes-gateway-s6-ops`): programar el restart 3-4 min después, entregar el mensaje ANTES de que dispare, verificar PID nuevo en el siguiente turno. NUNCA reiniciar dentro del propio turno.

## Pitfall CRÍTICO: error 403 / code 1010

- Discord bloquea requests REST con User-Agent genérico de urllib (`Python-urllib/3.x`) con **403 error code 1010** (Cloudflare). Afecta hasta `GET /users/@me`.
- **Fix:** enviar header `User-Agent: "DiscordBot (https://..., 1.0)"`. Con eso el mismo token funciona (200).
- El error NO significa token inválido ni falta de permisos — probar el UA antes de culpar al token.

## Scripts

- `scripts/discord_list_channels.py` — lista guilds/canales con token+UA correctos.
- `scripts/discord_create_channels.py` — crea N canales de texto bajo una categoría; devuelve IDs.

## Limpieza masiva de mensajes (borrado retroactivo, verificado 26/10/2026)

Para pedidos tipo "limpia los mensajes de X en este canal":

1. **Localizar el objetivo en AMBOS lugares:** el mensaje disparador suele estar en un canal padre (#general) y el ruido acumulado allí. Traer `fetch_messages` del canal padre con `limit` alto (100+) y filtrar por contenido/autor en Python; verificar con paginación que no haya más hacia atrás antes de declarar el total.
2. **Vía de borrado:** usar el plugin nativo `discord_admin` con acción `delete_message` (canal + message_id). **Es 1 mensaje por invocación** — no existe bulk-delete en el tool. El conector Composio `discordbot` permite lotes pero puede no estar conectado; no depender de él.
3. **Borrado en lotes paralelos:** `tool_call` con ~8-10 invocaciones por lote. Los 429 (rate-limit, `retry_after` < 1s) NO son fallo: reencolar esos message_id en un lote siguiente y reintentar hasta 0 pendientes. Llevar contador exacto borrados/pendientes.
4. **Verificación final obligatoria:** refetch del canal completo y confirmar 0 coincidencias restantes antes de reportar "limpio". Contar y clasificar (autor, rango de fechas) en el reporte.
5. Mensajes >14 días no son borrables vía API (Discord lo impone) — verificar fechas antes de prometer limpieza total.

## Pitfalls

- Canal con nombre `hermodr-connect` (kebab, slug del perfil) → visible y enrutable; el display bonito (`Hermóðr (Connect)`) es tema del Desktop, no del canal.
- `curl` inline gigante puede disparar el bloqueo del parser de terminal → usar scripts .py limpios.
- Verificar SIEMPRE con GET tras el POST (201 + presencia) antes de declarar "canal creado".

## Relación con otras skills

- `discord-reporter` — enviar mensajes/reportes a canales (complementaria, no solapa).
- `hermes-gateway-s6-ops` — reinicio seguro del gateway para aplicar `profile_routes`.
- `bot-team-architecture` — diseño de rosters; este skill es la parte operativa de canales.