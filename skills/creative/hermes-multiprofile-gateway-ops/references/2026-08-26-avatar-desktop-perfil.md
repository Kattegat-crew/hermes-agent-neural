# 26/08/2026 — Avatar de perfil en Hermes Desktop (assets/avatar.png)

## Contexto
El usuario pidió usar las imágenes COMPLETAS generadas por Sindri (1024×1024, retratos
épicos de los 8 dioses) como avatares de los bots en Hermes Desktop, usando el
contact_sheet_tripulacion.png como guía de cuál va en cada uno. Antes estaban instalados
recortes 512×512 de dominio público (set_avatars.py).

## Mecanismo (verificado en código)
- Desktop **NO tiene endpoint de avatar**: `_profile_to_dict` (web_server.py:14580) no
  expone campo avatar; no hay ruta `/api/profiles/{name}/avatar` en web_routers/profiles.py.
  La UI lee el archivo directamente del directorio del perfil.
- Ruta canónica: `profiles/<name>/assets/avatar.png` (+ opcional `avatar-<name>.jpg`
  descriptivo). Reemplazar ese archivo = nuevo avatar; un refresh de la lista de bots basta
  (sin reinicio de nada).

## Paso a paso (validado end-to-end)
1. **QA visual previo**: `vision_analyze` cada imagen contra el dios/módulo ANTES de
   instalar (8/8 correctas; Vili fue la única sin señal mitológica única — usar la que
   Sindri generó con ese nombre, decision del usuario).
2. **Backup**: copiar `avatar.png` actual a `backup-<ts>/<dios>_avatar.png.bak` antes de
   sobrescribir.
3. **Mapa slug→archivo**: hermodr_connect.png, brokkr_web.png, bragi_content.png,
   freyja_social.png, ullr_leads.png, vili_ads.png, heimdall_analytics.png,
   sindri_producer.png.
4. `shutil.copy2(src, assets/avatar.png)` + `copy2(src, assets/avatar-<dios>.jpg)`.
5. **NO llamar `os.chown`**: como usuario hermes no-root lanza
   `PermissionError: [Errno 1] Operation not permitted`. `copy2` como hermes preserva el
   owner (los archivos ya son hermes:hermes, uid 10000 = usuario del gateway).
6. **Verificar**: `md5sum` coincide con la fuente + `ls -la` permisos legibles por hermes.

## Pitfalls
- `os.chown` como hermes → EPERM. Omitirlo; solo se necesita chown si el proceso es root
  y el dir es de otro usuario.
- Comparar **md5**, no solo tamaño: un avatar.png con distinto hash = sigue la imagen vieja.
- El Desktop cachea en cliente; si no refresca tras cambiar el archivo, recargar la vista o
  reiniciar `hermes-serve` (9112) — el archivo en disco es la fuente de verdad.