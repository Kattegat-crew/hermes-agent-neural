---
name: ai-chat-share-extraction
description: "Use when reading a public AI-chat share link's content."
tags: [chatgpt, share-link, ssr, transcript, extraccion, imagenes, prompts]
license: Apache-2.0
metadata:
  author: "roshi"
  version: "1.0"
  tags: [chatgpt, share-link, ssr-payload, transcript, extraction, prompts]
  category: web
---

# Leer conversaciones compartidas de chats IA (link público, sin login)

Cuando alguien comparte un enlace tipo `https://chatgpt.com/share/<id>`, la conversación **completa ya viene dentro del HTML** que devuelve el servidor. No hace falta login, cookies ni navegador: hay que extraer y decodificar el payload SSR.

Respuesta corta al usuario: **sí, se puede** — y se prueba con evidencia (título, conteo de mensajes, fragmentos textuales), no con un "creo que sí".

## When to Use

- El usuario manda un link de ChatGPT/otro chat y pregunta "¿puedes acceder a esta conversación?" / "¿lo puedes leer?".
- Hay que convertir un hilo compartido en **insumo de trabajo**: prompts de generación de imágenes, guiones, decisiones de campaña, correcciones de un cliente.
- Se necesita citar textualmente lo que se habló ahí (dejando claro que es material del usuario, no fuente verificada).

## Cómo (verificado 11/09/2026)

1. **Bajar el HTML** con UA de navegador (sin él algunos bordes devuelven challenge):
   ```bash
   curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36" \
     -o /tmp/share.html -w "http=%{http_code} bytes=%{size_download}\n" "<url>"
   ```
   Un share real ronda **~1 MB de HTML** y `http=200`.
2. **Localizar el payload:** `<script>window.__reactRouterContext.streamController.enqueue("[…]")</script>` (React Router v7 *single-fetch*). El argumento es un **string JS** que contiene un JSON.
3. **Des-escapar + parsear:** `json.loads('"' + literal + '"')` y luego `json.loads(...)` → sale un **array plano (formato flatten de devalue/turbo-stream)**: las referencias son índices del array, los objetos son `{"_<idx>": ref}` y los enteros negativos son literales (`-1/-2/-5` ≈ null/undefined, `-3` NaN, `-4` Inf, `-6` 0). El root está en `arr[0]`.
4. **Navegar el árbol:** `root['loaderData']['routes/share.$shareId.($action)']['serverResponse']['data']` → `linear_conversation` (nodos) + `title` + `create_time` + `sharedConversationId`.
5. **Volcar a markdown** filtrando ruido: `content_type` en `thoughts`, `reasoning_recap`, `code`, `execution_output`, `model_editable_context`, y descartando nodos cuyo texto sea exactamente `The output of this plugin was redacted`.

**Atajo:** `scripts/decode_chatgpt_share.py <url-o-html> [salida.md]` hace 1-5 (stdlib puro) e imprime el resumen.

## Límites — decirlos explícitamente al usuario

- Los outputs de **plugins/herramientas salen redactados** por OpenAI (`The output of this plugin was redacted`). En un hilo de trabajo con imágenes, esa es la mayoría de los nodos `tool`.
- Las **imágenes** en el HTML vienen como punteros internos (`sediment://file_…?shared_conversation_id=…`), **sin URL**. Pero **SÍ son descargables a resolución completa** abriendo el share en Chromium headless: la página pide URLs firmadas `https://sdmntpr*.oaiusercontent.com/files/<uuid>/raw?se=…&sig=…` que se capturan de la red. Ver sección «Descargar las imágenes generadas». (Corrección 11/09/2026: la versión anterior de esta skill afirmaba que era imposible.)
- Ojo: esas URLs firmadas **caducan** (parámetro `se`, ~24 h) y pueden no volver a firmarse igual → guardar los bytes, no el link.
- El share puede **caducar o despublicarse**: si no aparece `linear_conversation`, decirlo antes de inventar.
- Los **prompts de texto sí salen completos**: cuando el valor del hilo son prompts/guiones, la extracción se los lleva enteros.

## Descargar las imágenes generadas (verificado 11/09/2026)

El payload solo trae punteros, pero el render del share sí baja los PNG completos (~2–2,6 MB, p. ej. 941×1672). Receta:

1. Chromium headless (Playwright): `/opt/data/.venv-pw/bin/python` + `PLAYWRIGHT_BROWSERS_PATH=/opt/data/home/.cache/ms-playwright`.
2. Abrir el share y **scroll incremental** (`window.scrollBy(0,700)` + `PageDown` hasta que `scrollY` se estanque) para forzar el lazy-load de toda la conversación (los hilos largos tienen 200+ nodos).
3. Recolectar `<img>` cuyo `src` matchee `/files/[0-9a-f-]+/raw` y **guardar el `alt`** — ahí viene el título real de cada generación (`Generated image: <título>`). Filtrar sprites del shell (`chatgpt.com/cdn/assets/…`).
4. Descargar cada `src` con `ctx.request.get(url)` (conserva cookies/referer) y escribir los bytes con extensión según magic bytes.
5. Guardar `index.json` con `{file, bytes, alt, source_url}` y armar una **hoja de contactos** (PIL está en `/opt/data/.venv`, no en `.venv-pw`) para revisar todo con `vision_analyze` en 2 llamadas en vez de 18.

**Script:** `scripts/fetch_share_images.py <url> <out_dir>` (Playwright + dedupe + index.json).

**Pitfall:** el número de PNG descargados puede ser **menor** que el de punteros `sediment://` del payload (los adjuntos que subió el usuario no se renderizan igual) → reportar ambos números, no inventar el faltante.

## Pitfalls

- **"El HTML no trae los mensajes" es falso por defecto.** No buscar `"parts"` sin escapar (da 0 coincidencias: en el payload están como `\"parts\"`): primero extraer y des-escapar el string, después buscar.
- **`og:title` es genérico** ("Échale un vistazo a este chat"); el **nombre real del hilo está en `<title>`** ("ChatGPT - <título>").
- **`arr[0]` es un índice válido** al decodificar: no tratarlo como el literal `0` (bug real que devolvió un `int` en vez del objeto raíz).
- Guardar la extracción en el workspace del agente (`workspace/recon/<share-id>/`), no en `/tmp`.

## Verification

Reportar: título, id del share, **conteo de mensajes por rol**, ruta del archivo guardado y 1-2 fragmentos textuales citados. Sin eso, no afirmar que se leyó.

## References

- `references/chatgpt-share-ssr-payload.md` — formato del payload, marcadores exactos y caso trabajado (números reales).
- `scripts/decode_chatgpt_share.py` — decodificador re-ejecutable (URL o HTML guardado → markdown).
