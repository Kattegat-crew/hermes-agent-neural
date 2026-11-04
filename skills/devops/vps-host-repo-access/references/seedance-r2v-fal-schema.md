# Seedance 2.0 reference-to-video (fal.ai) — schema verificado 2026-08-28

Fuente: https://fal.ai/models/bytedance/seedance-2.0/reference-to-video/llms.txt +
github.com/fal-ai/seedance-2.0-api (README + examples/reference_to_video.py).
Implementado en `/root/marketing-campaign-generator/scripts/fal-client.py --mode reference2video`
(commit 50417e0 en main).

## Endpoints
- `bytedance/seedance-2.0/reference-to-video` (tier full)
- `bytedance/seedance-2.0/fast/reference-to-video` (tier fast, mismas capacidades)
- Queue: `POST https://queue.fal.run/<endpoint>` → `{request_id, status_url, response_url}`;
  poll status; resultado completo en `response_url` (`{"video": {"url": ...}}`).

## Input schema
| Param | Tipo | Reglas |
|---|---|---|
| `prompt` | string, req | Referencias `@Image1`, `@Video1`, `@Audio1`; scene cuts/timestamps para pacing |
| `image_urls` | list | ≤9, JPEG/PNG/WebP, ≤30 MB c/u |
| `video_urls` | list | ≤3, MP4/MOV, combined 2–15 s, ≤50 MB, ~480p(640x640)–720p(834x1112) |
| `audio_urls` | list | ≤3, MP3/WAV, combined ≤15 s, ≤15 MB c/u. **Si hay audio, exige ≥1 imagen o video** |
| total archivos | — | ≤12 across all modalities |
| `resolution` | `"480p"` \| `"720p"` | default 720p — **NO hay 1080p en este endpoint** |
| `duration` | `"auto"` \| `"4".."15"` (strings) | |
| `aspect_ratio` | auto/21:9/16:9/4:3/1:1/3:4/9:16 | |
| `generate_audio` | bool, default true | Incluye lip-synced speech; costo idéntico on/off |
| `seed` | int | Reproducibilidad aproximada |

Multiplicador 0.6x de precio cuando hay video inputs.

## Ejemplo lip-sync oficial (talking head)
```json
{
  "prompt": "@Image1 speaks directly to the camera in a professional studio setting while saying @Audio1.",
  "image_urls": ["https://.../speaker.jpg"],
  "audio_urls": ["https://.../speech.mp3"],
  "resolution": "720p",
  "duration": "10",
  "aspect_ratio": "9:16",
  "generate_audio": true
}
```

## Notas para el pipeline AKARI
- Modelos del cliente: `r2v` (full, ~$0.014/s) y `r2v-fast` (~$0.011/s) → clip 5s ≈ $0.07.
- Preflight obligatorio: URLs de imagen deben devolver `image/*` y las de audio `audio/*`
  ANTES de POSTear (regresión 19/08: Cloudflare servía HTML de la SPA para /va/*).
- El WAV de ElevenLabs es local → publicarlo a URL `/va/` antes del run; fal no acepta
  paths locales ni data-URLs.
- Límite duro de audio: línea de narración ≤15s por clip (las de Goldie ~5s entran ok).
- `monid-client.py` (el otro proveedor, API `/v1/run` con content[] roles) NO tiene aún
  modo reference-to-video — hay que extenderlo si el lip-sync se quiere por Monid.
