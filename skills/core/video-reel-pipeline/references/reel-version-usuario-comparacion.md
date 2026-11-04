---
name: reel-version-usuario-comparacion
license: MIT
metadata:
  hermes:
    tags: [reel, edicion-usuario, subtitulos, quemados, whisper, correlacion, comparacion]
    related_skills: [akari-video-editing, video-transcript-extraction, video-frame-verification]
---

# Reel editado por el Admin — comparación frame a frame y reparación de subtítulos

## When to Use
Usar cuando el Admin entrega SU propia edición de un reel nuestro (link Drive u otro medio) y pide:
compararla contra el master del agente, aprender de sus decisiones de montaje, transcribir el audio
nuevo y reparar elementos quemados acotados (típicamente subtítulos descuadrados), preservando su
edición como base. No aplica a reels generados de cero (usar reel-pipeline) ni a posts externos de
terceros (usar analisis-video-post-externo).

Escenario tipo: el Admin edita nuestro master (p. ej. Lucky V06 desde CapCut/editor propio), lo entrega
por link de Drive y pide comparar, aprender de sus decisiones y arreglar algo acotado
("solo los subtítulos del diálogo de Lucky").

## Reglas duras
- **La edición del Admin es la base.** Nunca re-renderizar nuestra versión por encima; se trabaja
  sobre SU archivo. Los límites de alcance que da son contractuales: pies, logos, cartelas,
  música, montaje y duración NO se tocan salvo orden explícita.
- Inspeccionar streams con ffprobe antes de decidir el método: H.264/AAC sin pista de subtítulos, junto a texto visible en frames, indica texto quemado. No asumir que todos los MP4 carecen de pista editable.
- Prohibido blur para quitar texto quemado: mármol con reflejos, telas en movimiento y grades
  B&W de alto contraste lo delatan de inmediato. La vía correcta es **placa limpia** del clip
  original con máscara solo sobre la caja del subtítulo.

## Pipeline de diagnóstico y diseño de reparación
La descarga, ASR, comparación temporal y revisión visual tienen evidencia de ejecución; la reparación debe probarse aparte. No presentar una placa propuesta como restauración ya renderizada o aprobada.

1. **Ingesta:** descargar de Drive por la integración autorizada (google-workspace-ops / credencial materializada desde ActivePieces), sin gdown ni OAuth local revocado. Verificar tamaño y checksum contra metadata. Usar `ffprobe` de resolución/fps/duración
   (típicamente 1440x2560@30 del editor vs nuestro 1080x1920) y extraer audio
   `ffmpeg -vn -ac 1 -ar 16000` a wav en scratch.
2. **ASR word-level:** faster-whisper `small` int8 (mejor que base en es), `language='es',
   word_timestamps=True, condition_on_previous_text=False, beam_size=8`. Modelos ya cacheados en
   `/opt/hermes-agent-data/home/.cache/huggingface/hub/models--Systran--faster-whisper-*` (correr
   con la venv del repo de campañas, no el python del contenedor). Guardar JSON de palabras →
   da el timing real del diálogo para recolocar cápsulas.
3. **Mapa de timeline usuario→master:** decodificar TODOS los frames a gris 64x114 (centro-crop
   para ignorar franjas de subtítulos/logos), L2-normalizar y `scores = U @ O.T` contra los frames
   del master original. Una correlación alta y una trayectoria temporal coherente sugieren reutilización del material; verificarlo con frames. Una correlación baja no prueba material nuevo: también puede deberse a zoom, inversión, B&W, máscaras o transiciones. El mapa orienta la búsqueda, pero no certifica alineación subpíxel ni sustituye la inspección visual.
4. **Contact sheets para revisión visual:** frames a 240px de ancho en grillas 6x6 con etiqueta
   `f#### t.ss` y repartir rangos de hojas a subagents paralelos (uno por bloque de frames) para
   detectar cortes, entradas/salidas de texto y efectos. Declarar siempre cuántas hojas se revisaron.
5. **Forense de subtítulos:** crop full-res de la banda de cápsulas en 6-8 timestamps y
   `vision_analyze` pidiendo texto EXACTO (tildes, puntuación, «del día» vs «diaria») + estilo +
   posición. Cruzar contra el ASR: subtítulo quemado que no coincide con la voz actual = cue
   huérfano de la versión anterior (causa raíz típica del descuadre).
6. **Plan de reparación:** regenerar las cápsulas con el sistema de overlays del repo
   (`overlays_*.py`, PNG + `enable='between(t,..)'`) alineadas al ASR word-level del nuevo audio,
   y componer sobre la edición del Admin con máscaras que solo cubren la caja del subtítulo.
   Medir por plano la zona del footer/legal a resolución original; no reutilizar coordenadas de otra exportación sin verificar. En segmentos con grade del Admin (B&W), usar placa post-grade o replicar el LUT; sync frame-accurate y mismo fps. Si no se recupera fondo limpio con calidad suficiente, declarar el límite y solicitar export sin subtítulos o proyecto; no prometer eliminación invisible.

## Restauración con placas: controles de ejecución
- Reutilizar el renderer de la versión original con lista de captions vacía y rutas de salida/overlays nuevas; no sobrescribir el master ni sus PNG. Alinear la placa contra el usuario usando hitos visibles fuera del texto, no solo el timestamp del mejor correlato.
- Igualar color de la placa al video editado antes de componer. En fondos difíciles, una corrección armónica de borde (Poisson/Laplace) integra el detalle animado sin desenfocar la imagen; mantener la máscara estrictamente limitada a la caja vieja y proteger los píxeles del footer.
- Ajustar exposición POR FRAME cuando hay un fundido. Una transformación de color estimada en un frame luminoso crea pies iluminados y recortes negros al final del fade. Estimar ganancia/sesgo desde zonas descubiertas del mismo frame, excluyendo la caja y efectos atípicos, y comprobar los últimos frames individualmente.
- Evaluar supuestos defectos mediante comparativas del MISMO frame antes/después: un footer con aberración cromática preexistente no es una regresión de la reparación y no autoriza rediseñar efectos del usuario.
- Verificar tiempos de cada fragmento contra las palabras que contiene: no adelantar «de la Suerte» mientras aún se pronuncia «encantada». Añadir pruebas deterministas de esos límites.
- Auditar todos los frames antes de codificar: fuera de las máscaras y de las cápsulas nuevas los píxeles deben permanecer idénticos. Después de H.264, no afirmar identidad byte a byte del video; conservar número de cuadros, geometría y tiempos y medir por separado el audio copiado.
- Copiar la pista AAC sin remezclar y comparar el hash del bitstream demultiplexado de fuente y entrega. Esto prueba preservación de voz/música/SFX de forma más fuerte que un nuevo ASR por sí solo.
- Ejecutar renders que excedan el timeout de herramienta como procesos rastreados con notificación y límites de CPU locales; conservar y apartar salidas incompletas, nunca entregar un MP4 sin cierre/validación. Usar límites de BLAS por proceso cuando haya oversubscription, no modificar la configuración global.
- Distinguir un SRT lateral editable de los captions quemados en el MP4: entregar el SRT y el master, y no prometer que el texto del master pasa a ser una capa editable.

## Criterios de edición que deben pasar a la próxima producción
- Priorizar un gancho que comunique la invitación y personalidad desde el arranque; no gastar los primeros segundos solo presentando ambiente o una frase inconexa.
- Hacer reconocible la marca desde el comienzo, con logos legibles que no tapen la acción; la mascota no sustituye la atribución de marca.
- Construir un remate accionable: evento, fecha/hora y siguiente paso o sede, en lugar de depender solo de «ven» genérico. No inventar sedes ni modificar una cartela aprobada dentro de una reparación de subtítulos.
- Relacionar cambios de plano, gestos, transiciones y acentos de sonido con momentos narrativos. No copiar automáticamente flashes/negativos de una referencia ni declarar que más efectos siempre es mejor; revisar legibilidad y fotosensibilidad.
- Conservar la nueva duración autorizada por la edición del usuario: no recortarla al límite de un brief antiguo por inercia.
- Separar montaje limpio, diálogos, subtítulos editables y rótulos informativos. Entregar SRT/ASS además del master para evitar obligar al usuario a editar captions quemados.
- Después de mover planos o reemplazar voz, regenerar tiempos de subtítulos contra el audio FINAL. Eliminar cues huérfanos, dividir frases por unidades de lectura y revisar cada entrada/salida; no conservar textos por pertenecer al plano antiguo.
- Si el audio final usa una expresión distinta del guion previo, reportar la diferencia. En un encargo limitado a subtítulos, transcribir lo que se oye; no cambiar la voz ni reemplazar palabras silenciosamente.

## Gotchas de entorno
- No hacer `glob('/opt/**')` en python para buscar modelos de whisper: scan del disco entero y
  timeout. Buscar solo en los paths de cache conocidos.
- Los subtítulos parten frases entre cues («Cada noche que vienes,» + «te llevas tu boleta del
  día»): al recolocar, mantener la continuidad de minúscula/coma entre cues consecutivos.
- Los contact sheets del editor pueden salir con banda negra sobrante: recortar la grilla al alto
  real de los thumbs antes de mandarlas a visión.
