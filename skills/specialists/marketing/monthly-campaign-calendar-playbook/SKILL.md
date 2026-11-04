---
name: monthly-campaign-calendar-playbook
description: "Use when setting the monthly campaign calendar."
tags: [calendario, campanas, cron, publicacion, aprobacion, drive, marketing]
version: 1.0.0
author: Ragnar
---

# Playbook — Calendario Mensual de Campañas (regla NeuralCrew desde sep-2026)

Este es el estándar del pipeline de marketing automático para cada mes y cada cliente (Golden Game, Lucky Brothers, futuros). El caso vivo: `planning/calendario-sep2026/` en el repo `marketing-campaign-generator` (ruta host: `/root/marketing-campaign-generator`, contenedor: `/host/root/marketing-campaign-generator`).

## Contrato de arquitectura (no negociar)

1. **JSONL versionado en Git = fuente de verdad.** Una fila por pieza: `id · brand · campaign · type · slot · channels · copy · hashtags_ig/fb · estado · asset_drive_id · cover/slides · nota · media_ids · metrics`.
2. **XLSX de revisión en Drive = superficie humana.** El humano edita solo columnas: Estado, Copy, Hashtags, Portada, Nota. `sync_from_drive.py` hace diff por ID en cada tick; lo escrito gana; celda vacía/— no toca. El XLSX se REGENERA y re-sube al mismo archivo tras cada sync/publicación (los enlaces no cambian).
3. **Máquina de estados:** `a_producir → listo_para_aprobacion → aprobado → publicado`. El cron de publicación JAMÁS toca fila ≠ `aprobado`. Doble gate: en `cron_publish_due.py` (L filtro) y dentro de `publish()` (defensa en profundidad, `--force` solo humano).
4. **Aprobación por chat** ("Dale <ID>") o por celda `Aprobado` en XLSX. Regla dura inmutable: nada externo sin aprobación explícita.
5. **Cadencia fija por plantilla semanal** (definida con el Admin al arranque): ej sep-2026 = reel lunes 11AM, story diaria 12M, post jueves 11AM, story bingo viernes 5PM, carrusel sábado 11AM.
6. **Publicación IG+FB vía Composio** con assets hosteados en PROD (`reels.neuralcrewlabs.com/assets/<mes>/`, sin SSO). IG exige URL pública; FB >100MB por file_url (upload local = 413).
7. **Métricas:** harvest diario (día+1 y día+2) a `posts.jsonl` + dashboards por marca.

## Pasos para un mes nuevo (checkout del mes anterior como plantilla)

1. `cp -r calendario-sep2026 calendario-<mes><anio>` → renommar campaign en build_calendario.
2. **Inventario Drive:** escanear la(s) carpeta(s) de campaña del mes, clasificar piezas (Reels/Posts/Stories/Carruseles), asignar a la plantilla semanal → `build_calendario.py` → JSONL.
3. Huecos → filas `a_producir` con `nota` accionable (ej "Reel 3 — sede a confirmar; generar fin de semana X").
4. `build_xlsx.py` → subir XLSX a carpetas de campaña de ambos clientes.
5. Registrar los slot del calendario con anclas del mes (bings, festivos, fechas comerciales — Amor y Amistad, Halloween, Novenas, etc.).
6. **Crons gemelos por mes** (o reconfigurar los del mes anterior — SOLO 3 activos a la vez, uno por campaña vigente):
   - `calendario-paquete-diario` 7:30 → WhatsApp Admin
   - `calendario-publicacion-horaria` cada hora → solo publica aprobadas
   - `calendario-metricas-diario` 6:00 → harvest
   - Wrappers en `data/scripts/calendario_*.sh` → scripts del MES en curso.
7. **VERIFICACIÓN OBLIGATORIA EN EL NAMESPACE DEL GATEWAY** (skill `cron-runtime-verification`): los crons corren como uid 10000 en contenedor con /opt/data = data/ del host. Prueba con `nsenter`, no con setpriv. Los checks: wrapper→exit 0 silencioso, git push, composio shim, escritura cron/output, deps py3.13.

## Por qué así (decisiones tomadas con el Admin)

- Excel/Sheets en vivo NO (indiferenciable, no consumible); XLSX en Drive SÍ (descargable, diffable).
- Hermes crons + Composio, no ActivePieces (AP = alternativa futura fuera del contenedor).
- Link en stories: IMPOSIBLE por API Meta (sin stickers); el pie de bio+URL va en reels/posts (URL al FINAL del copy, decisión sep-2026); stories limpias.
- FB stories: sin API → solo IG.

## Pitfalls críticos (aprendidos 09-sep-2026)

0. **El cron horario NO publica al instante: tick cada 60 min.** Si apruebas una pieza y su slot es hoy, el cron la publica en el PRÓXIMO tick que caiga en la ventana `slot ± 2h`. Por ejemplo, slot 12:00 → ventana 12:00–14:00; si apruebas a las 09:00, el cron la toma en el tick de las 12:22 (≈12:22 en adelante), no antes. Si el usuario pregunta "¿por qué no se ha publicado?" recién aprobada, normal: revisar `ls /opt/data/cron/output/794be6c2336b/` (el último `.md` con bytes >0 = publicó; el último `0` bytes = `NO_REPLY` = nada debía publicarse aún).

1. **El sync de Drive REVIERTE la aprobación si el XLSX de Drive no se actualiza.** `sync_from_drive.py` trata `Estado` como campo editable y corre en el cron de las 07:30. Si apruebas por chat (JSONL→`aprobado`) pero NO subes el XLSX regenerado a Drive, el master de Drive sigue en azul y el sync lo revierte. **Siempre**: aprobar → `build_xlsx.py` → subir a AMBOS archivos de Drive (`files().update`, NO `create` para no duplicar; IDs en `sync_from_drive.py` `XLSX_IDS`) → commit+push. Verificar con `sync_from_drive.py --dry-run` → debe decir `0 cambios del humano aplicados`.
2. **Slots del JSONL son naive (hora local -05); `now` en el cron es aware.** Restar `datetime.fromisoformat(slot)` contra `datetime.now(TZ)` lanza `TypeError` en cuanto hay una pieza `aprobado`, y rompe TODA la publicación en ese tick. El cron usa `_slot_dt()` que fija `tzinfo=TZ` cuando falta offset. Si vuelves a tocar la lógica de ventana (`timedelta(0) <= now - slot <= timedelta(hours=2)`), normaliza SIEMPRE.
3. **Dir de salida del cron en `root:root` mata la entrega.** El gateway corre como `uid 10000`; si `/opt/data/cron/output/<jobid>/` queda `root:root 700`, el scheduler no escribe → el job muere en entrega (el usuario ve `Connection reset` o `Permission denied`). Verificar con `stat -c '%U:%G'`; reparar con `docker exec hermes-agent chown hermes:hermes /opt/data/cron/output/<jobid>` (NO hay `sudo` en este contenedor). Barrido: `for d in /opt/data/cron/output/*/; do stat -c '%U:%G' "$d"; done | grep root`.

## Cierre de mes (IMPLEMENTADO — cron `calendario-informe-campana`)

- Cron diario 8:00 AM con autogate: solo actúa el PRIMER lunes de cada mes (script `content-intel/cron_campaign_report.py` → `campaign_report.py`). Idempotente via `reports/state.json`.
- Genera 1 DOCX con membrete NeuralCrew por marca de la campaña cerrada: plan vs ejecución, totales y por formato, top piezas, viernes-bingo vs resto, recomendaciones. Sube a la carpeta de campaña en Drive (resuelta por nombre `bingo-millonario-<brand>-<mes>`) y manda resumen WhatsApp al Admin.
- Límite documentado: clicks del link de bio NO expuestos por API Meta → no se reportan.
- Última pieza del mes (p.ej. bingo del 2-oct) entra con 48-72h de maduración en el informe del 5.
- Aprender: top performers y brechas del informe = insumo del calendario del mes siguiente.