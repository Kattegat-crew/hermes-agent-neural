# Catálogo de modelos fal.ai — audio/TTS y probe a costo cero (19/08/2026)

## Descubrir IDs del catálogo (SPA-friendly)
La página de modelo de fal (`/models/<id>`) es SPA: NO trae el schema en HTML plano.
Pero el catálogo de categoría SÍ expone los IDs vía curl:

```python
import re, urllib.request
h = urllib.request.urlopen(urllib.request.Request(
    "https://fal.ai/models?view=audio",
    headers={"User-Agent": "Mozilla/5.0 Chrome/126.0"})).read().decode()
audio = sorted(set(re.findall(r'href="(/models/[^"#]+?)(?:/[\"?]|")', h)))
```
Categoría: `https://fal.ai/models?view=audio` o `.../models/categories/audio-generation`.
Extraer solo los `fal-ai/...` (modelos hosteados por fal), no los `bytedance/...` de terceros.

## Probe de endpoint SIN gastar (clave — costo cero, sin key)
Cada endpoint del catálogo responde **401** con auth inválida y POST mínimo → ruta válida:
```bash
for ep in <model_ids>; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -m 15 -X POST "https://queue.fal.run/$ep" \
    -H "Authorization: Key invalid_test_only" -H "Content-Type: application/json" -d '{"prompt":"hola"}')
  echo "$code  $ep"
done
```
- **401** = endpoint existe (solo falla auth). Listos para usar con la key real.
- **404** = el ID está mal o el modelo ya no existe.

## Modelos AUDIO/TTS verificados en fal.ai (todos responden 401):
| Endpoint | Tipo |
|---|---|
| `fal-ai/elevenlabs/tts/turbo-v2.5` | TTS multilingua (locutor). META public: "Generate high-speed text-to-speech using ElevenLabs TTS Turbo v2.5" |
| `fal-ai/minimax/preview/speech-2.5-hd` | TTS MiniMax 2.5 HD (uno de los mejores español) |
| `fal-ai/minimax/speech-2.6-hd` / `speech-2.8-hd` | TTS MiniMax 2.6 / 2.8 HD |
| `fal-ai/minimax/speech-02-hd` / `speech-02-turbo` / `preview/speech-2.5-turbo` / `speech-2.8-turbo` | variantes turbo |
| `fal-ai/minimax/voice-clone` | clonación de voz |
| `fal-ai/qwen-3-tts/text-to-speech/0.6b` y `/1.7b` | TTS gratuito/barato de Alibaba |
| `fal-ai/qwen-3-tts/voice-design/1.7b` | diseño de voz |
| `fal-ai/lux-tts` | TTS |
| `fal-ai/gemini-3.1-flash-tts` | TTS |
| `fal-ai/playai/tts/dialog`, `fal-ai/index-tts-2/text-to-speech`, `fal-ai/chatterbox/text-to-speech` | otros TTS |
| `fal-ai/stable-audio`, `stable-audio-25/text-to-audio`, `fal-ai/ace-step/prompt-to-audio`, `fal-ai/bytedance/seedance-2.0/mini/text-to-video` | audio/video |

También: `fal-ai/ace-step/prompt-to-audio`, `fal-ai/gemini-3-pro-image-preview` (visión).

## Elegir voz TTS real SIN créditos
- Demos web propios del proveedor aceptan texto libre gratis:
  - ElevenLabs: https://elevenlabs.io/text-to-speech — elegir el modelo multilingüe (v2) para español; voz con acento latino si aparece. Demo da crédito de prueba que no es tu FAL_KEY.
  - MiniMax: minimax.io sección Speech.
- Para validar PRONUNCIACIÓN (nombres propios, ciudades): pegar el guión COMPLETO del reel en la demo con la misma voz — es la prueba real de que dirá bien Chiquinquirá / La Calera / Funza / tragamonedas antes de gastar.
- ElevenLabs expone voces premade: `GET https://api.elevenlabs.io/v1/voices` (JSON `{voices:[{voice_id,name,labels}]}`). El endpoint público devuelve ~21 voces por defecto (premade en inglés); para voces españolas usar el playground con modelo multilingüe.

## Precio real fal TTS — advertencia
La web de pagos de fal muestra una tarifa que NO aplica directo al $/clip TTS (cobro por tokens).
Siempre validar el costo REAL en el dashboard del usuario tras 1 run. Regla dura heredada:
los costos de subagente se confirman con el proveedor, nunca se estiman a ojo.

## Uso posterior (una vez elegida la voz)
Escribir un `fal-tts-client.py` (drop-in del `fal-client.py` de video) que genere los N audios
WAV por escena, silenciar voz nativa del clip y mezclarla (ffmpeg) sobre el video aprobado.
GATE humano y asignación de saldo = como en el pipeline de video (approved_by humano + FAL_KEY
solo en var de sesión, no en disco).