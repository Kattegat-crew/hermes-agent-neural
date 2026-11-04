# Contrato `campaign.piezas` + `campaign.version` (desde 2026-08-26)

## Por qué existe

El plan de pipeline (§4 del PLAN-PIPELINE-AUTOMATIZACION-CAMPANAS.md) exige
"piezas + versión" en el contrato único; el template original solo traía
marca/colores/sedes/legal. Desde 26/08/2026 el template y el demo incluyen
ambos campos, y el generador los consume.

## Estructura

```yaml
campaign:
  slug: "demo-campana"
  version: "v0-draft"        # Review Bot registra aprobación por versión
  ...
  piezas:
    - id: "reel-01"
      tipo: reel             # reel | carrusel | post | story | banner_tv | flyer
      formato: "9:16"
      plataforma: instagram  # instagram | facebook | tiktok | todas
      tema: "La ruleta que cambia tu noche"
      hook: "¿Sabías que girar la ruleta puede pagarte el bingo?"   # lo escribe Content Bot
      angulo: "Promoción + experiencia real"
      cta: "Descarga la app y gira →"
      sede: "Sede Principal"
      fecha_publicacion: "2026-09-04"
      estado: draft          # draft | listo | aprobada
```

Si no hay piezas declaradas, usar `piezas: []` — el generador cae a temas
genéricos (videos_per_month) y el QA emite warning de contrato vacío.

## Cómo la consume el generador (`generate_docs.py`)

| Doc | Comportamiento |
|-----|----------------|
| GUIONES-REELS | Toma los reels declarados (tipo reel/reels/video) y usa `hook` + `cta` reales en la narración; fallback a temas genéricos si no hay piezas |
| BRIEF-PIEZAS | Tabla "Piezas Declaradas (Contrato)": ID, tipo, formato, plataforma, tema, hook/ángulo, CTA, fecha, estado |
| CALENDARIO-PUBLICACION | Piezas con `fecha_publicacion` entran como filas fijas a la matriz |
| QA-INTEGRIDAD (build_campaign.py) | JSON expone `campaign_version` + `piezas_count`; warnings si version vacía, piezas vacías, piezas sin hook/ángulo o sin CTA |

## Flujo de los bots (quién toca qué)

- **Content Bot (Bragi)**: escribe `hook`/`angulo`/`cta` en cada pieza del campaign.yaml.
- **Visual Bot (Sindri)**: produce desde BRIEF-PIEZAS (tabla Piezas Declaradas).
- **Review Bot**: aprueba por pieza, mueve `estado` → `aprobada`, registra la `versión`.
- **Social/Ads**: solo tocan piezas con `estado: aprobada`.

## Smoke test de referencia (demostrado 26/08/2026)

```bash
cd /root/hermes-agent-legacy-docker/data/profiles/roshi/workspace/campaigns
python3 template/build_campaign.py demo/campaign.yaml --output /tmp/smoke
# → 5/5 documentos generados y verificados | Estado: OK | Issues: 0
```

Verificar contenido real (no solo conteo de archivos) con python-docx:

```python
from docx import Document
for fname in ["GUIONES-REELS.docx", "BRIEF-PIEZAS.docx", "CALENDARIO-PUBLICACION.docx"]:
    doc = Document(fname)
    text = "\n".join(p.text for p in doc.paragraphs)
    tables = "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    haystack = text + tables
    assert "ruleta puede pagarte el bingo" in haystack  # hook del demo
    assert "reel-01" in haystack                        # id de la pieza
    print(fname, "OK")
```

## Pitfall: docstring vs argparse en `build_campaign.py`

El docstring prometía `--report`, pero argparse lo rechazaba
(`unrecognized arguments: --report`, exit 2). El flag ahora se acepta como
no-op por compatibilidad. Regla: si un flag aparece en el docstring, el
parser DEBE aceptarlo — o quitar la mención del docstring.