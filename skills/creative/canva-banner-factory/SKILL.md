---
name: canva-banner-factory
description: "Use when producing TV banners, venue posters, or real-world mascot composites (Golden Game / Grand Paradise) in 16:9 Full HD, with local Pillow composition or Canva MCP."
author: Ragnar (NeuralCrew Labs)
metadata:
  hermes:
    category: creative
    tags: [canva, banners, tv, produccion, mcp, mundo-real, casinos, composicion]
---

# Real-World TV Banner & Canva Factory Skill

Estándar probado en producción (campaña «El Aguinaldo» 2026, v12/v3) para producir sets de **20+ banners 16:9 (`1920×1080`)** para televisores de sala (rotación de **5 slides por pantalla** = 1 banner personalizado de sede + 4 piezas generales por marca) combinando fotografías reales de los casinos, mascotas 3D de marca (Goldie / Lucky), tipografía display profesional y el Portal Único de Producción.

---

## 1. Reglas de Oro Aprendidas en Producción (No Negociables)

1. **La fotografía real de una sede NUNCA pasa por un modelo generativo (GPT/Flux/Seedance):**
   - **Por qué:** Incluso con instrucciones explícitas de `SIGN PRESERVATION`, los modelos de imagen re-renderizan la foto y borran o deforman los letreros, pendones y marquesinas reales del local, o inventan pseudo-texto en pantallas de máquinas.
   - **Método obligatorio para banners de sede:** Generar únicamente la mascota de cuerpo entero sobre fondo chroma magenta plano (`#FF00FF`) y componerla localmente en Python/Pillow sobre la fotografía real intacta.

2. **Prohibido usar fotografías verticales con relleno desenfocado o cajas rectangulares de texto:**
   - **Por qué:** Pegar una foto vertical (`738×1600`) a la derecha y rellenar el resto con blur crea una costura vertical dura («imagen mal configurada»). Asimismo, poner una caja rectangular oscura detrás del texto produce un segundo corte vertical artificial.
   - **Método obligatorio:**
     - **Placas 100% horizontales a sangre (`1920×1080`):** Seleccionar tomas horizontales (`w >= h`) o extraer un encuadre horizontal limpio `16:9` de una toma amplia.
     - **Degradado lateral continuo (0 costuras):** Usar un `side_gradient` suave con curva cúbica (`t = 1 - z²(3 - 2z)`) desde `x=0` hasta `x=68% W` (opacidad máxima al 28% izquierdo y desvanecimiento orgánico hasta 0), sin cajas rectangulares.

3. **Cero clientes, empleadas o transeúntes visibles en el fondo (Privacidad + Estética):**
   - **Por qué:** Las fotos de WhatsApp de las sedes suelen tener clientes jugando de perfil, transeúntes en la acera, personal en caja o desorden en mostradores (atomizadores de limpieza, bolsas, monitores con escritorio de Windows, o letreros de otra marca como «Casino Zeus»).
   - **Auditoría previa obligatoria:** Antes de componer, generar hojas de contacto numeradas (`qa_sheets/sheet_<brand>_<sede>.jpg`) marcando orientación `[H/V w×h]` y pasar `vision_analyze` para filtrar y recortar encuadres **100% libres de personas reales y de desorden**.

4. **Separación estricta Texto vs. Mascota y Contraste de Logos:**
   - **Zona de texto:** Siempre a la izquierda (`side="left"`, `x0=104`, `COLW = 44% W`), incluyendo `tunja_lucky`. Jamás usar `side="right"` si la mascota también va a la derecha.
   - **Zona de mascota:** A la derecha (`target_h = 0.70 H`, `x = 0.655 W`, `y = H - target_h - 74`), con **despill cromático** (`si r > g+60 y b > g+60 -> limitar b y r`), **sombra proyectada** (`blur=26`) + **elipse de contacto bajo los pies** (`blur=16`, `alpha=190`) para que la mascota pise firme el suelo y nunca flote.
   - **Placa de contraste detrás del logo:**
     - **Golden Game:** Placa oscura translúcida (`tint=(8,8,12), alpha=175, radius=22, blur=10`).
     - **The Grand Paradise Club (Lucky):** Como su logo tiene tipografía cursiva en rojo granate y dorado, sobre fondo oscuro se pierde. Usar **placa clara marfil/dorada** (`tint=(252,245,225), alpha=215, radius=20, blur=6`).

5. **Piezas generales con GPT/Codex (`driver_general.py`):**
   - Para las 4 piezas generales de rotación por marca (`participas`, `final`, `jornadas`, `sede`), usar Codex/GPT con las hojas oficiales de identidad (`ref-goldie-identidad.png` + `ref-goldie-navidad.png` o `ref-lucky-hoja-v2.png` + `ref-lucky-arte-base.png`).
   - Incluir en el prompt:
     - `TOOLING: produce the final image with the built-in image generation tool and save it as poster.png. Do NOT call CLI scripts.`
     - `BACKGROUND TEXT: any screen, monitor or poster in the background must be in soft bokeh without readable words; zero pseudo-text.`
     - **En piezas GENERALES (rotan en todas las sedes), prohibir además fachadas y rótulos con nombre de sede real** (p. ej. el letrero de una sala concreta): el mismo PNG se replica en la TV de cada sede y mostrar la fachada de una en las demás es un error de contenido que solo se detecta leyendo el fondo de la pieza ya publicada. Fachada con nombre solo es válida en el banner propio de esa sede.
     - `BRAND PALETTE`: prohibir paneles verdes en Golden Game (solo vino/oxblood + oro); en Lucky usar verde bosque + vino + oro.
   - Normalizar siempre la salida de GPT (`1672×941` o `1717×916`) a **`1920×1080` exactos** con `Image.LANCZOS`.

---

## 2. Pipeline Técnico de Ejecución (Paso a Paso)

### Paso 1: Curaduría y recorte de placas 16:9 sin personas
1. Generar hojas de contacto numeradas de `venue_photos/{golden,lucky}/<sede>/`.
2. Inspeccionar con `vision_analyze` preguntando explícitamente por: orientación H, presencia de clientes/peatones (incluso parciales en bordes) y objetos de desorden.
3. Si una foto H tiene un peatón o gorra en un borde lateral, aplicar un sub-recorte limpio (`crop_16_9(path, x_range=(x0, x1), y_range=(y0, y1))`) y guardar en `plates_v10/plate-<slug>.jpg` a `1920×1080`.
4. Verificar los recortes en una hoja de candidatos (`sheet_candidates.jpg`) con `vision_analyze` hasta lograr **0 personas en las 12 sedes**.

### Paso 2: Cutouts de mascota + Composición determinista (`compose_v7.py`)
1. Generar cutouts sobre `#FF00FF` (`driver_cutout.py`). Cachear `chroma_to_rgba()` en memoria (`_CHROMA_CACHE`) para que renderizar las 12 sedes tome **< 8 segundos** (sin caché tarda > 60s y da timeout).
2. Ejecutar `compose_v7.py` y verificar la hoja de contacto `sheet_final.jpg` con `vision_analyze`.

### Paso 3: Publicación en el Portal Único (`reels.neuralcrewlabs.com`)
- **Arquitectura de acceso en PROD (`nginx-proxy-manager` host 20):**
  - La raíz `/` y `/campanas/` están detrás de `oauth2-proxy-universal` (SSO interno).
  - La ruta `/assets/` tiene **bypass de SSO** en Nginx (`HTTP 200` público directo).
- **Para que el cliente vea exactamente el mismo Portal Único que nosotros sin pedirle login:**
  1. Registrar las fichas de la campaña en `portal/reels/{golden,lucky}/<campana>.json` apuntando a fragmentos en `portal/libro/{golden,lucky}/<campana>/`.
  2. Ejecutar `.venv/bin/python scripts/build_portal_libro.py` (genera `assets/portal/index.html` con sidebar, selector de cliente y todas las secciones) y correr `pytest tests/test_portal_libro.py tests/test_portal_reel_assets.py`.
  3. Desplegar el HTML generado tanto a `/opt/reels/index.html` (raíz con SSO) como a `/opt/reels/assets/portal/index.html` (espejo público sin SSO).
  4. El `app.js` del portal soporta hash routing automático (`#golden-<slug>-...` o `#lucky-<slug>-...`), cambiando de cliente y haciendo scroll directo a la sección:
     - **Link público Portal Único (Golden Game):** `https://reels.neuralcrewlabs.com/assets/portal/#golden-2026-11-aguinaldo-banners-tv`
     - **Link público Portal Único (Grand Paradise / Lucky):** `https://reels.neuralcrewlabs.com/assets/portal/#lucky-2026-11-aguinaldo-banners-tv`
  5. Agregar cache-busting (`?t=MMDDx`) a los `src` de imágenes cuando se reemplace un archivo con el mismo nombre para evitar caché de Cloudflare/navegador.

---

## 3. Capa Canva MCP (Cuando se requiere plantilla editable en Canva)

| Objetivo | Tool MCP | Regla clave |
|---|---|---|
| Subir PNG | `create_upload_url` + `curl -X POST --data-binary` | URL de un solo uso (`application/octet-stream`) |
| Inspeccionar | `start_editing_transaction` | Devuelve `transaction_id`, `richtexts` y `fills` |
| Limpiar basura IA | `delete_element` | Borrar todos los `fills` decorativos **excepto el primero** (fill de página) |
| Reemplazar fondo | `update_fill` en el fill de página | Pasar el `mediaId` del arte sin texto (`bg_only=True`) |
| Editar textos | `replace_text` + `format_text` + `position_element` | **Prohibido** `resize_element` en `TEXT` (falla en API) |
| Guardar cambios | `commit_editing_transaction` | Solo recibe `transaction_id` y `user_intent` |
| Escalar a N sedes | `copy_design` | No gasta créditos de IA; cambiar fill y sede por copia |

---

## 4. QA del Set Publicado (pre-entrega al cliente)

Ejecutar SIEMPRE sobre las URLs públicas finales (no sobre los archivos locales) antes de declarar el set listo:

1. **Integridad en vivo:** `curl -s -o file -w '%{http_code} %{size_download}'` por asset (todas 200) + verificación con PIL de que cada PNG es exactamente `1920×1080`. Reportar peso por pieza y total.
2. **Texto crítico por pieza:** pasar `vision_analyze` pidiendo transcripción literal de encabezado, línea de sede, fechas y premio, y confirmar que la marca/sede corresponde al archivo (`tunja` dice Tunja, `calera_centro` dice La Calera Centro, etc.).
3. **Fechas contra calendario real:** validar con `datetime` que cada fecha prometida cae en el día de la semana anunciado (p. ej. todos los miércoles) — jamás a ojo; un desbalance de día/mes rompe la credibilidad del set completo.
4. **Texto pequeño con crop-then-zoom:** para leer o confirmar texto pequeño (pósters de fondo, letra legal), recortar primero la región con PIL y ampliarla (`crop.resize(3x, Image.LANCZOS)`) antes de `vision_analyze` — la lectura a imagen completa pierde o alucina texto pequeño, y un presunto typo debe confirmarse en crop ampliado (idealmente dos lecturas) antes de reportarlo o descartarlo.
5. ** Severidad de texto garbled de IA en fondos:** artefactos tipo letras inventadas («GOLDE GAME», «PIOE») en escena generada se reportan pero no fuerzan re-roll si son ilegibles a distancia de TV; texto legible a distancia de lectura sí bloquea la entrega.
6. **Peso para TV por WiFi:** presupuesto ~2 MB por PNG; un set de 20 piezas ronda 40+ MB. Si las TVs cargan lento, servir WebP (o AVIF) o precargar el slide 1 en el HTML de rotación.
