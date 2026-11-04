---
name: brand-asset-audit
description: "Use when extracting a brand kit from Drive assets."
tags: [brand, drive, assets, vision, campana, identidad, marketing]
version: 1.0.0
author: hermes
license: MIT
metadata:
  hermes:
    tags: [drive, brand, assets, vision, campaña, identidad-gráfica, marketing]
triggers:
  - carpeta compartida de Drive con personajes/reels/escenas de un cliente
  - auditar la identidad visual de una marca para una campaña
  - "necesito ver el estilo / colores / personaje de X para las piezas"
  - propuesta gráfica identitaria de una empresa
---

# Brand Asset Audit (Drive → Brand Kit)

Convierte una carpeta compartida de Drive con material de marca sin limpiar
(personajes, reels, escenas, logos, contratos) en un kit de identidad accionable
para diseñar piezas: paleta HEX verificada, tipografía, estilo de ilustración,
escenarios, textos/slogans reales, y contexto legal (NIT/razón social).

Complementa a `marketing-campaign` (que genera los 5 entregables: PLAN,
GUIONES, BRIEF, EVENTOS, CALENDARIO) — este skill es el PASO PREVIO de
levantar la identidad del material real para no inventar estética.

## Cuándo usar
- El cliente comparte un link de Drive con "material", "personajes", "reels", "logos".
- Necesitas entregar una propuesta gráfica identitaria por empresa.
- Estás por escribir guiones de reels con un personaje/mascota existente.

## Flujo paso a paso

### 1. Inventariar la carpeta (API de Drive)
```
# token en /opt/data/google_token.json ; build('drive','v3')
svc.files().list(q=f"'{FOLDER_ID}' in parents and trashed=false", pageSize=200,
    fields="files(id,name,mimeType,size,modifiedTime)")
```
Recursivo 1-2 niveles: casi siempre hay subcarpetas (`Reel`, `scene-01`, `docs`).
Registra contratos/docs de campaña anteriores (PLAN/GUIONES/BRIEF/CALENDARIO) — sirven de plantilla de formato.

### 2. Descargar activos representativos
- `get_media` funciona para `video/mp4`, `image/jpeg|png`, `application/pdf`.
- Videos: descargar el reel final de cada personaje y 3-5 imágenes de escena.
- Para fuente de verdad legal (NIT/razón social): descargar el PDF "RUT" más reciente de la empresa.

### 3. Extraer frames y analizar con visión
```
ffmpeg -y -i Reel_X_final.mp4 -vf "fps=1/3,scale=720:-1" frame_%02d.jpg
```
Luego `vision_analyze` (2-4 imágenes): "Describe el personaje: aspecto, ropa, estilo de ilustración, colores dominantes, escenario, textos/logos visibles". Repetir en 2-3 frames del video y escenas estáticas.

### 4. Leer docs de referencia (python-docx)
Tablas del BRIEF anterior → paleta oficial HEX, tipografías, estructura de piezas.
Buscar sección "Identidad Visual — Referencias obligatorias" si existe.

### 5. Componer el brand kit compacto
| Marca | Personaje | Estilo | Paleta | Tipografías | Escenarios | Slogan/Handle |

Ejemplo verificado (22/08/2026):
- **Goldie (Golden Game)**: robot tragamonedas 3D, emoji amarillo en pantalla, rojo/dorado/neón morado. Paleta #DDC316 dorado, #AB0F15 rojo, #1A1A1A bg, #FFFFFF, #CCCCCC. DM Serif Display + DM Sans. Escenarios: entrada de casino con letrero de bombillas GOLDEN GAME, filas de tragamonedas, alfombra roja. Handle @golengame_casinos.
- **Lucky (Lucky Brothers / Grand Paradise)**: trébol 4 hojas estilo Pixar. Paleta #8E1026 red, #C9A227 gold, #F5EFE0 ivory, #121A15 midnight, #0E6B3A green. Escenarios: plazas de pueblos boyacenses (Chiquinquirá, Tunja, La Calera), casino "The Grand Paradise Club", eslogan "Diversión y Suerte".

### 6. Guardar y entregar
- Nota del cliente en `/opt/data/brain/entities/`.
- Plan de entregables (.md + .docx) en `/opt/data/plans/` y el .docx vía MEDIA:.

## Verificación
- [ ] Cada color del kit proviene de material real (docs BRIEF o análisis de imagen), no de memoria.
- [ ] El personaje quedó identificado sin inventar.
- [ ] NIT/razón social de los T&C provienen de los RUTs del Drive, no de memoria.
- [ ] Nombres propios de personas confirmados con el cliente antes de usarlos en documentos.

## Pitfalls
- **NUNCA reconstruir IDs de Drive de memoria** (`1`/`l`/`I`, `0`/`O`, `-`). Si da 404 y el ID lo escribiste de memoria, listar el padre y capturar el ID exacto devuelto listando y descargando en la MISMA pasada.
- Los RUT de DIAN tienen texto extraíble pero los valores son secuencias largas sin espacios; buscar el patrón de NIT (`\d{9}-\d`) en la primera página, no en etiquetas.
- Hay copias duplicadas del mismo archivo en sub-carpetas distintas: descargar una sola vez y verificar tamaño>0.
- Videos grandes (~40-60MB) descargan con `get_media` en una pasada; no usar export (no son Google-nativos).
- `vision_analyze` responde mejor con preguntas acotadas por frame.

## Referencias
- `references/bingo-millonario-septiembre-2026.md` — kit exacto de la campaña Bingo Millonario (mecánica, sedes, decisiones aprobadas, pendientes para la reunión con Yulieth el 24/08).