<!-- Caso absorbido por F6 lote 4 el 2026-09-23 desde `creative/neuralcrew-bot-avatars`.
     Contenido íntegro; original en
     `data/archive/F6_lote4_20260923-161107/absorbidas/`. -->

---
name: neuralcrew-bot-avatars
description: "Use when: instalar/actualizar avatar de un bot NeuralCrew."
category: neuralcrew-ops
version: 1.0.0
---

**Propósito real:** Desplegar la identidad visual de los bots NeuralCrew en sus perfiles Hermes.

## Cuándo usar
- El usuario pide "configura X como avatar/imagen del bot Y" o renovar la imagen de los bots.
- Hay renders 1:1 nuevos (p. ej. lote de avatares de tripulación) que deben quedar instalados como imagen oficial de cada bot.

## Dónde viven los assets (fuente de verdad)
- `/opt/data/profiles/<bot>/assets/avatar.png` → avatar canónico **512×512 PNG** (el que consume la app desktop "hermes-bots"; el perfil está marcado con `ui_meta.hermes-bots` en su `profile.yaml`).
- `/opt/data/profiles/<bot>/assets/avatar-<bot>.jpg` → tarjeta grande **1024×1024 JPG**.
- Bots crew típicos: hermodr, bragi, brokkr, freyja, heimdall, sindri, ullr, vili (+ roshi, comms, vigia).

## Procedimiento
1. Identificar el render correcto por bot (QA visual previo — ver skill `quality-check-visual`; no fiarse del nombre del archivo).
2. **Backup** de los assets actuales → `/opt/data/deliverables/<proyecto>/backup-assets-<AAAA-MM-DD>/<bot>_avatar.png|jpg` (rollback garantizado).
3. Redimensionar e instalar con Pillow — script reutilizable: `scripts/install_bot_avatars.py` (PNG 512² optimize=True + JPG 1024² quality≈92).
4. **Verificar**: dimensiones exactas programáticamente y QA visual de 1-2 avatares instalados (identidad correcta, sin artefactos).
5. Si la app desktop cachea avatares, avisar al usuario que refresque/reabra.

## Arquitectura (importante, no confundir)
- El servidor Discord NeuralCrew Labs tiene UN solo bot miembro real: **"Ragnar"** (id 1493385610797252758). Los 8-12 bots crew NO son miembros separados de Discord: son identidades de la app desktop (perfiles Hermes multiplexados por canal en `config.yaml gateway.profile_routes`).
- Token Discord: `DISCORD_BOT_TOKEN` vive en los `.env` de los perfiles **roshi/comms/vigia** (los `.env` de perfiles crew suelen estar vacíos; el gateway lo carga por home/.env o por perfil al multiplexar). Jamás imprimir tokens.
- Cambiar el avatar del bot Discord REAL (Ragnar) = `PATCH /users/@me` con ese token; los avatares de perfil crew solo se muestran en la app/escritorio.

## Pitfalls
- Pillow no está en el python del sistema: usar `uv run --with pillow python3 ...`; si `/opt/data/.cache/uv` da "Permission denied", exportar `UV_CACHE_DIR=/tmp/uvcache`.
- Al QA de varias imágenes de golpe, no disparar >4 vision_analyze en paralelo (límite de concurrencia ~5 → 429); usar tandas de 2.
- No sobrescribir `avatar.png` sin backup previo (rollback = `backup-assets-*`).
- Consulta rápida del layout y comandos verificados: `references/layout-avatares-crew.md`.