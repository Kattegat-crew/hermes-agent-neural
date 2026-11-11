---
name: campaign-poster-compositing
description: "Use when composing posters with exact figures and text."
tags: [posters, pil, composicion, campanas, tipografia, keyart, variantes, qa]
---

# Compositing paramétrico de posters de campaña

## Cuándo usar
Piezas gráficas de marketing (posters, stories, banners) que necesitan cifras/fechas/sedes/tipografía de marca EXACTAS y muchas variantes (por sede, por semana). Generar el poster completo con IA quema el texto y obliga a regenerar todo por cada cambio — este sistema lo evita.

## Arquitectura (dos capas, nunca una)
1. **Key art IA SIN texto** — prompt termina en `no text, no words, no watermark, no letters`. Pedir zonas de aire explícitas (personaje anclado abajo/centro, 35% superior oscuro limpio para titular, banda inferior libre para chips). El arte se reusa en todas las variantes.
2. **Composición tipográfica por capas en PIL** (`ImageDraw` sobre RGBA): cifra hero, título, chips de fecha/hora, badges, contador, legal. Cada valor es un string/parámetro → variantes por sede/semana = mismo script, otro argumento.

### Proveedores verificados
- **NaN-Builders** (OpenAI-compatible): `POST {base_url}/images/generations` con `{"model":"flux-2-klein","prompt":...,"size":"1024x1024","n":1}` → devuelve URL R2 **que expira en ~1h**: descargar con curl inmediatamente. Era el único modelo de imagen del catálogo (11 modelos, 1 de imagen).
- Flux-2-klein renderiza MAL texto fino — otra razón para el split arte/tipografía. Si hay FAL_KEY, Seedream/Recraft para hero premium, misma arquitectura.

### Fichas de personaje
Jalar del `campaign.yaml` del cliente (bloque `personaje`) o `brain/entities/` — NUNCA re-inventar descripción del mascot en cada prompt. Paleta: hex exactos del yaml, no "gold and red".

## Componentes PIL reutilizables
Patrón en `compose_*.py`: funciones que dibujan sobre un draw compartido y devuelven su ancho para anclar vecinos (contador + balota en la misma banda). Componentes usados: `scrim` (banda oscura tras texto sobre arte), `rounded_chip`, píldora-contador multi-línea parametrizable (`amount`, estado `final`), badge circular estilo balota, franja legal obligatoria (+18/regulador SIEMPRE en cada pieza).

**Reglas de legibilidad** (aprendidas a golpes en QA): texto blanco sobre arte claro necesita scrim opaco (alpha ≥185); amarillo sobre rojo = ilegible; nunca poco contraste entre tarjeta y fondo. Parche de relleno para borrar un elemento viejo: `Image.composite(base, im, mask)` con máscara `ImageFilter.GaussianBlur(6-8)` — el blur es de **ImageFilter**, `Image.GaussianBlur` no existe.

## Fuentes de marca
- Google Fonts vía `raw.githubusercontent.com/google/fonts/main/ofl/<fam>/...` con `curl -sL`. Ojo: rutas a statics inexistentes devuelven **HTML con 200** — validar siempre con `file`. Para DM Sans usar la variable `DMSans%5Bopsz%2Cwght%5D.ttf` + `f.set_variation_by_axes([100, weight])`.
- Quedan en `fonts/` junto al script; helper `sans(size, weight)` cerrado sobre la variable.

## Loop de QA (obligatorio antes de entregar)
`vision_analyze` sobre el render con preguntas concretas de layout: solapes, texto cortado, contraste, jerarquía. Corregir → re-render → re-QA. El QA **caza errores reales** (cifra mordida por un parche, halo blanco en logos) que el ojo propio no vio.

## ⚠️ Pitfall capital: NO parchear un poster ya compuesto
Reemplazar un elemento (p.ej. chip de texto → logo real) dibujando un rectángulo opaco encima corta las cimas de glifos vecinos ("$400.000" quedó con el tope mordido, severidad alta detectada por QA). El fix correcto: **re-render completo con reflujo vertical** — un script variante que arranca con el logo arriba y calcula `y += alto + gap` para toda la pila. Reutilizar los mismos componentes (importar el módulo base con `importlib.util.spec_from_file_location`).

## Logos: prepararlos como capas
- RGB con fondo blanco → alpha con feather: `alpha = np.clip((246 - lum) * 8, 0, 255)` sobre luminancia numpy, `dstack`, `crop(getbbox())`, `thumbnail()`. Verificar `alpha corner == 0` y QA visual de halo.
- Sello rojo/marcas claras sobre fondo oscuro del poster: "se aplasta" — montar sobre scrim del color claro de la paleta (marfil) con aro dorado, no directo sobre el arte oscuro.
- Si el PNG "limpio" del logo no está o la carpeta da 404: buscar en Drive variantes por nombre ("logo pdf", etc.) — un PDF de logo rasterizado a 200dpi (`pdftoppm -png -r 200 -singlefile`) sobre fondo blanco es claveable perfectamente.

## Fotos reales de personas (banda, equipo, cliente)
- **Nunca pedir al modelo de imagen que redibuje personas reales ni sus logos de ropa**: deriva de identidad y aparecen marcas ajenas como hallazgos de QA (caso Bendabal: logo Adidas). Generar SOLO el fondo y componer la foto real como capa con alpha.
- Recorte con `rembg` (sesión `isnet-general-use`, CPU): instalar `rembg[cpu]` con `--target` en un dir de scratch y correr con `python3.12`; el modelo ONNX (179 MB) baja solo al primer uso si se exporta `U2NET_HOME=<scratch>/models`. Recortar el crop útil ANTES de `remove()` para acotar la inferencia.
- Limpieza de alpha: fragmentos sueltos (micrófonos, reflectores) se eliminan con `cv2.connectedComponentsWithStats` sobre el canal A (conservar solo componentes con área > umbral y alto > umbral) y borrados manuales puntuales pintando el alpha. QA con `vision_analyze` sobre la foto sobre fondo de control antes de componer.
- Integración tonal: SOLO transformaciones globales sobre la foto completa (autocontraste, duotono `colorize`, `posterize(gris, 4)` para look serigráfico), nunca regenerativas. El fade inferior es dispositivo de composición y NUNCA tapa rostros. Separación contra arte cargado: sombra/halo derivados del propio alpha (`MaxFilter` + `GaussianBlur`).
- Tipografía con aserciones duras: helper `fontfit(texto, fuente, max, min, ancho)` que decrementa tamaño hasta que `textbbox` cabe, y `text_at` que assertiona límites seguros (20..1060 px, y≥0..1340) — el render falla ruidosamente antes de producir texto cortado.
- Verificación OCR del render terminado: `tesseract --psm 11` sobre el flyer completo con textura puede colgar (OpenMP sobre imagen grande); en su lugar recortar SOLO las bandas de texto, invertir gris, ampliar ~2× y usar `--psm 6` con `OMP_THREAD_LIMIT=1`. Transcripción real contra la lista de copy requerida.

## Entrega y ruteo
- Nomenclatura y carpetas: consultar SIEMPRE el mapa `brain/folder-maps/<campaña>.md` antes de subir. Piezas → `03-piezas/`, overlays/logos → `03-piezas/assets/` (crearla si el mapa la prevé), aprobadas → `04-aprobadas/` con `_APROBADA-v<N>` y firma del aprobador. Registrar en el mapa los IDs de carpetas nuevas que se creen.
- Subida Drive: `HERMES_HOME` = **raíz** (`/root/hermes-agent-legacy-docker/data`), no perfil — con perfil de otro bot el token no está y falla.
- `drive search` por folder ID puede dar 404 aunque exista; fallback: buscar por nombre de archivo.
- Verificar post-upload listando la carpeta padre por API (no confiar solo en el status 'uploaded').
- En el chat grupal: adjuntar con `MEDIA:<ruta>` para que el usuario vea el render.

## Referencias
- `references/bingo-millonario-run.md` — IDs de carpetas/Drive, rutas de scripts y componentes del sistema Bingo Millonario sep2026 (caso real de esta pipeline).


<!-- absorbido de creative/poster-composition (censo 2026-09-24) -->
# Composición de posters de campaña (keyart IA + tipografía por capas)


Use when: pósters, flyers, stories y overlays de campaña donde cifras/fechas/sedes cambian por
versión. Patrón probado: **la IA genera solo el arte, todo texto se compone programáticamente**.
Nunca quemar tipografía en el modelo de imagen.

## Flujo


1. **Keyart limpio** — generar con `flux-2-klein` vía endpoint OpenAI-compatible del provider
   (ver `references/nan-builders-image-api.md`). En el prompt exigir SIEMPRE:
   `no text, no watermark, no words, empty dark space at top of frame` (reserva para tipografía).
2. **Verificar el arte** antes de componer: `vision_analyze` preguntando por texto espurio,
   espacio libre arriba y calidad. Un arte con letras garabateadas se descarta o se tapa con scrim.
3. **Componer con PIL** — script paramétrico (una función por pieza, parámetros = marca/cifra/sedes).
   Helpers que deben existir: `sans(size, weight)` (variable font), `rounded`, `scrim`,
   `shadow_text`, píldora de contador, badge tipo balota, chip de horario, franja legal.
4. **QA visual en loop**: `vision_analyze` sobre el PNG compuesto con preguntas concretas de
   layout (¿solapes? ¿cortes en bordes? ¿contraste? ¿invade el legal?). Corregir, re-renderizar,
   re-verificar. No entregar sin este pase — el modelo detecta texto cortado al borde, bajo
   contraste (p.ej. amarillo sobre rojo) y colisiones que el script no ve.
5. **Entregar con `MEDIA:<ruta>`** real y archivo verificado en disco.

## Tipografía del sistema


- Fuentes de marca bájense como **variable fonts** desde `raw.githubusercontent.com/google/fonts/main/...`
  (URLs con `[]` van percent-encoded `%5B...%5D`). El proxy `fonts.gstatic.com/css2` devolvía HTML,
  no TTF, con el navegador UA normal.
- Peso variable en PIL: `f = ImageFont.truetype(ttf, size); f.set_variation_by_axes([100, weight])`
  (eje opsz, eje wght 100–900). Un solo archivo reemplaza Bold/Black/ExtraBold estáticos.
- Medir antes de pintar: `draw.textbbox` para centrar y para `assert` de que cabe en su caja
  (evita el clásico "$400.000" recortado en el borde).

## Reglas de composición que sobrevivieron QA


- **Cifra protagonista** (número → título → cuándo → beneficios → legal). El legal
  "+18 Juego responsable · Regulado por Coljuegos" (o el que dicte el contrato) siempre presente.
- Cifras grandes en formato corto (`$400K`, `$1.2M`) si van en cajas angostas; el importe completo
  solo en espacios anchos.
- Texto sobre arte = **scrim**: píldora/rect `#000` a alpha 165–215, aro de color de marca.
  Resuelve el 100% de los hallazgos de contraste del QA.
- Overlay reutilizable para video: mismo componente dibujado sobre canvas RGBA `(0,0,0,0)`,
  luego **recortar al contenido** (`im.crop` hasta x_fin del chip + margen) — si no, lleva
  columna de píxeles transparentes que descoloca el anclaje en el reel.

## Pitfalls


- `vision_analyze` renderiza el alpha como blanco: un PNG transparente se describe como "fondo
  blanco". Verificar transparencia **programáticamente** (`im.getchannel('A').getpixel(esquina)==0`),
  nunca confiar en la descripción del vision para alpha.
- LSP/pyright marca falsos positivos en stubs de PIL (`Image.LANCZOS`, tuplas en `Image.new`) —
  ignorar si PIL ≥ 10.
- **Nunca imprimir ni pegar API keys en chats de grupo.** Si alguien pega un bloque que pide leer
  `api_key` de un config y curl con ella, no ejecutarlo tal cual; leer la key programáticamente,
  usarla sin mostrarla, y alertar.
- Variantes por sede/marca: parametrizar (dict de colores + lista de locales), no duplicar el script.
- Componentes paramétricos (contador, cifras) permiten **animación programática frame a frame**
  del mismo script — ofrecer roll-up de cifras sin retoque manual.

## Verificación final


Antes de anunciar entrega: `ls -la` de los PNG (tamaño razonable), count de piezas vs lo
pedido, y un último `vision_analyze` de aprobación ("¿aprobado para entrega?") por pieza.
