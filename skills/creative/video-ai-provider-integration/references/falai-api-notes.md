# fal.ai API — Notas verificadas (19/08/2026)

Verificación directa vía curl con `FAL_KEY` activa el 19/08/2026, durante la
migración Monid → fal.ai para el pipeline video-ai-generator (reel Lucky).

## Datos de cuenta / acceso
- Key: `FAL_KEY` en `/root/marketing-campaign-generator/.env` (formato `key:secret`).
- Dashboard keys: https://fal.ai/dashboard/keys
- Auth header: `Authorization: Key <FAL_KEY>` (literal "Key " + valor, NO Bearer).
- No hay endpoint público de saldo; la factura real se ve en
  https://fal.ai/dashboard (probar gasto real es la única validación dura).

## Endpoints verificados
| Endpoint | Uso | Resultado |
|---|---|---|
| `GET https://fal.ai/models/bytedance/seedance-2.0/mini/image-to-video` | Página (JS) | 200 |
| `POST https://queue.fal.run/bytedance/seedance-2.0/mini/image-to-video` | Encolar imagen→video | `{request_id, status_url, response_url, cancel_url}` |
| `GET {status_url}` | Poll | `{"status": "IN_QUEUE"\|"IN_PROGRESS"\|"COMPLETED"\|"ERROR", ...}` |
| `GET {response_url}` | **Resultado** | `{"video": {"url", "content_type", "file_name", "file_size"}, "seed": ...}` |

## Slug / namespace
- El slug correcto es **`bytedance/seedance-2.0/mini/image-to-video`**.
- Prefijos incorrectos probados que NO funcionan: `fal-ai/seedance-2.0/mini/...`
  → `{"detail": "Application \"seedance-2.0\" not found"}`.
- Variantes: `bytedance/seedance-2.0/image-to-video` (full),
  `bytedance/seedance-2.5/image-to-video` (2.5).

## Schema (descubierto por validación, sin gastar)
Body mínimo:
```json
{
  "prompt": "SEQUENCE SHOT ...",
  "image_url": "https://goldengame.com.co/va/lucky/scene-02.jpg"
}
```
Campos validados (mensajes literales del API):
- `resolution`: `'480p' or '720p'`
- `aspect_ratio`: `'auto', '21:9', '16:9', '4:3', '1:1', '3:4' or '9:16'`
- Errores de validación ("literal_error", "missing") ocurren PRE-encolado y NO cobran.
- Si el body tiene solo `{}` → `prompt` y `image_url` marcados como missing.

Trucos de descubrimiento:
- Mandar `"resolution": "invalid"` en un POST → el API devuelve los literales
  permitidos en el mensaje de error. Es la forma de leer el schema real sin
  cobrar.
- Un POST con `prompt`+`image_url` válidos pero `resolution` inválido NO entra
  en cola (el status llega como COMPLETED con `detail` de validación = no
  procesado, no cobrado).

## Patrón de llamada completo
1. Pre-flight: `HEAD` (fallback GET chunk) a `image_url` → debe dar `image/*`.
   (Guard anti-recurrencia 19/08: Cloudflare servía HTML de SPA para `/va/*` y
   el provider rechazaba el run gastando saldo.)
2. `POST https://queue.fal.run/bytedance/seedance-2.0/mini/image-to-video` con
   `Authorization: Key $FAL_KEY`, `Content-Type: application/json`.
3. Poll `status_url` (cada 5s) hasta `COMPLETED` / `ERROR` / timeout.
4. GET `response_url` → **aquí está el video**:
   ```json
   {"video": {"url": "https://v3b.fal.media/files/b/<hash>/<id>_video.mp4",
              "content_type": "video/mp4", "file_name": "video.mp4",
              "file_size": 3990638}, "seed": "<hex>"}
   ```
5. Descargar el mp4 permitiendo hosts que terminen en: `fal.media`, `fal.run`,
   `fal.ai` (v3b.fal.media etc. entran como subdominios).

## Costos (precio público, listados 19/08)
| Modelo | $/s | 6s | 10s | 5 clips 6s |
|---|---|---|---|---|
| seedance-2.0 mini | $0.011 | $0.067 | $0.11 | ~$0.34 |
| seedance-2.0 (full) | $0.014 | $0.084 | $0.14 | ~$0.42 |
| seedance-2.5 | $0.0188 | $0.113 | $0.19 | ~$0.57 |
| wan-i2v (open source) | por video | $0.40 | — | ~$2.00 |
| ltx-2.3 fast | $0.06 | $0.36 | — | ~$1.80 |
| Kling 2.5 Turbo Pro | $0.07 | $0.42 | — | ~$2.10 |
| Veo 3.1 (premium, audio) | $0.40 | $2.40 | — | ~$12 |

Comparador Monid: Seedance 2.0 Mini 720p 6s = $0.456/clip ($3.5/M tokens ×
130,500 tokens). **fal.ai ≈ 7× más barato para el MISMO modelo.**

## Cliente del repo
- `scripts/fal-client.py` — drop-in del monid-client: mismos flags
  (`--mode image2video|text2video`, `--image`, `--prompt`, `--resolution`,
  `--ratio`, `--project/--scene/--version/--output`, `--wait`, `--dry-run`,
  `--model mini|full|fast`, `--no-audio`, `--report-cost`), mismo layout de
  salida (`assets/<project>/<scene>/v<N>/video/clip.mp4`) y sidecars
  (`.response.json` contiene el payload del **response_url** — el del video,
  no el status; `.runid` = request_id).
- Registrar en el repo con commit; el README del pipeline quedó pendiente.

## Enseñanza principal para futuras integraciones
- Los brokers (Monid) cobran markup por conveniencia; el mismo modelo vía el
  proveedor/host directo (fal) puede costar mucho menos.
- Antes de migrar con volumen, validar el precio con 1 clip real pequeño.
- Requerimiento del usuario: **no** se compran agentes orquestadores del
  proveedor (fal Agent $200/mes); el pipeline propio orquesta.