---
name: two-way-sync-state-integrity
description: "Use when a canonical store syncs an editable mirror."
tags: [sync, sincronizacion, state-integrity, estado, idempotencia, monotonico, data-integrity, git]
version: 1.0.0
author: Ragnar
---

# Integridad de estado en sincronizaciones bidireccionales (canonical store ↔ editable mirror)

## Cuándo usar esta skill

Cuando existe:

- un **store canónico** versionado (JSONL/JSON en Git, tabla SQL, DB de la app), y
- una **superficie espejo editable por humanos** (XLSX en Drive, Google Sheets, Notion DB, panel de admin),
- con un script de sync que aplica los cambios del espejo al store (y a veces al revés),
- y aparece alguno de estos síntomas: "el estado X se ve mal en la tabla" (lo que el humano ve no coincide con lo que el sistema hizo); un estado avanzado/terminal **retrocede** solo; el estado oscila entre ticks; un informe/contador subcuenta trabajo ya ejecutado.

## Inmutables (aplicar al diseñar o al reparar)

1. **Máquina de estados monotónica.** Define el orden (`a_producir < listo_para_aprobacion < aprobado < publicado` o el que aplique) y prohíbe las transiciones hacia atrás automáticas. El sync del espejo NUNCA debe bajar de un estado terminal: si el espejo dice `aprobado` y el store dice `publicado`, el store gana y se **registra la divergencia** (log/fila/nota), no se aplica.
2. **Todo escritor del store re-sube el espejo.** Si un proceso cambia el estado (publicación, envío, cierre), DEBE regenerar y subir la superficie espejo al mismo ID (`files().update`, nunca `create`). Un escritor que no sube el espejo deja al humano mirando datos viejos — y el sync lo convierte en fuente de verdad al tick siguiente.
3. **Prueba de simetría.** `grep -rn "files().update\|MediaFileUpload\|upload"` (o el equivalente del provider) y verificar que **cada** punto que escribe estado también actualiza el espejo. Si sólo lo hace el flujo de aprobación, el flujo de ejecución está roto.
4. **Orden dentro del tick.** Si el sync corre al INICIO del tick y la ejecución después, el espejo (potencialmente viejo) gana siempre. Documenta el orden y evalúa mover el sync a después de la ejecución, o hacerlo monotónico.
5. **Idempotencia y auto-sanado con ventana.** Un auto-sanado condicionado a una ventana temporal (`slot ±2h`) repara dentro de la ventana y abandona después: no es una garantía. El auto-sanado debe ser incondicional o el invariante debe vivir en el sync.
6. **El estado no es la evidencia.** Reporta y cuenta con los campos de hecho (`publicado_en`, `media_ids`, `sent_at`, `external_id`) más el registro de eventos (registry/log), no con la columna `estado` que el espejo puede pisar.

## Diagnóstico reproducible (5 pasos, todo read-only)

1. **Historia del store, no memoria.** Si es Git:
   ```bash
   git log -p --format='COMMIT %h %ad %s' --date=short -- <ruta del store> | grep -E '^COMMIT|<ID afectado>'
   ```
   Busca el par `-publicado +aprobado` dentro de un commit de SYNC: eso prueba la reversión y delata el tick culpable.
2. **Quién escribe el estado:** `grep -n "estado" <script_sync> <script_ejecutor>` — localiza la asignación y su filtro de elegibilidad.
3. **Quién sube el espejo:** grep de upload/update en todo el repo. Comparar con el paso anterior (si son conjuntos distintos, ya tienes el bug).
4. **Leer el espejo tal como lo ve el humano** (no el archivo local, que puede estar al día): `--dry-run` del sync que descargue el master y leer la columna de estado de las filas afectadas.
5. **Medir el impacto colateral:** `grep -rn "'publicado'\|== *estado" <repo>` — cualquier informe/dashboard que cuente por estado hereda el defecto y subcuenta.

## Checklist de verificación tras el fix

- [ ] Filas afectadas restauradas a su estado real + espejo regenerado y subido a TODAS las copias.
- [ ] `sync --dry-run` → `0 cambios` (prueba de que el espejo ya refleja la verdad y no revertirá).
- [ ] Un tick completo deja el estado en el valor terminal (no oscila).
- [ ] El contador del informe coincide con el número de eventos reales en el registry.

## Anti-patrones

- Sync bidireccional "lo que diga el espejo gana" sin ranking de estados → reverts silenciosos.
- Subir el espejo sólo desde el flujo manual (aprobar) y no desde el automático (ejecutar/publicar).
- Curar el síntoma (reescribir la fila a mano) sin arreglar quién la pisa: al tick siguiente vuelve.
- Reportar "publicado/cerrado" basándose en la columna que el espejo controla.

## Casos documentados

- `references/marketing-calendar-xlsx-jsonl.md` — calendario de campaña NeuralCrew (JSONL en Git ↔ XLSX en Drive): el sync de cada tick revertía `publicado`→`aprobado`; diagnóstico completo, 6 filas afectadas, impacto en el informe de cierre y plan de reparación.
