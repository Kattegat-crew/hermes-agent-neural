# STT: transcripción de notas de voz vía NaN Builders whisper

Receta validada (2026-08-19) para transcribir audios entrantes (WhatsApp ptt, Telegram voice).

## Pasos

1. **Localizar el audio:** las notas de voz entrantes se guardan en `/opt/data/cache/audio/`:
   ```bash
   find /opt/data/cache/audio -type f -mmin -5   # el .ogg más reciente = la última nota
   ```
   El bridge de WhatsApp entrega el body como `[ptt received]`; el `.ogg` es el payload real.

2. **Leer la key real:** `grep` NO sirve — Hermes enmascara secrets en output de tools
   (`sk-JzB...ohYw`). Leer con yaml y usar sin imprimir:
   ```python
   import yaml
   cfg = yaml.safe_load(open('/opt/data/config.yaml'))
   key  = cfg['stt']['openai']['api_key']
   base = cfg['stt']['openai']['base_url']   # https://api.nan.builders/v1
   model= cfg['stt']['openai']['model']      # whisper
   lang = cfg['stt'].get('language', 'es')
   ```

3. **POST multipart a `{base}/audio/transcriptions`** (OpenAI-compatible):
   - Campos: `model=whisper`, `language=es`, `file=<audio>`
   - Headers: `Authorization: Bearer <key>`, `Content-Type: multipart/form-data; boundary=...`,
     **`User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36`**,
     `Accept: application/json, text/plain, */*`

## Pitfalls

- **HTTP 403 error code 1010** = Cloudflare bloquea sin User-Agent de navegador (igual que chat/imagenes).
- **HTTP 401 auth_error** = key mal formada al extraer con grep (por el enmascarado). Usar yaml.safe_load.
- **HTTP 403** también aparece si se usa la URL con guion (`api.nan-builders.com` NO resuelve — ver skill `devops:nan-builders-api`).

## Script de referencia (funciona tal cual)

```python
import yaml, urllib.request, urllib.error, uuid

cfg  = yaml.safe_load(open('/opt/data/config.yaml'))
key, base, model, lang = cfg['stt']['openai']['api_key'], cfg['stt']['openai']['base_url'], cfg['stt']['openai']['model'], cfg['stt'].get('language','es')
audio_path = '/opt/data/cache/audio/aud_XXXX.ogg'  # el más reciente
boundary = uuid.uuid4().hex
audio = open(audio_path,'rb').read()

def field(n,v): return (f'--{boundary}\r\nContent-Disposition: form-data; name="{n}"\r\n\r\n{v}\r\n').encode()
body  = field('model', model) + field('language', lang)
body += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="voice.ogg"\r\nContent-Type: audio/ogg\r\n\r\n').encode() + audio
body += f'\r\n--{boundary}--\r\n'.encode()

req = urllib.request.Request(base.rstrip('/') + '/audio/transcriptions', data=body, method='POST')
req.add_header('Authorization', f'Bearer {key}')
req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
req.add_header('Accept', 'application/json, text/plain, */*')
try:
    print(urllib.request.urlopen(req, timeout=90).read().decode())
except urllib.error.HTTPError as e:
    print('HTTPError', e.code, e.read().decode()[:500])
```

Respuesta: `{"text": "...", "language": "es", "duration": N, "segments": [...]}` — usar `text`.
