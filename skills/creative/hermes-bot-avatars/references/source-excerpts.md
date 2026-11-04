# Extractos verificados — mecanismo de avatar de perfiles Hermes (26/08/2026)

Fuentes: instalación `/opt/hermes` (v0.20.x), servidor Docker VPS, gateway `gateway-default` bajo s6.

## RPC `profiles.set_asset` / `profiles.get_asset`

Implementación: `tui_gateway/methods_profiles.py`. Registradas en `tui_gateway/server.py`
como métodos pesados (corren fuera del reader thread WS: `profiles.configure`, `profiles.create`,
`profiles.describe`, `profiles.get_asset`, `profiles.list`, `profiles.set_asset`, `image.generate`...).

### set_asset (resumen fiel)
- Params: `name` (perfil), `asset` (solo `"avatar"`), `data` (data URL o base64 crudo), `clear: true` para borrar.
- Escribe atómicamente `assets/<asset>.<ext>` DENTRO del directorio del perfil — server-side, para que
  todo cliente conectado vea la misma imagen vía `get_asset`.
- Decodifica con `base64.b64decode(validate=True)`; rechaza > 2_000_000 bytes.
- Valida magic bytes (no confía en el mime declarado): PNG `\x89PNG\r\n\x1a\n`, JPEG `\xff\xd8\xff`, WEBP `RIFF....WEBP`.
- Borra las demás extensiones del mismo asset antes de escribir (canónico = un archivo).
- `clear` → elimina `assets/avatar.{png,jpg,webp}` y devuelve `{ok, asset, size:0, removed}`.

### get_asset (resumen fiel)
- Params: `name`, `asset` (default `"avatar"`).
- Recorre `{png, jpg, webp}` en ese orden, lee el archivo del disco en CADA llamada
  (sin caché server-side) y devuelve `{found, mime, size, data: "data:<mime>;base64,..."}`.
- `found: false` cuando no existe (no es error) — los roster UIs lo usan como probe barato.

## Dónde NO está el avatar (diagnóstico)
- `web_server.py` / `web_routers/profiles.py`: no hay endpoint de avatar ni mount de assets de perfiles.
  El dict de perfil (`_profile_to_dict`) solo trae name/path/model/description/display_name/... — sin imagen.
- Bundle JS del dashboard (`web_dist/assets/*.js`): no hay referencias a `avatar` ni rutas de imagen de perfil.
  El roster de Bots es un plugin del desktop app (`apps/desktop/src/plugins/hermes-bots/plugin.js`), no del backend.
- Doc oficial Bot Mode: «A Bot's look, title, and description are stored in the profile's metadata on the backend,
  so the same Bot appears the same way on every desktop connected to that backend.» → el look/avatar se persiste
  server-side y el desktop lo lee por RPC; el archivo canónico es `assets/avatar.<ext>`.

## ui_meta / hermes-bots
- `profile.yaml` → `ui_meta` guarda metadata del look del bot (título, descripción, ocultado, rostro geométrico...).
- Bot Mode marca perfiles con `ui_meta.hermes-bots` (bloque dict). `tools/bot_mode_probe.py` lo usa para decidir
  si inyecta el protocolo «Messaging other agents» (título canónico de sesión `Bot Chat`) en la Bot Chat.
- El TUI gateway permite `profiles.configure` con `ui_meta` (merge key-wise; key `None` borra; cap ~64 KB).

## Lecciones del flujo de diagnóstico
1. Primero verificar el archivo en disco + md5 — si está en `assets/avatar.<ext>`, el servidor lo sirve.
2. No buscar endpoints REST de avatar en el backend web: no existen.
3. El «no se ve» casi siempre es caché del CLIENTE Desktop → reconnect o Edit Profile → subir imagen (fuerza set_asset).
4. Backup antes de reemplazar (`cp` a `backup-<ts>/`); permisos hermes:hermes (uid 10000 en Docker).
5. `os.chown` desde el contenedor como hermes falla con `Operation not permitted` — no es necesario:
   `shutil.copy2` conserva el propietario del proceso (hermes) al escribir sobre el destino.
