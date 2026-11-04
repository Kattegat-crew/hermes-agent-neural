---
name: outline-wiki-ops
description: "Use when operating the Outline wiki API, docs, or backups."
tags: [outline, wiki, api, devops, docs, diario, backup]
version: 1.0.0
author: Ragnar
license: MIT
metadata:
  all_triggers: [outline, wiki, api, colecciones, diario, backup, publicar docs, templatize]
  hermes:
    tags: [outline, wiki, api, devops, docs, diario]
    category: devops
    related_skills: [hermes-multiprofile-cron-ops, vps-ops]
---

# Outline Wiki Ops (wiki.neuralcrewlabs.com)

Operar la wiki de la empresa: leer/publicar docs vía API, mantener colecciones,
backups y el Diario automático. Todo verificado en producción contra Outline
**1.9.2 exacto** — las features se comprueban contra el source de esa versión
(`https://raw.githubusercontent.com/outline/outline/v1.9.2/<ruta>`), NO contra la
doc actual de Outline (difiere: p. ej. "bases de datos" no existen en 1.9.2).

## Topología

- PROD: host Tailscale `100.73.30.29`, contenedores `outline` + `outline-postgres`
  (usuario y DB postgres: `outline`).
- URL canónica: `https://wiki.neuralcrewlabs.com`. El servidor fuerza redirect 301
  si el header `Host` no coincide con esa URL.
- 6 colecciones correctas (una por empresa): Golden, Digital Expressions, Bendabal,
  Guaya Racing, Lucky Brothers + NeuralCrew Interno. NO usar "Endaval"/"Warrior
  Racing"/"Lucky Broders".
- API solo alcanzable por la IP Tailscale del host, puerto 3042. Desde el
  contenedor Hermes (DEV) se llega directo a `http://100.73.30.29:3042`.

## Acceso API

Cabeceras OBLIGATORIAS en cada llamada:

```
Authorization: Bearer <key>
Host: wiki.neuralcrewlabs.com
X-Forwarded-Proto: https
```

Sin `Host` + `X-Forwarded-Proto` la respuesta es un 301 que parece "empty response".
Todos los endpoints son **POST** (GET da 301/405).

Keys de servicio existentes:
- "Ragnar (orquestador)": secret en `/root/.outline-apikey-ragnar` (PROD, chmod 600)
  y `/opt/data/.outline-wiki-key` (DEV, chmod 600).
- "neural-agents": key previa con scopes (ya existía).

NUNCA imprimir el secret en chat, logs o documentos — siempre [REDACTED].

## Crear una API key de servicio (si hiciera falta otra)

Fuente de verdad: `server/models/ApiKey.ts` + `server/utils/crypto.ts` de la
versión exacta instalada (raw de GitHub).

1. Formato del secret: `ol_api_` + 38 chars alfanuméricos aleatorios.
2. `hash` = sha256 hex del secret completo; `last4` = UPDATE aparte tras el INSERT
   (calcular substr en bash dentro del INSERT falló por comillas).
3. Antes del INSERT, mirar `information_schema.columns` de `"apiKeys"` para los
   NOT NULL reales (no confiar en memoria ni en la doc).
4. Probar SIEMPRE end-to-end con un endpoint de lectura (`collections.list`)
   antes de dar el insert por bueno.

## Quirks verificados de la API 1.9.2

- `documents.create` con `templateId` → **403 authorization_error** con API key.
  Workaround: `documents.info` de la plantilla → pasar su `text` como `text` del
  doc nuevo (resultado equivalente).
- `documents.search` con `collectionId` → **403**. Buscar sin filtro y filtrar en
  cliente por `d["document"]["collectionId"]`.
- Los resultados de `search` anidan el doc: usar `r["data"][i]["document"]`, no
  `r["data"][i]` directo.
- `documents.delete` → manda a papelera; segunda llamada con `permanent: true` →
  borrado definitivo (funciona con API key).
- `documents.templatize` convierte un doc markdown en plantilla nativa — no hace
  falta construir JSON Prosemirror a mano.
- `documents.create` SIN `publish:true` deja el doc en **BORRADOR** (no aparece en
  `list`). Para publicar uno ya existente: `documents.update({id, publish:true})`.
  El endpoint `documents.publish` da **404** con la key de servicio (no existe como
  ruta válida para esa key); usar `update` en su lugar.
- `documents.list` **FILTRA los borradores** (devuelve solo publicados) y además
  tiene lag/caché (a veces omite un doc publicado). Para auditar dups/borradores
  usar `documents.search` (trae TODO, incl. borradores) — NUNCA confiar en `list`
  para contar/verificar.
- `documents.move` devuelve `ok` pero NO garantiza el parent → verificar SIEMPRE con
  `documents.info` (responde el `parentDocumentId` real). La respuesta del move a
  veces da parent null aunque diga ok.
- **CRÍTICO**: NO se puede mover un doc dentro de un doc que está en BORRADOR →
  error "Cannot move document inside a draft" (400). Publicar el padre ANTES de
  mover los hijos.
- `documents.create` SIEMPRE crea un doc nuevo aunque el título se repita (no hace
  upsert) → correr el script de publicación varias veces genera duplicados. Dedupe:
  normalizar título (emojis >127 ignorados, á→a/ñ→n, —→-, colapsar espacios),
  agrupar por (collectionId, título), conservar el de mayor contenido, borrar los
  placeholders vacíos con `documents.delete`.
- NO hay bases de datos nativas en 1.9.2 (llegaron en versiones posteriores):
  las tablas van como tablas markdown en docs dedicados, con doc hijo enlazado
  cuando un análisis es extenso.

## Publicación idempotente (patrón Diario)

1. `documents.search` del título → si existe: `documents.update`; si no:
   `documents.create` con `parentDocumentId` y `publish: true`.
2. Sección por agente con marcador único `## <Agente> — <fecha>`; si ya está en el
   texto → `[SKIP]` (idempotente ante re-runs y pruebas).
3. Si varios perfiles publican en el mismo doc y comparten state.db (ver
   hermes-multiprofile-cron-ops), el bloque de sesiones se publica solo la
   primera vez; los siguientes perfiles lo omiten (dedupe por substring).

## Backups

- Cron en el host PROD: `30 3 * * *` → `pg_dump | gzip > /root/outline-backup-YYYYMMDD.sql.gz`,
  retención 14 días (`find /root -name "outline-backup-*.sql.gz" -mtime +14 -delete`).
- Antes de cambios estructurales (borrados masivos, migraciones, retoques de
  colecciones): `pg_dump` manual primero. Regla: backup → cambio → verificar.

## Automatización del Diario

Los crons `guardar-diario-memoria` (23:00) de los perfiles default/roshi/vigia
corren `guardar_diario_wiki_step.py`: wrapper que ejecuta el reporte local
(`daily_session_report.py`) y luego `publish_daily_wiki.py` (publica la entrada
del día en NeuralCrew Interno → Diario). Detalles del rollout, job IDs y
snippets en `references/2026-08-27-wiki-diario-auto-publicacion.md`.

## Pitfalls

- Llamar a la API sin probar antes la key con un endpoint de lectura → debug
  a ciegas. Siempre `collections.list` primero.
- SQL por SSH con comillas anidadas rompe bash (literales con `"` dentro de `"`):
  usar Python con `subprocess` en modo argv (sin shell intermedio).
- Probar desde dentro de la red Docker: `docker run --rm --network outline_default
  curlimages/curl:latest …` — la primera tirada descarga la imagen y parece
  colgarse; reintentar, la segunda va al instante.
- `docker exec outline sh -c 'find / …'` dentro del contenedor Outline se cuelga:
  no buscar en su filesystem; ir al source de la versión en GitHub.
- Un `pg_dump` del contenedor postgres requiere ejecutarse DENTRO del contenedor
  (`docker exec outline-postgres pg_dump …`), no en el host.
