---
name: hermes-bot-avatars
description: "Use when setting or fixing a Hermes bot avatar image."
tags: [hermes, avatar, bots, desktop, perfiles, imagen, rpc]
version: 1.0.0
author: Ragnar
triggers:
  - avatar bot / avatar perfil / foto de perfil de bots / cambiar avatar / subir imagen de perfil
  - no se ven los avatares / no se reflejan / no se ven reflejados tras copiar imagenes
  - hermes desktop bot mode rostros / roster avatares / bot avatar
---

# Hermes bot/profile avatars — Hermes Desktop / Bot Mode

## Cuándo usar
- Poner o reemplazar la imagen de perfil (avatar) de un perfil Hermes / bot que aparece en Hermes Desktop (Bot Mode, pestaña Bots / roster).
- El usuario reporta «copié las imágenes pero no se ven reflejadas» tras editar archivos server-side.
- Auditar por qué un bot muestra la cara determinista (blob/geométrica) en vez de la imagen esperada.

## Mecanismo canónico (verificado 26/08/2026, Hermes v0.20.x, VPS Docker)
- El avatar de un perfil ES un archivo en el home del perfil:
  `HERMES_HOME/profiles/<name>/assets/avatar.<ext>` con ext ∈ {png, jpg, webp} — un único archivo canónico por asset.
- El gateway lo sirve por RPC:
  - `profiles.get_asset` {name, asset="avatar"} → devuelve data URL leyendo el archivo del disco EN CADA llamada. **Sin caché server-side.**
  - `profiles.set_asset` {name, asset="avatar", data=<dataURL|base64>} → valida magic bytes (PNG/JPEG/WebP), rechaza blob >2 MB, escribe atómicamente `assets/avatar.<ext>` y borra las demás extensiones del mismo asset. `clear: true` elimina `assets/avatar.*`.
  - Implementación: `tui_gateway/methods_profiles.py`; registradas en `tui_gateway/server.py` junto a métodos pesados (fuera del reader thread WS).
- El resto del «look» del bot (título/descripción/ocultado/rostro geométrico) vive en `profile.yaml` → clave `ui_meta`. Bot Mode marca perfiles con `ui_meta.hermes-bots` (lo usa `tools/bot_mode_probe.py` para el protocolo «Messaging other agents» en la Bot Chat canónica).
- El API web (`/api/profiles`, web_server.py) NO expone endpoint de avatar y no monta los assets de perfiles — no perder tiempo buscándolo; la vía es el RPC del gateway o el archivo directo.

## Flujo probado para aplicar imágenes nuevas
1. Obtener las imágenes (p. ej. generación IA vía perfil Producer o skill de imagen; o contact sheet como guía).
2. Verificar correspondencia dios/bot ↔ imagen con `vision_analyze` (cerrar con «¿corresponde a X?» y comprobar atributos: armadura alada, arpa, gatos, cuerno, arco, forja…).
3. Backup previo + copiar al lugar canónico con permisos del usuario del gateway (uid hermes/10000 en Docker):
   - backup: `cp <dest>/avatar.png <backup-dir>/<name>-avatar.png.bak` (o `shutil.copy2`)
   - copiar: `cp <src>.png profiles/<name>/assets/avatar.png` (+ opcional `avatar-<name>.jpg` descriptivo)
4. Verificar md5 origen↔destino para todos los perfiles.
5. Confirmar permisos legibles (`ls -la` → hermes:hermes) y tamaño < 2 MB.

## Pitfall #1 — el Desktop cachea el roster (causa #1 de «no se ve»)
Servidor: `get_asset` lee disco cada vez → los archivos nuevos YA se sirven. Cliente: Hermes Desktop cachea el roster/avatares al cargar y no re-pide hasta reconectar. Fix:
- Reconectar la conexión al gateway (Settings → Connections → Reconnect) o cerrar/reabrir Hermes Desktop.
- Vía 100% garantizada: clic derecho en el bot → **Edit Profile → avatar → subir la imagen** (fuerza `profiles.set_asset` + refresco inmediato del roster).
- NO hace falta reiniciar el gateway ni `hermes-serve` por cambiar un archivo de avatar.

## Pitfall #2 — límites y formatos
- Máx 2 MB (blob decodificado); solo PNG/JPEG/WebP (verifica magic bytes, no confía en el mime declarado).
- PNG 1024×1024 de flux ≈ 760–800 KB → OK.
- `set_asset` borra extensiones hermanas del mismo asset (canónico = un archivo). Si reemplazas a mano y quedan `avatar.jpg` + `avatar.png`, `get_asset` elige por orden de extensión (png → jpg → webp); dejar solo la que quieras.
- No cambiar `ui_meta` para la imagen: eso es metadata del look, no el archivo.

## Verificación sin Desktop
- `ls -la profiles/<name>/assets/` + `md5sum` contra el origen.
- Prueba del servidor: invocar RPC `profiles.get_asset` por el gateway → `{found: true, mime, size, data}`.

## Referencias
- `references/source-excerpts.md` — extractos verificados de `set_asset`/`get_asset` y del rastro de diagnóstico.