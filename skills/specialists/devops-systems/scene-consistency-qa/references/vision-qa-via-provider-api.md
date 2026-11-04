# QA visual por API directa del proveedor (cuando vision_analyze no soporta imágenes)

Receta validada 2026-08-28 en el QA de 10 stills del reel Lucky / Bingo Millonario
(modelo con visión vía API OpenAI-compatible de NaN-Builders).

## Síntoma

`vision_analyze` falla con `400 - Model do not support image input`: el auxiliar
`auxiliary.vision` de config.yaml quedó apuntado a un modelo SIN visión
(deepseek-v4-flash en ese momento).

## Camino 1 — arreglar la config (probar primero)

1. Backup: `cp config.yaml config.yaml.bak-vision-$(date +%Y%m%d-%H%M%S)`.
2. Editar el bloque `auxiliary.vision` → provider/modelo CON visión del catálogo del
   proveedor (ej. qwen3.6 en NaN), con base_url y api_key del MISMO provider.
3. Reintentar `vision_analyze`. Si la tool cachea la config y sigue fallando,
   usar el camino 2 (no bloquea el trabajo).

## Camino 2 — API directa (stdlib puro, sin dependencias)

```python
import re, base64, json, urllib.request, io
from PIL import Image

def vqa(img_path, question, max_tokens=3000):
    im = Image.open(img_path).convert("RGB")
    im.thumbnail((1400, 1400))                      # payload ligero
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    payload = {"model": MODEL, "max_tokens": max_tokens, "messages": [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": question + "\nResponde directo, sin razonamiento visible."},
        ]}]}
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            # User-Agent de NAVEGADOR: obligatorio; el UA de python recibe
            # Cloudflare 403 error 1010 (la API lo exige).
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        },
    )
    with urllib.request.urlopen(req, timeout=240) as r:
        resp = json.load(r)
    c = resp["choices"][0]["message"].get("content")
    if not c:
        raise RuntimeError(f"empty content, finish={resp['choices'][0].get('finish_reason')}")
    return c
```

## Trampas (todas encontradas en vivo)

| Trampa | Señal | Fix |
|---|---|---|
| UA de python | HTTP 403 `error code: 1010` | UA de navegador (ver código) |
| Modelo con reasoning | content vacío, `finish_reason: "length"` (el pensamiento consumió los tokens) | `max_tokens >= 3000` + "responde directo, sin razonamiento" + reintentar 2-3 veces |
| Content vacío intermitente | `'NoneType' object is not subscriptable` al parsear | retry con el mismo payload (pasa y luego pasa bien) |
| Nunca imprimir keys | — | leer api_key del config.yaml con regex, usarla en memoria |

## Validar que el modelo REALMENTE ve (anti-hallucinación)

Antes de confiar en el backend, lanzar una prueba de control con una imagen conocida
y una pregunta cerrada (ej. "¿cuántas hojas tiene el personaje? ¿qué dice el letrero?").
Si responde genérico o "no veo imagen", NO usar ese backend para QA: la hallucinación
de visión no siempre da error — puede devolver una descripción plausible inventada
(sin haber visto nada). Preguntas cerradas con detalles concretos (transcribir texto,
contar elementos) son el detector.

## Estilo de prompt para QA de escenas

Estructura fija, concisa (max 200 palabras de respuesta):
1) personaje (anatomía/dedos/accesorios) 2) props (maleta, etc.) 3) entorno + TEXTOS
transcritos exactamente + ortografía 4) cámara/encuadre/dirección de acción
5) defectos (dedos raros, morphing, texto deformado).

Para detalles ambiguos: segunda pasada con pregunta CERRADA y específica
("¿hacia qué lado camina?", "cuenta las hojas del cuerpo, no los brazos").
