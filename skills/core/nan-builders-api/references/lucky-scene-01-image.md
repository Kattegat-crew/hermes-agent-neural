# Lucky Scene-01 — Image Generation via NaN Builders (2026-08-17)

## Contexto

Primera imagen generada para el reel Lucky (The Grand Paradise Club Casino).
Mascota: Lucky (trébol de 4 hojas) en calle colonial de Tunja, Boyacá.

## Llamada exitosa

```python
import json, urllib.request, base64

nan_key = "sk-..."  # de /root/marketing-campaign-generator/.env
prompt = "A friendly 4-leaf clover mascot named Lucky standing on a colonial street in Tunja, Colombia. The clover is bright green with a cute smiling face, big eyes, wearing a tiny golden crown. Behind him, colorful colonial buildings with white walls, clay tile roofs, and wooden balconies. Blue sky with white clouds. Stone street. Warm sunny afternoon light. Cheerful atmosphere. Digital illustration, vibrant colors, 9:16 vertical, cartoon mascot style."

payload = {
    "model": "flux-2-klein",
    "prompt": prompt,
    "n": 1,
    "size": "720x1280",
    "response_format": "b64_json",
}

req = urllib.request.Request(
    "https://api.nan.builders/v1/images/generations",
    data=json.dumps(payload).encode(),
    headers={
        "Authorization": f"Bearer {nan_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    },
)
resp = urllib.request.urlopen(req, timeout=180)
data = json.loads(resp.read())
img = base64.b64decode(data["data"][0]["b64_json"])
# 608,358 bytes | 720x1280 PNG
```

## Errores durante el camino

| Error | Causa | Fix |
|---|---|---|
| Name or service not known | URL `api.nan-builders.com` (con guion) | Usar `api.nan.builders` (sin guion) |
| HTTP 403 error 1010 (Cloudflare) | urllib sin User-Agent de navegador | Agregar headers User-Agent + Accept |
| DNS failure en contenedor efímero | python:3.12-slim sin resolución | Ejecutar desde contenedor Hermes |

## Resultado

608 KB PNG, 720x1280, guardado en `/opt/data/cache/lucky-scene-01.png`.
Estilo: digital illustration, cartoon mascot, colores vibrantes.