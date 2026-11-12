---
name: reel-campana-video-modelos-voz
description: Canon de producción de reels de campaña casino — lote-preparado.json como SSOT, voces ElevenLabs por marca, catálogo/precios de video i2v en fal y reglas de fotos de sedes.
version: 1.0.0
license: internal
metadata:
  hermes:
    category: specialists
    tags: [reels, casinos, elevenlabs, fal, kling, wan, lote-preparado, voces]
---

# Reel de campaña casino: video-modelos, voces y canon del lote

## When to Use
- Antes de producir cualquier lote de reels de campaña (Golden/Lucky): fijar proveedor de voz, elegir modelo de video en fal o armar el `lote-preparado.json`.
- Al estimar costos de un lote (keyframes + video i2v) o decidir la mezcla hero/ambiente.
- Al diagnosticar un reproche del Admin sobre voz de marca (kokoro vs ElevenLabs).

> Verificado en producción 12-nov-2026 (campaña El Aguinaldo Millonario, repositorio
> `marketing-campaign-generator` en DEV, branch main).

## 1. El lote canónico: `lote-preparado.json` es la SSOT

Todo prompt, referencia, voz, escena y coste de un lote de reels vive en un
`lote-preparado.json` por carpeta de reel (`planning/<campania>/02-guiones/<reel>/`).
Estructura probada (Halloween reel2-fantasma-v02):

- `status: prepared_waiting_human_gate` — nada se gasta sin gate.
- `source_literal` (ruta + sha256 del guion aprobado LITERAL) y `source_script`.
- `image`: modelo (gpt-image-2), endpoint (`openai/gpt-image-2/edit`), quality/size/format,
  `references[]` con rol y **sha256** de cada hoja (front.png = autoridad de identidad,
  design-sheet = anatomía, arte aprobado = atmósfera), `submissions_per_scene: 1`,
  `automatic_resubmissions: 0`.
- `voice`: provider `elevenlabs`, modelo `eleven_multilingual_v2`, `voice_id` POR MARCA,
  `fallback_allowed: false`.
- `video`: provider, endpoint, resolution/ratio, `first_frame_only`, 0 reintentos.
- `scenes[]`: duración y diálogo literal por escena.
- `estimated_cost_usd` con tarifas reales medidas (gpt-image-2 medium 720x1280 = $0.0434/still).

Fuera de este archivo no se improvisa ningún prompt ni parámetro.

## 2. Voz: ElevenLabs siempre en campaña (nunca kokoro)

- `ELEVENLABS_API_KEY` vive en el `.env` del repo; `_load_key()` lo resuelve.
- Voces de marca (listado verificado): Goldie **`qWWAqFomnJ99VwQLREfT`** ("Voz-Goldie", es,
  female), Lucky **`lWweqHoPFkas8ijavnVj`** ("Lucky final", es).
- Cubierto por el plan de ElevenLabs → coste marginal $0, pero igual pasa por el gate.
- Kokoro/nan builders (`voz-es-coste-cero-nan`) es SOLO para drafts internos sin marca.
  El Admin lo dejó cerrado: para reels de Golden/Lucky «jamás kokoro».

## 3. Catálogo video image-to-video en fal (precios $/s, verificados 12-nov-2026)

| Endpoint | $/s | Nota |
|---|---|---|
| `fal-ai/kling-video/v3/pro/image-to-video` | 0.14 | hero: cinemática + audio nativo + custom elements |
| `fal-ai/kling-video/v3/standard/image-to-video` | 0.14 | mismo precio que Pro: sin ventaja |
| `kling/v4/image-to-video` | 0.157 | 3–30 s, multi-shot, 720p/1080p, end-frames |
| `fal-ai/kling-video/ai-avatar/v2/pro` | 0.115 | lipsync: anima foto con NUESTRO audio |
| `minimax/h3-max/image-to-video` | 0.035 | ambiente, 4× más barato |
| `alibaba/wan-3.0/image-to-video` | 0.05 | ambiente, gran continuidad |
| `fal-ai/veo3*` (todas las variantes) | — | **DEPRECADO en fal** |

**Estrategia de mezcla** (no todo en el modelo caro): por reel de 24 s — 2 planos hero de
4 s en Kling v3 Pro ($1.12) + 4 planos ambiente en Wan 3.0 ($0.80) + 6 keyframes
gpt-image-2 ($0.26) ≈ **$2.18/reel**.

**"Gente real":** solo (a) image-to-video con la foto real de la persona o (b) avatar-lipsync
con su audio (Kling Avatar v2 / Omnihuman / H3 Max Lip Sync). Ambas exigen consentimiento de
uso de imagen; en publicidad de apuestas, doblemente sensible. Los modelos NO muestran gente
real: generan fotorrealismo sintético si no das foto + permiso.

## 4. Fotos de sedes: referencia-only

`assets/sedes/index.json` es la SSOT de ambientes. Las fotos viven en Drive (carpetas
`Fotos Locales` por marca; bajar con `drive_get_media.py`). Regla dura del índice:
**sin gente, sin marcas ajenas; las fotos sirven como referencia de layout/paleta, NO se
pegan en crudo ni se adjuntan tal cual**. Los `landmarks` de pueblo se buscan en internet
con fuente y revisión humana, nunca para mostrar el local.

## 5. Logo y cierre

- El logo JAMÁS se genera con IA: se compone en post (registry kind=logo).
- Pie legal va LITERAL en el cierre del reel (p. ej. `AUTORIZA COLJUEGOS · SOLO MAYORES DE
  EDAD`), no como nota del documento.
- Campañas: cero montos, cero mecánica (no nombrar sellos/tarjetas/premios), cero menores.

## 6. Codex CLI en el host DEV (para keyframes/código de escena)

- No está en el contenedor: vive en el host DEV en `/root/.local/bin/codex`
  (`codex-cli 0.167.1`, config `/root/.codex/config.toml`).
- Invocación no interactiva: `ssh dev '/root/.local/bin/codex exec "..."'`.
- El Admin definió que los keyframes de escena se disparan con Codex; si su runtime no
  expone generación de imagen, el fallback canónico es `scripts/fal_image_client.py
  --model gpt-image-2` (dry-run gratis primero, luego live con gate).
