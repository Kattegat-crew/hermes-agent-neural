# Edición quirúrgica de un DOCX académico y verificación de citas

Aplica cuando el usuario manda un `.docx` que **ya existe y ya fue aprobado** (planteamiento del
problema, RAE, informe, marco teórico) y pide corregirlo o integrarle insumos — no crear otro
documento. El objetivo es doble: que el formato original quede intacto y que cada afirmación
pueda defenderse con página.

## Reglas de oro

1. **Partir del archivo original, no de una copia reescrita.** Regenerar desde cero pierde
   estilos, sangrías y numeración, y el docente lo nota. Se copia el original y se intervienen
   párrafos puntuales.
2. **Nunca inventar una referencia.** Si el texto cita `(MEN, 2023)` y esa entrada no existe en
   la lista, la salida no es inventar la entrada: es atribuir la afirmación a quien realmente la
   sostiene en el insumo revisado ("Barreto Arrieta y Cardona Hoyos (2024) señalan que el
   Ministerio…") y anotar el pendiente en la planilla.
3. **El bloque RESUMEN de un RAE es textual con página; los COMENTARIOS son lectura del grupo.**
   Una idea que aparece en "COMENTARIOS" no se cita como si el artículo la dijera. Confundirlos
   produce citas falsas que el revisor desmonta en dos minutos.
4. **Distinguir lo que la fuente mide de lo que la fuente espera.** "Se espera que los resultados
   arrojen que el 95 %…" no es un hallazgo. Si un ANOVA no dio diferencias significativas, el
   documento no puede afirmar que el programa mejoró esa dimensión.
5. **Cita secundaria siempre con fórmula:** `Evans y Liu (2019, citados en Gutiérrez et al.,
   2021, p. 12)`. Nunca tres niveles encadenados ni la fuente interna presentada como propia.
6. **Datos de laboratorio no se trasladan a la escuela.** Un hallazgo de EEG o de ansiedad
   medido en condiciones controladas se cita como base fisiológica y se advierte en el párrafo
   de límites.

## Helpers de python-docx (`scripts/docx_surgical.py`)

```python
set_text(p, texto)      # reemplaza el texto conservando pPr y el rPr del primer run
clone_after(p, texto)   # clona el párrafo entero (estilo, alineación, sangría) y lo inserta después
rep(p, viejo, nuevo)    # reemplazo dentro de un run; falla ruidosamente si no hay match
```

- `set_text` conserva el formato porque deja el primer run y elimina los demás. **No** usarlo en
  párrafos con formato heterogéneo (típico en referencias): ahí se reconstruyen los runs.
- `clone_after` es la forma correcta de **partir un párrafo en dos** (separar justificación de
  delimitación conceptual, separar dos líneas de análisis): copia el elemento XML, así hereda
  estilo, alineación y sangría sin replicarlos a mano.
- `rep` falla con `SystemExit` si no encuentra el texto: sirve de prueba de que el reemplazo se
  aplicó, en lugar de dejar cambios silenciosos.

Esqueleto de un script de integración:

```python
import copy, docx
from docx.text.paragraph import Paragraph

doc = docx.Document(SRC)
P = doc.paragraphs                      # capturar ANTES de insertar nada
set_text(P[7], TEXTO_A)
clone_after(P[7], TEXTO_B)              # el párrafo nuevo queda entre 7 y 8
rep(P[23], "Solo el trabajo de", "De los seis textos revisados, solo el trabajo de")
doc.save(OUT)
```

## Pitfalls que ya costaron una regeneración

- **Borrar `runs[2:]` en un párrafo de referencia se lleva el separador.** En APA el título del
  artículo va en cursiva y el punto que lo separa de la revista vive en el run siguiente; al
  borrar desde el índice 2 desaparece ese `". "` y queda `…primariaEdetania. Estudios…`.
  Reconstruir explícitamente: run normal `". "` + run itálico con la revista + run normal con
  `volumen(número), páginas. DOI`.
- **Sustituir una palabra clave rompe concordancia y anáfora.** Cambiar `9.533 casos` por
  `9.533 alertas` deja `relacionados… de los cuales`. Reemplazar la frase completa
  (`casos relacionados… de los cuales` → `alertas relacionadas… de las cuales`).
- **`cell.text = ...` borra el formato** de la celda; escribir en el primer párrafo con `add_run`.
- **Tablas en horizontal que se cortan entre páginas:** añadir `w:cantSplit` a cada fila y
  `w:tblHeader` a la fila de encabezado.
- **Los índices de párrafo se mueven** al insertar; operar sobre objetos `Paragraph`, no sobre
  índices recalculados.
- **La extracción del zip trae guiones de partición** (`emocio nes`, `profe sorado`): limpiar las
  citas antes de pegarlas o quedan en el entregable.

## Segunda ronda de insumos: regenerar, no parchear

Cuando llegan más fuentes después de entregar («faltaban 4 RAE más»), **no** se edita el DOCX ya
entregado: se extiende el script para que vuelva a leer el original y escriba `_v3`. Así cada
versión es reproducible, el diff es auditable y las correcciones anteriores no se pierden ni se
duplican. Un script por entregable (`build_v3.py`), nunca ediciones a mano sobre el output.

## Chequeos sobre la fuente (no solo sobre el texto)

- **Contar artículos, no archivos.** Dos RAE pueden describir el mismo artículo (uno ampliado); el
  documento no puede decir «seis textos» si en realidad son cinco artículos. Verificar título,
  autores y año antes de numerar.
- **Restituir la expresión literal al citar.** Un calificativo que parece de relleno puede ser la
  bisagra del argumento: `el maestro de música como agente regulador` (p. 13) no es `el maestro`.
  Si el proyecto indaga justamente quién enseña, borrar «de música» elimina el hallazgo.
- **Superlativos y frecuencias propias no se citan como hallazgos.** «Los aportes surgen con mayor
  frecuencia en ambientes no formales» suele estar en los COMENTARIOS; el artículo dirá otra cosa
  («los hallazgos sobre desempeño intrapersonal se asocian con…», p. 7). Citar la formulación
  exacta de la fuente, no la interpretación del RAE.
- **Comprobar que las conclusiones de la fuente se sostengan en sus propios resultados.** Si la
  p. 77 afirma que «docentes y directivos coinciden en que la música disminuye las conductas
  disruptivas» y en las pp. 36–49 no hay un solo registro donde hablen de música, eso se escribe
  con páginas: es el mejor argumento para justificar ir al campo.
- **Conservar la página al reformular.** Cada frase que entra debe llevar su `p.`/`pp.` del insumo;
  al añadir una idea nueva a un párrafo ya citado, repetir la página (no heredarla del párrafo).

## Verificación obligatoria antes de entregar

1. **Render real:** `soffice --headless --convert-to pdf X.docx --outdir .` y luego
   `pdftotext -layout X.pdf -`; revisar a ojo el tramo intervenido (sangrías, saltos, que un
   `Heading 3` no quede huérfano al pie).
2. **Cero placeholders:** buscar `Completar`, `XXX`, `TODO`, `[` y las erratas conocidas.
3. **Citas colgantes:** cada cita del texto con entrada en la lista y cada entrada citada;
   comparar apellidos entre ambas listas. `scripts/docx_surgical.py check` lo hace en un paso.
4. **Conteo de párrafos y palabras** antes/después: confirma que las divisiones ocurrieron y que
   no se perdió contenido.
5. **Concordancia:** releer la oración completa, no solo la palabra reemplazada.

```bash
python3 scripts/docx_surgical.py check out.docx \
  --forbid "Completar,bogotá,TODO" \
  --expect "Edetania. Estudios y Propuestas Socioeducativas"
```

## Planilla de trazabilidad (entregable hermano)

Cuando el trabajo es para terceros (compañeras de grupo, docente, cliente), entregar junto al
`.docx` una planilla de cambios: es lo que convierte "lo corregí" en "esto es defendible".

- Columnas: `N.º | Ubicación | Cambio aplicado | Fuente / evidencia | Motivo`.
- Una fila por cambio, numeradas en orden de aparición en el documento (no de ejecución).
- La columna *Fuente* lleva página o ruta concreta: `PDF Edetania, p. 213`, `RAE 1, p. 7`.
- Segunda tabla de **verificación insumo por insumo** cuando se integraron varios documentos:
  qué se confirmó, qué se corrigió, páginas, cambio asociado.
- Cierre con **pendientes** (requieren decisión del usuario) y **qué no se integró y por qué**
  (etiquetas de colores, comentarios en primera persona, citas de tercer orden).
- Formato: A4 horizontal, `Table Grid`, encabezado con relleno, 8,5–9 pt en celdas.
