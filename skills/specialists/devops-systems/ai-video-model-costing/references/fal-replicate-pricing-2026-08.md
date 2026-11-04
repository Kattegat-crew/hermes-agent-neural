# Precios fal.ai + Replicate (video 6s · 720p · 9:16) — verificados 19/08/2026

Todos extraídos por curl de páginas oficiales / catálogo el 19/08/2026. fal.ai factura POR
VIDEO o POR SEGUNDO según modelo; Replicate por segundo de salida (nueva 2026) o por video.
Siempre distinguir el `billing_unit` antes de calcular el clip.

## Método de extracción (curl, sin token)

### fal.ai
1. Catálogo con slugs REALES (no adivinar): `curl -s "https://fal.ai/api/models?page=N"`
   → JSON `items[].id` + `category`. Filtra `category=="image-to-video"`. Slugs adivinados tipo
   `fal-ai/wan/v2.1-14b/image-to-video` suelen 404; el real es `fal-ai/wan-i2v`.
2. Página `https://fal.ai/models/<slug>`: blob `endpointBilling` de __NEXT_DATA__ trae
   `"billing_unit":"seconds"|"videos"` + `"price":N`. El chip "[...]will cost $X per [video|second]"
   es la fuente autoritativa.
3. Pitfall scraping: __NEXT_DATA__ viene con escaping anidado. Normalizar con `h=h.replace("\\","")`
   y luego `re.findall(r'"billing_unit":"([a-z]+)","price":(\d+\.?\d*)', d)` y
   `re.findall(r'will cost.*?\$(\d+\.?\d*)', d, re.S)`.

### Replicate
1. Slugs por colecciones: `curl -s https://replicate.com/collections/image-to-video` y
   `.../text-to-video` → grep `href="/owner/model"` (páginas SSR, sale con curl).
2. Página `https://replicate.com/<slug>`: el chip autoritativo es el unit-output tipo
   `"description": "N seconds for $X"` / `"N videos for $X"`, o los `"title":"per second of output
   video","price":"$X"`.
3. PITFALL: `"p50price"` es LEGACY (precio por segundo de cómputo interno) — NO es lo que se factura.
   Basarse en los chips por-unidad, no en p50. Los modelos por-video NO cotizan por segundo.

## Precios verificados fal.ai (6s 720p)

| Modelo | bill | $/clip 6s | Audio | Nota |
|---|---|---|---|---|
| `fal-ai/wan-i2v` (Wan 2.1) | video | **$0.40** | No | open source; mejor calidad-precio |
| `fal-ai/wan/v2.2-a14b/image-to-video` | s | $0.48 | No | Wan 2.2 A14B |
| `fal-ai/wan/v2.2-a14b/image-to-video/turbo` | video | ~$0.10 | No | turbo, clips cortos |
| `fal-ai/ltx-2.3/image-to-video` (Pro) | s | $0.48 | No | LTX 2.3 |
| `fal-ai/ltx-2.3/image-to-video/fast` | s | $0.36 | No | LTX 2.3 Fast |
| `bytedance/seedance-2.0/mini/image-to-video` | s | **~$0.067** | **Sí (voz)** | ⚠️ ~7× más barato que Monid (0.45675/clip). VERIFICAR con run de prueba |
| `bytedance/seedance-2.0/image-to-video` | s | $0.084 | Sí | Seedance 2.0 std |
| `bytedance/seedance-2.5/image-to-video` | s | $0.113 | Sí | Seedance 2.5 |
| `fal-ai/kling-video/v1/standard/image-to-video` | s | $0.27 | No | Kling v1 standard |
| `fal-ai/veo3.1/image-to-video` | s | $2.40 | Sí | Veo 3.1 premium |
| `fal-ai/hunyuan-video` (t2v) | video | $0.40 | No | solo text-to-video |

## Precios verificados Replicate (6s)

| Modelo | $/clip 6s | Audio | Nota |
|---|---|---|---|
| `wavespeedai/wan-2.1-i2v-720p` | **$1.50** ($0.25/s) | No | Wan caro aquí |
| `wavespeedai/wan-2.1-i2v-480p` | **$0.54** ($0.09/s) | No | Wan barato |
| `bytedance/seedance-2.0` | $0.60 ($0.10/s) | Sí | |
| `minimax/video-01` (Hailuo) | $0.50/video | No | legacy |
| `lightricks/ltx-video` | ~$0.50 ($0.083/s) | No | ambiguo, re-chequear |
| `kwaivgi/kling-v2.1` | $0.30–$0.54 | No | 2 tiers |
| `tencent/hunyuan-video` | est $0.20–$0.40 | No | por runtime; depende de latencia |

## Conclusión de la sesión (19/08/2026)
- Más barato open-source decente (6s 720p): fal.ai `wan-i2v` → $0.40/clip → **$2.00 / 5 clips**.
- LTX 2.3 Fast: $0.36/clip → $1.80 / 5 clips.
- Con audio nativo: fal `seedance-2.0/mini` $0.067/clip (~$0.34 / 5) — sospechosamente barato vs Monid
  ($0.45675 → $2.28 / 5): validar con un run real antes de reemplazar el pipeline.
- Hunyuan/LTX en Replicate no son competitivos (per-second-runtime confuso o caro).