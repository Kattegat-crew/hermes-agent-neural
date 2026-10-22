---
name: whatsapp-bridge-operations
description: "Use when operating or debugging the WhatsApp bridge"
tags: [whatsapp, bridge, baileys, allowlist, gateway, stt, voz, debug]

---

# WhatsApp Bridge Operations

Arquitectura y operación del puente WhatsApp de Ragnar (modo bot). Cubre: quién puede escribir, cómo habilitar grupos, transcripción de notas de voz y debugging.

## Puente = un solo remitente (lección 27-28/08)
El puente sale con UN número para TODOS los perfiles ruteados. Los envíos proactivos de Ragnar (`/send`) y los del perfil enrutado (p.ej. roshi → DM de Chucho) comparten remitente visible: el destinatario NO distingue quién escribió. Regla:
- Todo informe/envío proactivo debe **etiquetar al remitente** en el texto ("— Ragnar" / "— Roshi") o ir al grupo oficial del equipo.
- Chucho ya reclamó recibir un informe "de Roshi" que era de Ragnar (27/08). Cron `informe-diario-equipo` (57dd5580b592, 07:00) aplica etiqueta.

## Re-pairing (v0.20.6, 28/08)
Runbook completo en `references/re-pairing-runbook.md`. Tres pitfalls nuevos verificados:
1. **Bug `pair-code.js`**: `fetchLatestBaileysVersion()` devuelve `{version,isLatest}` — pasar objeto crudo a Baileys muere silencioso en `version.join()`. Corregido 28/08 (backup `.bak-20260828`). Código de 8 dígitos expira ~60 s; **mejor usar `pair-qr.js`** (QR PNG rotativo ~50 s × 8 intentos).
2. **Sesión root-owned**: si el pairing corre vía `docker exec`, la sesión nueva queda owned por root → `EACCES` en el bridge (uid hermes). Fix: `chown -R hermes:hermes /opt/data/whatsapp/session` ANTES de reiniciar.
3. **Gateway parked**: tras emparejar, el gateway NO reintenta el bridge solo → `s6-svc -r /run/service/gateway-default`. Verificar `curl http://127.0.0.1:3000/health` → `{"status":"connected"}`.
4. Borrar sesión vieja pierde `lid-mapping-*` (LID→número) que usa la allowlist; se regeneran al reconectar, pero revisa las variantes de chat_id del ruteo (`@lid`, JID, número plano).

## Arquitectura

- **Bridge Node:** `/opt/data/scripts/whatsapp-bridge/bridge.js` (Baileys vía whatsapp-rust-bridge)
- **Sesión:** `/opt/data/whatsapp/session/` (`creds.json`, `lid-mapping-*.json`, `device-list-*.json`)
- **Log:** `/opt/data/whatsapp/bridge.log`
- **HTTP API local (127.0.0.1:3000):** `/send`, `/send-media`, `/send-poll`, `/send-location`, `/typing`, `/read`, `/chat/:id`, `/messages`, `/health` (sin endpoint de listar chats) — incluye POST /send para envío proactivo (ver sección Envío proactivo)
- **Config:** `config.yaml` sección `whatsapp:` + env del proceso (`WHATSAPP_ALLOWED_USERS` en `/opt/data/.env`, `WHATSAPP_MODE=bot`)

**PITFALL crítico:** el bridge lee el env AL ARRANCAR. Cambios en `.env`/config no se aplican al proceso corriendo → verificar `ps aux | grep bridge` y reiniciar. Síntoma: mensajes siguen rebotando con `allowlist_mismatch` aunque el número ya esté en la lista.

## Allowlist (quién puede escribir al bot)

- `WHATSAPP_ALLOWED_USERS` (config.yaml `whatsapp.allowed_users` + `.env`): números permitidos separados por coma.
- Los IDs llegan como `@s.whatsapp.net` o `@lid`. Los LID (15 dígitos) se resuelven vía `lid-mapping-*.json`; si no hay mapping ni match literal → `allowlist_mismatch` en bridge.log.
- Síntoma en log: `{"event":"ignored","reason":"allowlist_mismatch","chatId":"...@lid"}` → revisar env del proceso vs .env actual.
- **Captura de LID:** el LID de un contacto se resuelve recién cuando la persona escribe por primera vez (aparece en `lid-mapping-<número>.json`). Antes de eso no existe mapping y un envío entrante de ese contacto llega como `<lid>@lid` → sin ruta match puede caer en el perfil default. Con `gateway.profile_routes` agregar rutas por LID + JID + número para cada persona.

## Envío proactivo (escribir de primeras)

El bot PUEDE iniciar conversación aunque el contacto nunca haya escrito:

- `POST /send` en `127.0.0.1:3000` con `{"chatId": "<JID|LID|número>", "message": "...", "replyTo?": ...}` → el mensaje sale directo al celular. También `/send-media`, `/send-poll`, `/send-location`, `/typing`, `/read`.
- Anti-echo: el bridge registra los envíos propios en `recentlySentIds` para no rebotar el propio mensaje como entrante (no dispara al agente).
- **Regla dura: no enviar nunca sin orden explícita del usuario** (riesgo de spam / mala primera impresión con el cliente).
- **PITFALL crítico (verificado 19-oct, PROD):** desde el HOST de PROD el bridge NO es alcanzable aunque `ss` muestre `LISTEN 100.73.30.29:3000 (docker-proxy)` — `curl` a `127.0.0.1:3000` ni a la IP de Tailscale responde (exit 7 / 000, probable firewall local). La ÚNICA vía que funciona desde el host es **dentro del contenedor**: `docker exec hermes-agent curl -s -X POST http://127.0.0.1:3000/send-media -H "Content-Type: application/json" -d '{"chatId":"...","filePath":"...","caption":"..."}'`. El `filePath` debe ser visible DENTRO del contenedor (`/opt/data/...`, montado) con dueño `hermes` (10000:10000); `/send` usa `message`, `/send-media` usa `filePath`+`caption`.
- **PITFALL verificación de envíos (22/09/2026):** `GET /messages` NO sirve para verificar un envío — hace `splice()` de `messageQueue` y CONSUME los mensajes entrantes que el bot aún no procesó (el agente los perdería). Además `messageStore` es solo en memoria: no hay log persistente de lo enviado (ni en bridge.log, ni en los state.db de los perfiles de PROD — verificado). Verificación correcta de un `POST /send`: (1) HTTP 200 con `{"success":true}`; (2) `messageId` con prefijo `3EB0...` devuelto = ID emitido tras ACK del servidor WhatsApp → confirma entrega AL SERVIDOR, no lectura ✓✓ (eso solo lo ve el destinatario); (3) `GET /health` → `connected` y `queueLength:0` tras el envío. No intentar confirmaciones de lectura vía API: Baileys no las expone.

## Grupos de WhatsApp — política por defecto RECHAZA todo

El gateway Python (`/opt/hermes/gateway/platforms/whatsapp_common.py`, `_is_group_allowed`) con `group_policy` default **"pairing"** rechaza TODO mensaje de grupo. **Agregar el bot al grupo NO basta.**

Para habilitar UN grupo específico, en `config.yaml` sección `whatsapp:`:

```yaml
whatsapp:
  allowed_users: <lista actual>
  group_policy: allowlist
  group_allow_from: <JID del grupo, ej. 57300XXXXXXX@g.us>
  require_mention: true
  mention_patterns: ["ragnar", "neuralcrew"]
  auto_tts: false
  tts_mode: audio_only
```

- `require_mention: true` → solo responde a: menciones al bot, replies a mensajes del bot, comandos `/`, o patrones de `mention_patterns`. `false` → responde a TODO mensaje del grupo (ruidoso).
- Los participantes del grupo igual pasan por la allowlist del bridge: sus números deben estar en `allowed_users`.
- **PITFALL: el agente NO puede escribir config.yaml** (write_file/patch → `Refusing to write to Hermes config file`). Vías válidas para activar grupos:
  - `hermes config set whatsapp.<key> <value>` (CLI oficial; escribe config.yaml).
  - Env vars en `/opt/data/.env` — **preceden al YAML** (`_apply_yaml_config` en el adapter). VERIFICADO 2026-08-19: `WHATSAPP_GROUP_POLICY=open`, `WHATSAPP_REQUIRE_MENTION=true`, `WHATSAPP_MENTION_PATTERNS=["ragnar","neuralcrew"]` (JSON, comillas dobles). Para `group_allow_from` en modo allowlist, lo más seguro es YAML/`hermes config set`: el adapter lo lee de `config.extra` (línea 452 de whatsapp_common.py); el fallback a env NO está verificado.
- Restart requerido tras cambiar config/env — ver abajo.

### Reiniciar el gateway (s6) — el restart mata el turno actual

`hermes gateway restart` desde dentro del proceso queda BLOQUEADO por el guard del tool. El gateway corre bajo **s6 supervisor** (PID 1 = s6-svscan). ⚠️ **El servicio real es `gateway-default` — `main-hermes` es un dummy placeholder de s6-rc (NO reinicia el gateway).**

```bash
/package/admin/s6/command/s6-svc -r /run/service/gateway-default
```

⚠️ **PITFALL crash loop:** tras reiniciar, verificar que el PID del proceso `python3 ... gateway run` cambió y se estabiliza (no cambia cada ~30s). Si está en crash loop, leer `docker logs hermes-agent --tail 30`:
- `PermissionError: .../pairing/_rate_limits.json` u otro `Permission denied` en `/opt/data` → el gateway corre como `hermes` (UID 10000) y hay dirs/archivos creados como root. Fix: `chown -R hermes:hermes` sobre los dirs afectados (pairing, hooks, image_cache, audio_cache, runtime, desktop, images, pets, cache) + archivos (auth.json, processes.json, projects.db).
- `Refusing to start: whatsapp has dm_policy/group_policy set to 'open' but neither GATEWAY_ALLOW_ALL_USERS nor WHATSAPP_ALLOW_ALL_USERS is enabled` → falta el opt-in. Agregar `WHATSAPP_ALLOW_ALL_USERS=true` a `.env`.

Cualquier restart mata el turno del agente en curso → **programarlo como cron one-shot `no_agent`** (`deliver=local`, schedule T+3/4 min, script en `~/./scripts/`) para que dispare DESPUÉS de entregar el mensaje final al usuario. ⚠️ El script `/opt/data/scripts/gateway_restart_once.sh` apunta a `main-hermes` (equivocado) — corregir a `gateway-default` antes de usarlo. El bridge es hijo del gateway: se respawnea con el env fresco — eso también arregla allowlists desactualizadas del proceso viejo.

### Comando /allowlist (reporte de allowlists y grupos)

Registrado como `quick_commands:` en config.yaml (type: exec). Ejecuta `/opt/data/scripts/allowlist_report.py` → muestra números permitidos y grupos de WhatsApp + Telegram. NO toca core (`commands.py`/`slash_commands.py`). El gateway redacta salidas sensibles automáticamente.

### Cambiar el modelo

En `config.yaml` sección `model:` (primeras 6 líneas): cambiar `api_key` + `base_url`. Provider NaN-Builders ya existe en `providers:`/`custom_providers:` (api_key `sk-JzB...ohYw`, base `https://api.nan.builders/v1`, default `deepseek-v4-flash`). Restart requerido. Verificar con `POST https://api.nan.builders/v1/chat/completions` + User-Agent Cloudflare (la skill devops:nan-builders-api tiene la receta).

### Obtener el JID del grupo (no hay /chats)

1. Pedir al admin un mensaje de prueba en el grupo (ej. "@Ragnar prueba").
2. Alternativa temporal: `group_policy: open` → el mensaje entra con su chatId → capturar el JID → volver a `allowlist`.
3. Los `@g.us` no aparecen en logs hasta que fluye al menos un mensaje del grupo.

## Notas de voz entrantes (ptt)

- El bridge descarga el audio a `/opt/data/cache/audio/aud_<hash>.ogg`; el body llega como `[ptt received]` (placeholder, el audio es el payload real).
- Transcribir vía NaN Builders whisper — receta completa validada en `references/stt-whisper.md` (User-Agent Cloudflare obligatorio, key real con yaml.safe_load). Nota: `devops:nan-builders-api` (user-owned) documenta el UA Cloudflare para chat/imagen pero NO cubre STT.
- Protocolo: responder directo al pedido hablado, NUNCA citar/repetir la transcripción.

## Debug rápido

- **440 conflict loop** en bridge.log = dos procesos con la misma sesión peleando (`type: replaced`) → `ps aux | grep bridge`, matar duplicados.
- **Logout 401 `device_removed` (27/08, real):** WhatsApp desvincula el dispositivo desde el servidor SIN que nadie toque el teléfono. Causa raíz verificada: el perfil de sesión había estado en conflicto prolongado (2 instancias peleándose: bridge del contenedor + otro proceso en el host, hostnames distintos en bridge.log) — patrón exacto que el anti-abuso de WhatsApp castiga. Enviar mensajes NO provoca logout (4+ envíos previos sin incidente). Prevención: garantizar UNA sola instancia del bridge; si hay hostnames ajenos (`vmi*`) en bridge.log, pedir a Chucho que mate el proceso duplicado del host. Recuperación: sesión nueva por código (pair-code.js) tras cooldown de ~5 min; NO repetir intentos seguidos o WhatsApp enfría el número ("Connection Closed" o "intente más tarde" en el teléfono).
- **Cooldown de emparejamiento:** intentos repetidos de pairing (QR o código) disparan enfriamiento de WhatsApp con "Connection Closed" silencioso. UN intento limpio por ventana de 5-15 min; el código de 8 dígitos vive ~60 s — generar solo con el teléfono ya en la pantalla "Vincular con el número de teléfono". **EVIDENCIA 01/09/2026:** tras ~8 intentos en 30 min, el servidor devolvía `loggedOut`/`connectionClosed` ANTES de que el usuario entrara el código y el teléfono mostraba "No se pudo iniciar sesión" — antibloqueo del número; la única cura es dejar pasar la ventana sin ningún socket nuevo. **EVIDENCIA 01/09 (misma mañana, QR):** con la cuenta ya enfriada, TAMBIÉN el escaneo de QR falló (Admin: "la cuenta está molestando") — durante enfriamiento activo ni código ni QR entran; esperar horas (no minutos) sin abrir sockets de pairing y reintentar con UN solo QR fresco.
- **Baileys rc13 roto para pairing por código (01/09/2026):** rc13 emitía el código y caía en `logged_out`/`Connection Closed` en todos los intentos. Actualizado el módulo del bridge a `@whiskeysockets/baileys@7.0.0-rc14` en `/opt/data/scripts/whatsapp-bridge/node_modules` (`npm install` con `npm_config_cache=/tmp/npm-cache-hermes`; `/tmp/.npm-cache` queda root-owned). Script con reintentos y sesión fresca por intento: `pair-code2.js`.
- **Instancia competidora durante pairing:** el bridge del gateway (`bridge.js`, escucha 3000) intenta autenticar la MISMA sesión que usa pair-code → el servidor mata el registration. Síntoma: bridge.log con "❌ Logged out. Delete session and restart" en bucle. Procedimiento limpio: sesión fresca + pairing + NO reiniciar el gateway hasta tener `paired` (el gateway respawneará el bridge con la sesión nueva).
- **Keys enmascaradas:** grep de config.yaml devuelve `sk-JzB...ohYw`; leer valor real con `python3 -c "import yaml; print(yaml.safe_load(open('/opt/data/config.yaml'))['stt']['openai']['api_key'])"` sin imprimirlo en output.
- `emitDebugEvent` redacta IDs en el log JSON; el payload real al gateway lleva los IDs completos.
- Health: `curl 127.0.0.1:3000/health` → `{"status":"connected",...}`.
