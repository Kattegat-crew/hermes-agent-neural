# Modelos de video en fal para reels con personajes (verificado 12-nov-2026)

## Regla de oro del precio
`mcp__fal__get_pricing` devuelve la **tarifa base**, no la condicional. Kling cobra distinto segun
`generate_audio` y voz. **Confirmar siempre en la pagina del modelo** (`fal.ai/models/<endpoint>`),
que publica la frase «For every second of video you generated, you will be charged...».
Caso real: get_pricing dijo $0.14/s para v3 Standard y Pro por igual; la pagina dice
Standard $0.084 / Pro $0.112 con audio off. El MCP no distingue tier ni modo de audio.

## Tabla verificada (pagina oficial del modelo)
| Endpoint | Audio off | Audio on | Audio + voice control |
|---|---|---|---|
| `fal-ai/kling-video/v3/standard/image-to-video` | $0.084/s | $0.126/s | $0.154/s |
| `fal-ai/kling-video/v3/pro/image-to-video` | $0.112/s | $0.168/s | $0.196/s |
| `fal-ai/kling-video/v2.6/pro/image-to-video` | $0.07/s | $0.14/s | $0.168/s |

## Lip-sync con audio propio (obligatorio para dialogo en espanol)
Kling v3 `generate_audio` **solo genera voz en chino e ingles**; otros idiomas se traducen al ingles.
No sirve para ponerle nuestro dialogo en espanol. Para sincronia labial real se alimenta
**imagen + audio** a un endpoint de lip-sync:

| Endpoint | $/s | Notas |
|---|---|---|
| `minimax/h3-max/lip-sync/image-to-video` | 0.05 | 480P/768P/1080P/2K; **audio >= 5 s**; salida = duracion del audio |
| `fal-ai/kling-video/ai-avatar/v2/standard` | 0.0562 | image_url + audio_url; salida = duracion del audio |
| `fal-ai/kling-video/ai-avatar/v2/pro` | 0.115 | idem, mayor calidad |
| `fal-ai/bytedance/omnihuman/v1.5` | 0.16 | el mas caro de la familia |

Consecuencia de diseno: **cada bloque hablado debe durar >= 5 s** (H3 Max) o se rellena con pad de
silencio al inicio. La duracion del clip la manda el audio: el guion se escribe por frases y el TTS
se mide antes de encargar el video.

## Deprecados
`fal-ai/veo3`, `fal-ai/veo3/image-to-video`, `fal-ai/veo3/fast`, `fal-ai/veo3/fast/image-to-video`,
`fal-ai/veo2`: retirados por fal. No inventar un ID nuevo a partir del nombre.

## Mezcla recomendada (coste/calidad)
Bloques hablados -> H3 Max Lip Sync 1080P. B-roll y ambiente -> Kling v3 Standard audio off
($0.084/s). Pro solo para el plano hero si el cliente lo pide expresamente.
