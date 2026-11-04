# Arte premium de campaña: workflow con generadores de imagen (fal.ai) + fichas de personaje

Detalle de la sesión Bingo Millonario (26/08/2026) sobre cómo subir el acabado visual de las
piezas de campaña de "OK" a "premium y profesional". Complementa `marketing-campaign-pipeline`.

## El problema real (dónde se quedaba corto flux-2-klein)

Los posters salían con buen layout/estructura pero se sentían "mediocres". Diagnóstico honesto
con el equipo: flux-2-klein **no es el actor que limita el texto** — la tipografía de los
posters YA se compone por capas paramétricas (`compose_posters.py`, cambia cifra/sede/fecha por
parámetro). Lo que flux entrega flojo es el **arte base** (el "hero"): iluminación, materiales,
textura de casino premium.

**Regla del sistema:** NUNCA quemar tipografía en el render IA. La IA genera SOLO el arte base
(hero); el texto (BINGO MILLONARIO, cifra, "VIERNES DESDE 5PM", contador) y los logos van por
capas encima. Si un modelo quema texto, se pierde la ventaja de edición paramétrica.

## Matriz de test fal.ai (misma dirección de arte, distinto motor)

Cuando hay FAL_KEY disponible, probar 3 motores con el MISMO encargo para medir solo calidad
de arte (costo total ~$0.12-0.24):

| Test | Modelo fal | Precio | Propósito |
|------|-----------|--------|-----------|
| 1 | `bytedance/seedream/v5/pro/text-to-image` (Seedream V4.5) | $0.04/img | Hero foto-realista premium (materiales, luces, bokeh) |
| 2 | `recraft/v3/text-to-image` | $0.04-0.08 | Versión gráfica/vector (P3 "escalera del bote") |
| 3 | `fal-ai/flux-2/pro` (control) | $0.03/mp | Same-prompt contra flux-2-klein para comparar |

Otros candidatos fuertes por tipografía/realismo (si hace falta): `ideogram/v3` ("posters y
logos", tipografía excepcional), `openai/gpt-image-2` (tipografía fina, el más caro),
`google/nano-banana-2` ($0.08, edición). FAL_KEY vive en `.env` del repo (comentada cuando no
hay credencial); sin FAL_KEY no hay test — es una línea de config + $0.20 de crédito.

## Fichas de personaje con fidelidad (técnica clave)

Para que el personaje salga CONSISTENTE en distintos generadores, NO describirlo de memoria:
**escanear las imágenes reales del personaje y describirlas con vision_analyze**, luego escribir
la ficha en un archivo compartido. Flujo verificado:

1. Localizar la carpeta de material del rig en Drive (ej. `Reel Goldie final`, `Reel lucky`) con
   `google_api.py drive search --raw-query "'<FOLDER_ID>' in parents"`.
2. Descargar las imágenes/escenas con vision: `curl -s -L "https://drive.google.com/thumbnail?id=<ID>&sz=w1600" -o out.bin`, renombrar a `.jpg/.png`.
3. `vision_analyze` sobre cada imagen con el prompt: "describe con máxima fidelidad: forma,
   colores exactos (hex si posible), materiales, luces, detalles, estilo 3D, pose, fondo".
4. Escribir `prompt-hero-fichas-personajes.md` con: ficha Goldie + ficha Lucky + logo verificado
   + prompt hero profesional (EN), con composición (personaje ocupa ~55%, zona ~40% limpia oscura
   para titular/logo) y negativo fijo.
5. Los prompts de personaje se jalan del campaign.yaml (`personaje:` block) y de `brain/entities/`
   para no re-inventar la descripción en cada modelo.

### Anclas de prompt hero (spec del compositor)
- Personaje anclado centro-inferior (~60% inferior del lienzo); arriba 35% oscuro/limpio para
  título+cifra; banda inferior-izquierda ~390×190px despejada para el chip contador.
- Negativo fijo: `no text, no words, no watermark, no letters on machine body`.
- Paleta desde los hex del campaign.yaml, no "gold and red" al criterio del modelo.
- Logo: verificar si la variante es transparente o con fondo sólido antes de prometer capa limpia.

## Escanear Drive (recordatorio de paréntesis)
- Los covers de reel (`.jpg`) son buenas fuentes de personaje estático.
- No todas las carpetas son accesibles con el token actual (algunas dan 404 `File not found`) —
  pedir la ubicación/logo al Admin si hace falta.