---
name: vendor-pricing-research
description: "Use when comparing live API/model pricing across providers."
tags: [pricing, precios, api, llm, proveedores, costos, research, brokers]
---

# Vendor Pricing Research (APIs / modelos / brokers)

## Cuándo usar
- Necesitas precios REALES actualizados de proveedores de API (video, imagen, LLM, brokers) para comparar costos por clip, por token o por segundo.
- No hay base de precios interna o la hoja quedó vieja y hay que re-verificar contra las páginas oficiales.
- Los típicos `web_search` / `web_extract` no están configurados (falta FIRECRAWL key) y hay que llegar por otra vía.

## Método (de preferido a fallback)
1. **curl directo con UA de navegador** a la página de precios. Funciona si la página es SSR/HTML plano:
   `curl -sL --max-time 25 "<url>" -H "User-Agent: Mozilla/5.0 ... Chrome/120.0"`
   Limpiar HTML con `sed 's/<[^>]*>//g'` y filtrar por regex del precio.
2. **Browser CDP para páginas JS** (Next.js/SPA tipo `siliconflow.cn/pricing`, `volcengine`, `alibabacloud.com`): `browser_navigate` y extraer con `browser_console` → leer `document.body.innerText` y recortar con `.slice()` en torno a la sección buscada, o clicar pestañas (p.ej. Together: pricing divide en tabs CHAT/VISION/IMAGE/AUDIO/VIDEO/…).
   - No vuelques toda la página: las páginas de precio son gigantes (miles de elementos); extrae solo el slice del nombre de modelo buscado.
3. **Buscadores**: Bing y DuckDuckGo por `curl` bloquean con CAPTCHA/vacío. DDG **funciona vía browser_navigate** (`https://duckduckgo.com/?q=...`). Útil para localizar el doc canónico (p.ej. `wan 计费 元/秒`).
4. **Aliyun**: los enlaces `help.aliyun.com/zh/...` dan 404/redirigen. La web **internacional** `www.alibabacloud.com/help/en/model-studio/model-pricing` SÍ carga y tiene tabla completa. Generaliza: ante páginas chinas rotas, probar el canto internacional.

## Trampa de modelo de facturación (CRÍTICO)
Los proveedores cobran el video/inferencia de formas distintas — SIEMPRE normaliza antes de comparar:
- **Flat por generación**: p.ej. SiliconFlow Wan2.2 = ¥2.00/video, sin importar duración. Para clips más largos que una generación, multiplica (¿2 generaciones + unión?).
- **Por segundo de salida**: p.ej. Alibaba Model Studio `wan` = $/s de video generado, `Coste = precio/s × duración`.
- **Por token**: p.ej. Volcengine seedance, `precio = token单价 × tokens` con `tokens = (duración) × W × H × fps / 1024`.
- **"Lowest setting" trampa**: varias páginas (Together) muestran el ajuste mínimo (resolución/duración mínima) y el real para 720p/6s puede subir.

## Entrega
- Tabla Markdown `Proveedor | Modelo | $/clip | Audio nativo | Verificado/Estimado | Notas`.
- Cerrar con el proveedor más barato del grupo y una estimación para el volumen pedido (p.ej. ×5 clips).
- Marcar **✅ Verificado** (precio de tabla oficial) vs **⚠️ Estimado** (lowest setting, promo, GPU/sec, no encontrado). Nunca inventar el número.

## Referencias
- `references/ai-video-asian-brokers-2026-08.md` — precios verificados 19/08/2026 de SiliconFlow, Kluster (FUERA), Together, Volcengine seedance, Alibaba Model Studio wan. Datos por $/clip 6s 720p I2V.
- `references/fal-models-discovery-2026-08.md` — catálogo de modelos **audio/TTS y video de fal.ai** (ElevenLabs, MiniMax, Qwen3-TTS, etc.) + patrón de PROBE de endpoint a costo CERO sin key ni saldo.

## Catálogo y probe sin gastar (fal.ai, 19/08/2026)
- **La página de un modelo de fal es una SPA (JS)** — el schema NO está en el HTML plano (no saquees la página del modelo con curl). Pero el **catálogo** SÍ expone los IDs en HTML: `curl "https://fal.ai/models?view=audio"` y `re.findall(r'href="(/models/[^"#]+?)"')` devuelve todos los endpoints de la categoría.
- **Probe de existencia del endpoint SIN costo ni key**: haz `POST https://queue.fal.run/<model-id>` con header `Authorization: Key invalid_test_only` y cuerpo mínimo. **401 = el endpoint existe** (la ruta es válida, solo falla la auth → cero gasto, cero generación). **404 = no existe** (o el ID está mal). Esto permite confirmar el modelo correcto antes de gastar.
- **Elegir voz TTS sin créditos**: los demos web propios del proveedor (MiniMax speech demo, ElevenLabs https://elevenlabs.io/text-to-speech) aceptan texto libre gratis — para validar pronunciación (nombres propios, ciudades) pegar el guión completo del reel; no genera en fal ni toca la key del broker. ElevenLabs expone voces premade vía `GET https://api.elevenlabs.io/v1/voices`.
- **No confiar en el precio listado de fal para TTS**: fal cobra por tokens; la tarifa por 6s de una generación NO es directamente el $/clip de voz. Validar contra el dashboard del usuario tras 1 run real (regla dura: los costos de subagente se confirman con el proveedor, no se estiman).

## Auditoría de ads de comparación de precios (agregadores, verificado 28/10/2026)
Cuando un agregador (Sunra, etc.) publica una tabla "nosotros vs rivals" contra una captura de pantalla, el precio de cada fila se verifica en DOS capas antes de creerlo:
1. **Ancla = precio de lista del maker (fuente primaria):**
   - **Google / familia Nano Banana:** `ai.google.dev/gemini-api/docs/pricing` publica el equivalente por-imagen en texto plano (NB 2.1 1K = $0.0336; Nano Banana Pro 1K/2K = $0.134, 4K = $0.24). Leer con browser: `document.body.innerText` + regex del bloque "Nano Banana Pro" — la página puede renderizar localizada.
   - **OpenAI gpt-image-\*:** NO publica precio por-imagen, solo tarifa por token ($30/1M image output tokens). Convertir: tokens_por_imagen × tarifa (1024×1024 high ≈ 1756 tokens ≈ $0.0527). Páginas de terceros (kavel.ai, tokencost.app) sirven de cross-check.
   - **ByteDance (Seedream/Seedance):** no hay página de precios limpia; BytePlus ModelArk y páginas de revendedores (pika.dev) publican tiers por resolución (Seedream 5.0 Pro: 1K $0.045, 2K $0.09). Precios por segundo de video se derivan de ejemplos de clip completo.
   - **Kling:** `klingai.com/global/dev/pricing` (1 Unit = $0.14). Las versiones nuevas suelen estar en "preview price" con API cerrada — marcarlo en la comparación.
2. **Rival:** la página de MODELO de cada agregador manda sobre el texto hero (los precios del hero se desfasan; p.ej. fal Seedance 2.5 720p = $0.473/s cuando el ad decía $0.462).

**Trampas recurrentes de estos ads (llamarlas siempre):**
- **Ahorro solo en algunas filas:** recalcular TODAS las filas; en el caso Sunra, Kling 4.0 y GPT Image 2.5 costaban IDÉNTICO en fal (cero ahorro) y solo Seedance (−51%) y Seedream 2K (−33%) mordían.
- **Celdas "No API" del rival:** verificar contra los docs del competidor; suelen ser falsas (Higgsfield SÍ tiene API self-serve con 50+ modelos en docs.higgsfield.ai, incluidos Nano Banana Pro y Seedream).
- **Settings escogidos a mano:** la tabla compara el setting caro (720p+audio, high, 2K) mientras la propia página del agregador anuncia "desde $" con el setting barato del mismo modelo.
- **Límite honesto:** sin cuenta/key no se puede confirmar el DÉBITO real — solo que el claim coincide con el precio de lista del maker. Cerrar siempre recomendando un test pago chico (1 modelo, 1 setting, 1 clip) comparando débito real vs incumbent antes de migrar gasto.

**Sunra específico:** catálogo API público sin key en `api.sunra.ai/v1/models` (paginar con `?limit=200` siguiendo `has_more`/`url`) pero NO expone campos de precio en ningún lado (metadata ni openapi). Su claim "cobra precio maker sin fees" es declaración propia replicada por reseñas; la empresa es Second Enlightenment Global Pte Ltd (Singapur, UEN 202530874K) y monetiza con app de suscripción ($12/$29/$125/mes) + enterprise.

## Pitfalls
- **Verifica que el servicio siga vivo**: los brokers del segmento desaparecen rápido. p.ej. Kluster.ai fue adquirido por MITO y suspendió servicios el 9/jun/2026. No propongas un broker sin confirmar status (title/meta "joined X" o redirect).
- **Moneda**: sé explícito con el tipo de cambio USD↔CNY (≈7.1) al convertir ¥ a $.
- No asumas que un modelo existe en un proveedor; verifica en la lista pública (p.ej. no todo broker hostea Wan2.7; algunos solo Wan2.2).
- Un 404 en el sitio china de precios no significa que no exista el modelo/percio; usa el doc canónico internacional + buscador.