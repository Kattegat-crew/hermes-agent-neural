---
name: bot-avatar-config
description: "Use when installing crew avatars or refreshing Desktop"
tags: [avatares, bot-avatar, perfiles-hermes, hermes-desktop, pillow, qa-visual, discord]
category: neuralcrew-ops
version: 1.0.0
---

# Bot avatar config (flota NeuralCrew)

Arquitectura verificada 2026-08-26 en el deploy `/opt/data`. Cada "bot" crew es un **perfil Hermes**, no un bot de Discord separado.

## Dónde vive el avatar de cada bot
- Perfiles: `/opt/data/profiles/<bot>/` con bots `bragi, brokkr, freyja, heimdall, hermodr, sindri, ullr, vili` (+ roshi, comms, vigia).
- **Avatar canónico** (el que pinta Hermes Desktop): `/opt/data/profiles/<bot>/assets/avatar.png` (512×512 PNG).
- **Tarjeta grande**: `/opt/data/profiles/<bot>/assets/avatar-<bot>.jpg` (1024×1024 JPEG q92).
- Bot Mode: la app desktop "hermes-bots" se detecta por `ui_meta.hermes-bots` en `profile.yaml`; lee/escribe avatares server-side vía JSON-RPC `profiles.get_asset` / `profiles.set_asset`.
- `has_avatar` (que reporta `profiles.list`) = existe `assets/avatar.{png,jpg,webp}`.

## Instalar / reemplazar un avatar
1. **Backup previo**: copia `avatar.png` y `avatar-<bot>.jpg` a un dir con fecha (ej. `deliverables/<proyecto>/backup-assets-YYYYMMDD/`).
2. Redimensionar desde el render fuente (1024×1024): `avatar.png` → 512×512 PNG `optimize=True`; `avatar-<bot>.jpg` → 1024×1024 JPEG `quality=92`.
3. Verificar dimensiones post-escritura (ver comando abajo).
4. QA visual con `vision_analyze` sobre el `avatar.png` instalado (identidad correcta del personaje).

## Verificar con Pillow (el python del sistema NO trae PIL)
```bash
cd /opt/data && UV_CACHE_DIR=/tmp/uvcache uv run --with pillow python3 - <<'EOF'
from PIL import Image
im = Image.open('/opt/data/profiles/<bot>/assets/avatar.png')
print(im.size)  # debe dar (512, 512) para avatar.png, (1024, 1024) para avatar-<bot>.jpg
EOF
```
`/opt/data/.cache/uv` no es escribible → siempre usar `UV_CACHE_DIR=/tmp/uvcache`.

## Por qué Hermes Desktop no muestra la imagen nueva
- El servidor **NO cachea**: `profiles.get_asset` lee el archivo del disco en cada llamada. No hay evento de refresco emitido por el servidor.
- La caché está en el **cliente** (roster en memoria): hay que recargar/reconectar la app para que vuelva a pedir `profiles.list` + `get_asset`.
- Si tras recargar persiste: preguntar al usuario DÓNDE exactamente no se ve (lista lateral / chat / ajustes del perfil) y si antes veía los avatares viejos; verificar de nuevo el sha256 del archivo en disco (puede haber otro proceso sobrescribiendo).

## Discord: un solo bot real
- En el guild NeuralCrew Labs solo hay UN bot miembro: **"Ragnar"** (id `1493385610797252758`). Los 8 crew NO son miembros separados de Discord; cambiar su avatar real = PATCH REST `/users/@me` con el token del bot.
- `DISCORD_BOT_TOKEN` vive en `/opt/data/profiles/{roshi,comms,vigia}/.env` (los `.env` de los perfiles crew están vacíos). Token también disponible vía `curl -H "Authorization: Bot $DISCORD_BOT_TOKEN" https://discord.com/api/v10/users/@me`.

## Relacionados
- `quality-check-visual` — QA de retratos generados (contar manos, objetos fusionados al cuerpo, verificar etiqueta↔imagen en contact sheets). Su sección "Prompts endurecidos" aplica antes de instalar.
- `inspecting-hermes-desktop-dom` — si el Desktop corre en la misma máquina (CDP en `127.0.0.1:9222`), se puede inspeccionar el DOM en vivo; en deploys remotos el Desktop no es visible desde el servidor.

## Referencias absorbidas

- `references/neuralcrew-bot-avatars.md` — absorbida desde `creative/neuralcrew-bot-avatars` el 2026-09-23 (F6 lote 4, R15: condensar sin borrar).


<!-- absorbido de creative/bot-avatar-pipeline (censo 2026-09-24) -->
# Bot Avatar Pipeline (NeuralCrew)


Pipeline completo para que los bots de la tripulación tengan avatar verificado: generación → QA visual → instalación en el perfil → entrega. Complementa a `quality-check-visual` (checklist QA) y a `flux-models`/`brand-assets-library` (generación/identidad). Entorno NeuralCrew: bots crew = hermodr, bragi, brokkr, freyja, heimdall, sindri, ullr, vili.

## Cuándo usar

- "genera avatares para los bots", "cambia la foto de perfil de X", "las imágenes no corresponden al bot", "configúralo como imagen de cada bot".

## Pasos

1. Localizar el lote: `/opt/data/deliverables/avatares-tripulacion/` (`gen_avatares.py` define las fichas por bot con STYLE+NEG común; API NaN-Buiders flux-2-kein en `https://api.nan.buiders/v1/images/generations`, respuesta b64_json; leer API key del config.yaml del perfil).
2. QA visual de CADA archivo con `vision_analyze` — NO fiarse del nombre del archivo. Preguntar por: quién aparece, objetos en cada mano, nº de manos visibles y dedos, objeto fusionado al cuerpo (p.ej. cuerno "saliendo del hombro"), fondo. Limíte: ≤2-3 llamadas por turno (429 si >5 paralel).
3. Si un avatar falla: regenerar 2-3 candidatos con prompt ENDURECIDO (anatomía explícita: "exactly two hands with five fingers each, only this single figure, no other people, the object held clearly in his hand and separate from the body, nothing growing out of the shoulder"), QA cada candidato y promover el mejor al archivo canónico. Conservar el STYLE base del lote para consistencia.
4. Contact sheets/mosaicos: verificar el pareado etiqueta↔imagen CELDA POR CELDA con visión. El corrimiento de 1 posición (imagen[i] bajo label[i-1]) es el fallo típico al armar mosaicos (pasó con los 8 avatares: las 5 primeras celdas estaban corridas).
5. Instalar en el perfil: copiar a `/opt/data/profiles/<bot>/assets/avatar.png` (512×512 PNG) + `avatar-<bot>.jpg` (1024×1024 JPEG q92). SIEMPRE backup previo (`backup-assets-YYYYMMDD/`).
6. Verificar post-install: tamaños con Pillow (`uv run --with pillow`; `UV_CACHE_DIR=/tmp/uvcache` si /opt/data/.cache/uv no es escribible), y visión sobre 1-2 instalados.
7. Entregar con `MEDIA:` (archivos reales).

## Pitfalls

- No fiarse del nombre del archivo para saber qué bot muestra (puede no coincidir con el prompt).
- Manos extra sobre objetos del protagonista (2ª figura tocando) y objetos fusionados al cuerpo son fallos clásicos de flux-2-kein en retratos con props.
- `vision_analyze` en paralelo: rate-limit 429 si se lanzan ≥5; lote pequeño.
- Pillow no está en el python del sistema; usar `uv run --with pillow`.
- Los avatares viejos pueden quedar cacheados por la app cliente aunque el servidor ya sirva los nuevos (ver `references/desktop-avatar-delivery.md`).

## Referencias

- `references/desktop-avatar-delivery.md` — modelo de entrega al Hermes Desktop: dónde vive el avatar, quién lo lee (get_asset fresco vs UI web hardcodeada), y diagnóstico cuando el usuario "no ve" los cambios.