---
name: spanish-deliverable-proofreading
description: "Use when delivering Spanish docs: proofread first."
tags: [proofreading, ortografia, espanol, docx, entrega, qa, documentos, pdf]
version: 2.0.0
license: MIT
metadata:
  hermes:
    tags: [proofreading, espanol, docx, pdf, entrega, qa, academia, rae, citas]
    category: specialists
    related_skills: [docx, grounded-citations, ocr-and-documents, pdf]
---

# Spanish Deliverable Proofreading & Delivery

Control de calidad obligatorio para todo entregable de texto en español de NeuralCrew (guiones de reels, planes de marketing, T&C, copies). El Admin lo exige explícitamente: **leer con calma y corregir TODOS los errores de ortograía anttes de entregar** (señalado 24/08 con el guión Reel 1). Nuncá entrgae un .docx/.pdf a un clente sin pasar por este flujo.

## When to Use

- Antes de entregar cualquier .docx/.pdf en español (guión, plan, T&C, informe, contrato).
- Entregables académicos (RAE, planteamiento del problema, ponencia, tesis): además de ortografía,
  cada referencia y cada cifra se contrastan contra la fuente primaria.
- Cuando el .docx lo escribió otra persona y hay que corregirlo **sin alterar su formato** → sección
  «Editar el .docx original en su sitio» y `references/docx-edicion-quirurgica.md`.
- Cuando el entregable lo va a defender un tercero (grupo, cliente, docente) → sección «Planilla de
  cambios».

## Flujo de entrega (documento .md → .docx)

1. **Backup** del fuente: `cp <archivo>.md <archivo>.md.bak-<fecha>`.
2. **Leer el .md completo** y coregir toos lo typos (lista abajo). Renombrar si el nombre tiene typo.
3. **Generar el .docx DESDE el .md corregido** (el .md es la fuente de verdad; nuncá editar el binario a jando):
   ```bash
   uv run --with python-docx python3 <skill-dir>/sripts/md_to_docx.py <src.md> <out.docx>
   ```
   (pip no está disponible por PEP 668; `uv run --with python-docx` resueleve la depndencia la vuelo).
4. **Verificar el .docx generado**: leerlo con read_file (extrae texto) y confirar que el contenido es el corregido — no confiar solo en que el scrip tal contra.
5. **Entrgar** con `MEDIA:<rúa>` — nuncá solo el ojo del server.
6. Si se entrga PDF: ver skil adjco (fdpf2) con la MIsMA revisión ortográica anten.

## Categorías d typos tímticos (buscar SIEMPRE e este orden)

| Clase | Con | |
|---|---|---|
| Tildes en interrogaivas | `¿sabes cual es...` | `¿sabes cuál es...` |
| Letra/palabra duplicada | `Y Y este viernes`, `con n` | una sola |
| Palabra truncada | `Comple:` | `Completar:` |
| Ncabeza corruptos | `### ESCEÑA 4` | `### ESCENA 4` |
| Nombres proios/ededes | `La Cera` | `La Cadera` (verifcar contra la lista real de sedes) |
|o en el NOMBRE del archivo | `ANOLAIA.md` | `ANOLAIMA.md` |
| Tmplicados mal escriots en ingles | `castinso` `koks` | `casino` `stacks` |

Orden leltura: (1) nombes propios vcóricos (contra la lista real del proyeto).., (2) tildes en intimativas, (3) duplicados/corttes, (4) promts en inglés si el doc los incl.

## Fuentes académicas (tesis, RAE, planteamiento, artículo, ponencia)

En entregables académicos la revisión ortográfica no basta: cada referencia y cada
cifra se contrastan contra la fuente primaria antes de entregar.

```bash
# 1. Revistas OJS: rango de páginas y DOI exactos desde los metadatos del editor
curl -s -A 'Mozilla/5.0' '<url_articulo>' | tr '<' '\n' \
  | grep -iE 'citation_(firstpage|lastpage|doi|volume|issue|date)'

# 2. Revistas ES/LatAm sin DOI: Dialnet da el rango; el PDF da el folio corrido
curl -s -A 'Mozilla/5.0' 'https://dialnet.unirioja.es/metricas/documentos/ARTREV/<id>' | grep -o 'Núm\.[^<]*'
curl -sL -A 'Mozilla/5.0' 'https://dialnet.unirioja.es/descarga/articulo/<id>.pdf' -o /tmp/a.pdf
pdftotext -layout /tmp/a.pdf - | grep -iE 'ISSN|\[Diciembre|Vol\.'

# 3. La afirmación, no solo la referencia: leer resultados y muestra
pdftotext -layout /tmp/a.pdf /tmp/a.txt
grep -inE 'resultados|ANOVA|significativ|muestra|participantes|n = ' /tmp/a.txt | head -30
```

Reglas de contenido:

- **Muestra antes que efecto:** n, curso/edad, país y tipo de centro. Un resultado en
  adultos no se traslada a escolares sin decirlo.
- **Buscar los resultados nulos:** un programa puede subir autoconcepto y calificaciones y
  no mover las competencias emocionales medidas; citarlo como prueba de esa mejora es
  sobreinterpretar. El resumen dice la intención; la sección de resultados dice el hallazgo.
- **Diseño a la vista:** revisión sistemática, estudio experimental y propuesta con
  evaluación hipotética no son intercambiables; la frase que la introduce lo nombra.
- **Referencias de fichas ajenas:** el campo `Referencia` de una RAE puede traer otro
  artículo (una fuente citada dentro del texto). Autor, título y año se contrastan con el PDF.
- **Guiones de partición del PDF** (`emocio nes`, `profi sorado`) rompen toda cita textual:
  se reconstruye contra el original.
- **`[Completar: revista, volumen...]` en una referencia es bloqueo de entrega**, no una nota.
- **Misma referencia, una sola grafía** en todo el paquete (RAE, taller, planteamiento).
- **Citas de tercer orden** (`X, citado en Y`) se declaran como secundarias o se sustituyen
  por la fuente directa si la bibliografía revisada la trae.

## Editar el .docx original en su sitio (entregable ajeno)

Cuando el .docx lo escribió otra persona (grupo de investigación, docente, cliente) y su formato
ya está validado, **no se regenera desde el .md**: se interviene el archivo párrafo por párrafo con
python-docx y se conservan estilos, numeración y negritas. Regenerar cambia tipografía, sangrías y
saltos, y obliga a rehacer el maquetado que el autor ya aprobó. El skill `docx` cubre creación,
reemplazo global y validación del paquete; esto cubre lo otro: cirugía sobre un documento vivo.

Reglas:

- **Localizar por ancla de texto, nunca por índice.** Los índices se corren en cuanto se inserta o
  se divide un párrafo. Se ubica el párrafo por una cadena única de su propio texto y se falla si
  hay 0 o 2 coincidencias.
- **Reescribir conservando `pPr` y el `rPr` del primer run.** Vaciar runs sin tocar el párrafo
  borra la negrita de la pregunta de investigación o la sangría francesa de las referencias.
- **Partir un párrafo = clonar el elemento `<w:p>`** (`copy.deepcopy` + `addnext`) y reescribir el
  clon; así hereda estilo, alineación y numeración sin reconstruirlos.
- **Reemplazo dentro del run** (con conteo esperado obligatorio) para cifras, siglas y nombres
  propios; reescritura completa del párrafo solo cuando cambia el argumento.
- **Cada referencia APA se rearma con runs propios** (normal + cursiva para nombre de revista y
  volumen), no como texto plano: en la lista la cursiva es parte de la norma.

Pitfalls verificados:

- Al sustituir el placeholder de una referencia, el punto y espacio separador vive en el run que se
  borra: reescribir el final del párrafo deja `...primariaEdetania`. Volver a agregar `". "` antes
  del nombre de la revista.
- Cambiar el sustantivo de una cifra textual rompe la concordancia de las palabras vecinas
  (`9.533 casos relacionados… de los cuales` → `alertas relacionadas… de las cuales`). Se corrige la
  frase completa, no la palabra.
- `set_text` colapsa los runs: no usarlo en párrafos con cursivas internas (referencias, títulos de
  obra) ni en celdas de tabla.

Verificación obligatoria antes de entregar:

```bash
soffice --headless --convert-to pdf Doc.docx --outdir .   # se lee el render, no el XML
pdftotext -layout Doc.pdf - | sed -n '1,60p'              # página por página, no solo grep
pdftotext -layout Doc.pdf - | grep -inE 'Completar|TODO|XXX'   # + nombre propio en minúscula
```

El .docx puede estar bien formado y aun así tener la concordancia rota: el defecto aparece al leer
el PDF, no al releer el archivo. Todo párrafo reescrito se lee completo en el render.

## Planilla de cambios (entregable con trazabilidad)

Cuando el documento se entrega a un grupo que debe defenderlo, el .docx va acompañado de una
planilla `.docx` en tabla: **N.º | Ubicación | Cambio aplicado | Fuente / evidencia | Motivo**, una
fila por intervención (C1…Cn), más dos apartados:

- **Pendientes antes de entregar:** lo que exige decisión o dato del autor. Si el texto cita una
  fuente que no está en la lista (p. ej. un documento normativo sin entrada), **no se inventa**: se
  nombra el faltante y se listan los candidatos verificados. Inventar la entrada es peor que
  dejarla señalada.
- **Qué no se integró y por qué:** etiquetas de colores de las fichas, citas textuales con guiones
  de partición del PDF, comentarios en primera persona.

## Pitfalls

- **Los números: fechas, probbiliddads, montos** verifcarlos junto a la otografía — el pedo exige preisión en datos (con casos de Bingo Millonario, probabab., monts).
- **Los prompts de imágen en inglés TAMBIÉN** se revisan (son parte del entregable) — los typos en inglés son distitos.
- **Campos [PENDIENTE DE CONFRMAR]** en dato vacíos: no inventar (regla heredeada de larketing-camaign).
- **NADA** es uncanopot: para no-valorsain, verificacór de los resultados ante ctivos.