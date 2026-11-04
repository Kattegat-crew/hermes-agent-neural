# Caso: calendario de campaña NeuralCrew — JSONL(Git) ↔ XLSX(Drive)

**Fecha del diagnóstico:** 11-sep-2026 · **Reportado por:** Jonathan ("en la tabla las piezas publicadas ayer aparecen como aprobadas, no publicadas")

## Arquitectura

- Store canónico: `planning/calendario-sep2026/calendario.jsonl` en `marketing-campaign-generator` (Git).
- Espejo humano: `Calendario_BingoSep2026_Golden_Lucky.xlsx` en 2 copias de Drive (golden `1K1EFCAQiR8Z-hch_0Hr1IY4Y9Fjd8n6e`, lucky `1O1KX15rSq4CY3xuPlox5y2FosfTRC_Gn`).
- `sync_from_drive.py` (espejo → store) corre al inicio de cada tick del cron horario; `build_xlsx.py` regenera el espejo; `cron_publish_due.py` publica y marca `publicado`.

## Síntoma

Filas ya publicadas con `estado: aprobado` pero conservando `publicado_en` y `media_ids`.

## Evidencia (git log del JSONL)

```
COMMIT dbc690e 2026-09-10 reel(calendario): publicación cron 2026-09-10 golden-sep10-story-2, lucky-sep10-story-2
-  ... "estado": "aprobado" ...
+  ... "estado": "publicado" ... "publicado_en": "2026-09-10T12:37:35-05:00", "media_ids": {...}
COMMIT eac054a 2026-09-10 chore(calendario): sync edición admin XLSX→JSONL (cron publicar)
-  ... "estado": "publicado" ...
+  ... "estado": "aprobado" ...   (publicado_en y media_ids intactos)
```

## Defectos concretos

1. `cron_publish_due.py:118` regenera el XLSX local tras publicar, **no lo sube a Drive**. El único `files().update` del pipeline está en `approve_ids.py:70-77` (flujo de aprobación).
2. `sync_from_drive.py:109-119` aplica cualquier diferencia de la columna `Estado` sin protección de estado terminal; y `cron_publish_due.py:52` lo ejecuta ANTES de publicar → el master desactualizado gana en cada tick.
3. `cron_publish_due.py:79-83` (auto-sanado: `media_ids` presente ⇒ `publicado`) sólo se alcanza dentro de la ventana `slot ±2h`; fuera de ella la fila no se repara nunca más.

## Filas afectadas al 11-sep-2026

`golden-sep09-story-1`, `lucky-sep09-story-1`, `golden-sep10-post-pacho`, `lucky-sep10-post-chiqui2`, `golden-sep10-story-2`, `lucky-sep10-story-2`.

Sobrevivieron `golden-sep08-reel-pacho` y `lucky-sep08-reel-chiquinquira` porque su celda en Drive ya decía `publicado` (subida manual en `b16afee`) — confirma que el sync empuja el valor del espejo sin filtrar.

## Impacto colateral

`content-intel/campaign_report.py:122` filtra `r['estado'] == 'publicado'` → el informe de cierre de septiembre habría contado 2 piezas publicadas en vez de 10.

## Reportar mientras siga abierto

Contar publicadas por `publicado_en`/`media_ids` (y `content-intel/data/posts.jsonl` como registro autoritativo), y decirlo explícitamente si el humano está mirando la tabla.

## Reparación propuesta (pendiente de OK del Admin: toca código y Drive)

1. Una vez: filas con `publicado_en` + `media_ids` → `publicado`, regenerar XLSX, subir a AMBAS copias.
2. `cron_publish_due.py`: subir el XLSX a los dos Drive tras publicar (simetría con `approve_ids.py`).
3. `sync_from_drive.py`: transición monotónica, nunca `publicado` → `aprobado`; registrar divergencia.
4. `campaign_report.py`: contar por `publicado_en`/`media_ids` (defensa en profundidad).
