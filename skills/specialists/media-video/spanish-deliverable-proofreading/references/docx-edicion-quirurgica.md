# Edición quirúrgica de un .docx existente

Código probado sobre un planteamiento académico de 42 párrafos (TNR 12, encabezados con estilo,
referencias con cursivas internas) que se intervino en 15 puntos sin perder un solo atributo de
formato. Se reconstruyó el documento desde el original y se renderizó a PDF para verificarlo.

## Helpers mínimos

```python
import copy, docx
from docx.text.paragraph import Paragraph

doc = docx.Document(SRC)
P = doc.paragraphs           # capturar ANTES de insertar: los objetos siguen válidos

def set_text(p, text):
    """Reemplaza el texto conservando pPr y el rPr del primer run."""
    if not p.runs:
        p.add_run(text); return
    first = p.runs[0]
    for r in p.runs[1:]:
        r._element.getparent().remove(r._element)
    first.text = text

def clone_after(p, text):
    """Clona el párrafo (mismo estilo/formato) y lo inserta justo después."""
    el = copy.deepcopy(p._p)
    p._p.addnext(el)
    q = Paragraph(el, p._parent)
    set_text(q, text)
    return q

def rep(p, old, new):
    """Reemplazo dentro de un run; falla si no hay coincidencia (no cruza runs)."""
    hit = 0
    for r in p.runs:
        if old in r.text:
            r.text = r.text.replace(old, new); hit += 1
    if not hit:
        raise SystemExit(f"NO MATCH: {old!r} en {p.text[:60]!r}")
```

## Casos resueltos con estas tres funciones

| Necesidad | Operación | Nota |
|---|---|---|
| Corregir una palabra o cifra | `rep` | Conteo esperado; si hay 0 coincidencias, el texto está partido entre runs |
| Reescribir el argumento de un párrafo | `set_text` | Solo si el párrafo es de formato uniforme |
| Dividir un párrafo demasiado largo | `set_text` (parte A) + `clone_after` (parte B) | El clon hereda pPr; no reconstruir estilos a mano |
| Rehacer una referencia APA | `rep` para el placeholder + runs nuevos con cursiva | Ver pitfall del separador |
| Añadir siglas APA 7 (`[OCDE]`, `[SED]`) | `rep("Económicos. (2024).", "Económicos [OCDE]. (2024).")` | La sigla va en la entrada, no solo en el texto |

## Reconstruir el final de una referencia con cursiva

```python
p = P[38]                                   # párrafo de la referencia
for r in p.runs[2:]:                        # descartar el placeholder
    r._element.getparent().remove(r._element)
p.add_run(". ")                             # ¡el separador vivía en el run borrado!
it = p.add_run("Edetania. Estudios y Propuestas Socioeducativas"); it.italic = True
p.add_run(", (54), 199–222. https://revistas.ucv.es/edetania/index.php/Edetania/article/view/398")
```

Sin el `". "` el resultado leído es `...educación primariaEdetania. Estudios...`: el defecto no
rompe el archivo, rompe la cita.

## Verificación en dos pasadas

```bash
# 1) sondas sobre el texto extraído del .docx (barato, detecta lo obvio)
python3 -c "import docx,re; d=docx.Document('out.docx'); t='\n'.join(p.text for p in d.paragraphs);\
print([s for s in ['Completar','XXX','TODO'] if s in t], len(re.findall(r'\w+',t)))"

# 2) el render manda: leer páginas, no solo grep
soffice --headless --convert-to pdf out.docx --outdir . && pdftotext -layout out.pdf - | sed -n '1,260p'
```

La pasada 1 confirma que no quedaron placeholders y que el conteo de párrafos creció solo donde se
insertó. La pasada 2 es la única que revela concordancia rota, frases pegadas y párrafos partidos
mal.

## Numeración y desplazamiento de índices

Al insertar o dividir párrafos, los índices posteriores se corren. Estrategias, en orden de
preferencia:

1. Capturar `P = doc.paragraphs` una vez y operar sobre esos objetos (válidos aunque cambie el orden).
2. En un plan reproducible, ubicar por ancla de texto única y fallar si hay 0 o 2 coincidencias.
3. Nunca encadenar dos operaciones por índice numérico si la primera inserta.

## Planilla de cambios: forma mínima

Tabla de 5 columnas (`N.º`, `Ubicación`, `Cambio aplicado`, `Fuente / evidencia`, `Motivo`) con una
fila por intervención, más `Pendientes antes de entregar` y `Qué no se integró y por qué`. La fila
debe permitir que un tercero abra el PDF, vaya a la página y compruebe la cita: por eso la columna
de fuente lleva página o sección, no solo el autor.
