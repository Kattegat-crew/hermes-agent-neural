---
name: video-ai-provider-integration
description: "Use when wiring an AI video provider into the pipeline."
tags: [video-ia, fal-ai, monid, proveedor, api, image-to-video, seedance]
---

# Video AI Provider Integration (fal.ai / Monid / brokers)

## Cuándo usar
- Montar un proveedor de video IA (image-to-video) nuevo o migrar entre brokers (ej. Monid → fal.ai).
- El usuario pide "prueba los endpoints" o "configura el proveedor con la app".
- Presupuestar/decidir proveedor para reels (comparativas están en `ai-video-model-costing`, user-owned).
- El usuario quiere saber si vale comprar una herramienta orquestadora del proveedor (fal Agent, etc.).

## Reglas del usuario (19/08/2026 — correcciones con costo)
1. **NO gastar en orquestadores extra.** fal Agent = $200/mes y NO se compra: "para eso estás tú y la app". El orquestador es Ragnar + video-ai-generator. Solo se usa la **API** (clave + HTTP).
2. **"Solo haz pruebas de endpoints" significa: NO generar clips reales.** Aunque un clip valga $0.07, el usuario lo corrigió ("espera, ya generaste los videos"). Endpoint tests = dry-run (`--dry-run`) + requests con campos inválidos que fallen en validación pre-encolado. CERO generaciones pagadas salvo orden explícita.

## Patrón de API de fal.ai (async queue) — verificado 19/08
- Auth: header `Authorization: Key <FAL_KEY>` (formato `key:secret`, ver `video-ai-generator/.env`).
- Slug del modelo lleva namespace: `bytedance/seedance-2.0/mini/image-to-video` (el prefijo `bytedance/` es obligatorio — `fal-ai/...` devuelve "Application not found").
- Body mínimo image2video: `{"prompt": "...", "image_url": "<HTTPS público>"}`.
  - `resolution ∈ {480p, 720p}` (literal: '480p' or '720p').
  - `aspect_ratio ∈ {auto, 21:9, 16:9, 4:3, 1:1, 3:4, 9:16}`.
- Flujo:
  1. `POST https://queue.fal.run/<slug>` → `{request_id, status_url, response_url, cancel_url}`.
  2. Poll `status_url` (5s) hasta `COMPLETED` / `ERROR`.
  3. **El video NO está en status_url** → GET `response_url` → `{"video": {"url": "https://v3b.fal.media/...mp4", ...}}`.
  4. Descarga con allowlist de hosts: sufijos `fal.media`, `fal.run`, `fal.ai`.
- Descubrir schema SIN gastar: mandar body con valores inválidos (`"resolution":"invalid"`) → la validación Pydantic devuelve la lista exacta de literales permitidos como error pre-encol. Los errores de validación NO cobran.
- Pre-flight obligatorio: verificar que `image_url` devuelva `Content-Type: image/*` antes de encolar (run falla y gasta si llega HTML/SPA).

## Costos (19/08, precio público fal, validar con 1 clip real $0.067 antes de migrar grande)
- Seedance 2.0 Mini 720p: $0.011/s → 6s ≈ $0.067; 10s ≈ $0.11.
- Seedance 2.0 full: $0.014/s. Seedance 2.5: $0.0188/s.
- Reel 5 clips a 6s: ~$0.34 (vs Monid $2.28 — ~7× más barato).
- Monid (referencia): $3.5/M tokens → 6s 720p = 130,500 tokens = $0.456/clip.

## Imágenes con GPT vía fal (verificado 11/09/2026)

fal sirve **12 endpoints GPT Image**. Los relevantes:

| endpoint | familia | 9:16 nativo | precio |
|---|---|---|---|
| `openai/gpt-image-2` (+`/edit`) | GPT Image 2 | SÍ | $0.005–0.211/img según tamaño y calidad |
| `openai/gpt-image-2.5/{flare,sunburst}/text-to-image` (+`/edit`) | 2.5 (08/09/2026) | SÍ | por tokens (texto $5/$10; imagen $8/$30 por 1M) |
| `fal-ai/gpt-image-1.5` (+`/edit`) | 1.5 | NO (máx 2:3) | low $0.009–0.013 / medium $0.034–0.051 / high $0.133–0.200 |
| `fal-ai/gpt-image-1-mini` | 1 mini | NO | low $0.005–0.006 / medium $0.011–0.015 / high $0.036–0.052 |
| `fal-ai/gpt-image-1/text-to-image` (+`/edit-image`) | 1 (legacy) | NO | low $0.011–0.016 / medium $0.042–0.063 / high $0.167–0.250 |

Datos duros que cuestan dinero si se ignoran:
- **Solo la familia 2.x acepta 9:16**, y solo con `image_size` **explícito** `{width,height}`:
  múltiplos de 16, área 655.360–8.294.400 px, aspecto ≤ 3:1, lado ≤ 3840. `720x1280` es 9:16
  válido y casa 1:1 con el video Seedance 720p; `1024x1792` es el 9:16 en alta. Los presets de
  fal (`portrait_16_9`, `portrait_4_3`) NO son 9:16.
- **`quality` por defecto es `high`** en gpt-image-2/2.5 (3–5× el costo): fijar `medium` salvo
  intención explícita.
- El schema OpenAPI de cada endpoint se lee SIN key y sin gastar:
  `https://fal.ai/api/openapi/queue/openapi.json?endpoint_id=<slug>` (precios y tamaños también
  en `https://fal.ai/api/models?keywords=<modelo>`).
- Precios de tamaños fuera de tabla: extrapolación por píxeles (la tabla publicada no es monótona
  en píxeles) → tratarlos como ESTIMACIÓN, el cobro real está en el dashboard.
- Editar/restyle: `/edit` acepta URL pública o data URI base64; `gpt-image-2/edit` soporta
  máscara. El costo de edición suma los tokens de la imagen de entrada.

Cliente del repo: `marketing-campaign-generator/scripts/fal_image_client.py` (`--need`,
`--dry-run`, gate de gasto obligatorio).

## Gate de gasto (patrón verificado 11/09/2026)

En `marketing-campaign-generator` el gate es FÍSICO: un archivo que firma el humano, no el agente.
`scripts/spend_gate.py` + `.spend-gate.json` (`approved_by` humano, `purpose`, `providers`,
`expires_at` con offset y ≤ 24 h); legacy `.fal-gate.json` / `.monid-gate.json` / `.nan-gate.json`.
Aborta con **exit 3 antes de tocar la red**; `--dry-run` no lo exige. Estado: `--status`.

Lecciones que costaron auditoría:
- **Un gate solo en `main()` es teatro**: cualquier consumidor de librería lo salta. Enforzarlo en
  el choke point HTTP (`api_post` / `_run`), que es el único camino al POST.
- Un archivo de gate **sin consumidores** (`.monid-gate.json` existía y nadie lo leía) da falsa
  seguridad: grep del nombre antes de confiar.
- Rechazar firmas de agente (`agent|ragnar|assistant|bot|gpt|…`), exigir offset de zona y limitar
  la ventana evitan gates eternos u auto-firmados.
- Los scripts ad-hoc (no el engine) suelen ser el hueco real: gatearlos uno por uno.

## Pitfalls
- **Nunca recomendar herramientas orquestadoras del proveedor** (fal Agent $200/mes); el pipeline propio basta.
- **Monid no tiene endpoint saldo** (`/v1/credits`→404). fal tampoco expone balance vía API fácil: factura real en el dashboard web.
- `--dry-run` en los clientes del repo imprime body + costo sin gastar — usar siempre primero.
- El sidecar `.response.json` del fal-client guarda el payload del `response_url` (con video.mp4), no el status.

## Referencias
- `references/falai-api-notes.md` — notas verificadas: body, response shape, discovery del schema, prices, errores vistos (Application not found, literal errors), comparación Monid vs fal.