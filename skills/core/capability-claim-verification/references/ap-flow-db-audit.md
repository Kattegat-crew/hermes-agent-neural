# Auditar un orquestador ActivePieces por DB (read-only)

Caso trabajado: 11-sep-2026, PROD (`ap-db` en el VPS), pregunta «¿el pipeline automático de reels
está conectado?». Objetivo: decir qué flows existen, cuáles están **realmente** operando y dónde
se rompe, sin disparar nada y sin tocar la UI.

---

## 1. El patrón de consulta que sí funciona

`ssh + docker exec + heredoc` con comillas anidadas **falla de formas confusas** (`column ", " does not
exist`, `function left(jsonb, integer) does not exist`, o silencio). Patrón que funcionó a la primera:
escribir el `.sql` **en local** y pasarlo por stdin a `psql`:

```bash
ssh prod 'docker exec -i ap-db psql -U postgres -d activepieces -f -' < /tmp/ap_flows.sql
```

Dentro del `.sql`, empieza con `\pset pager off` y `\echo === sección ===` para separar bloques.

## 2. Esquema real (esta versión de AP)

- Contenedor: **`ap-db`** (no `ap-postgres`).
- Tablas: `flow`, `flow_version`, `flow_run`, `trigger_source`, `file`.
- **Columnas camelCase** → en SQL, entre comillas dobles: `"publishedVersionId"`, `"flowVersionId"`,
  `"displayName"`, `"logsFileId"`, `"externalId"`.
- `flow` **no** tiene `display_name` ni `name`: el nombre legible vive en `flow_version."displayName"`.
- `flow_version` **no** tiene columna `actions` (verificado en `information_schema.columns`):
  los pasos no se leen de ahí. Para el destino de un paso HTTP, usa los logs del run
  (`logsFileId` → `file.data` → base64 → `zstd -d`) o el estado serializado del flow.
- `flow_version.trigger` es un **objeto** jsonb, **no un array**.
- `flow.publishedVersionId` (no `published_version_id`).

## 3. Las tres consultas del veredicto

```sql
-- a) ¿qué existe y qué está publicado?
SELECT f.status,
       (f."publishedVersionId" IS NOT NULL) AS pub_ok,
       (SELECT v."displayName" FROM flow_version v WHERE v.id = f."publishedVersionId") AS nombre
FROM flow f ORDER BY f.status, nombre;

-- b) ¿la versión publicada es válida?
SELECT left("displayName",28) AS flow, valid
FROM flow_version
WHERE "displayName" ILIKE '%reel%' OR "displayName" ILIKE '%video generator%';

-- c) ¿corrió de verdad? (esto es lo que manda)
SELECT left(fv."displayName",26) AS flow, fr.status, count(*) AS n, max(fr.created) AS ultima
FROM flow_run fr JOIN flow_version fv ON fv.id = fr."flowVersionId"
GROUP BY 1,2 ORDER BY 1 DESC, 3 DESC;
SELECT f.id, f."externalId"
FROM flow f JOIN flow_version v ON v.id = f."publishedVersionId"
WHERE v."displayName" ILIKE '%reel%';
```

El id del flow **es** el de la URL del webhook: `.../api/v1/webhooks/<flow.id>`. Y esa URL es un
gatillo cargado: **no la sondees** — un GET la dispara.

## 4. Cómo se interpreta (reglas duras)

| Observación | Lectura correcta |
|---|---|
| `ENABLED` + `valid = t` + **0 corridas** | montado, **no** operando. El claim «ya está conectado» es falso. |
| `valid = f` | **zombi**: su publicación está rota; nadie debería poder dispararlo → retirarlo, no resucitarlo. |
| Fallos repetidos con fechas concretas | el flow **sí** se dispara y falla: busca el 400/500, no la configuración. |
| Solo un flow con tráfico reciente | el resto del pipeline es decorativo; dilo con la tabla de corridas. |
| `trigger->>'name' = trigger` (piece-webhook, `authType: none`) | el disparador es externo: alguien tiene que postear el body correcto. |

Regla de oro: **estructura ≠ tráfico.** Un informe que solo mira `flow`/`flow_version` sobreestima el
sistema; el veredicto sale de cruzar con `flow_run`.

## 5. Snapshot de la flota (11-sep-2026) — ejemplo real

7 flows, todos `ENABLED` con versión publicada:

- `Bre-B Lucky → aviso Discord` — **el único con tráfico real** (cada ~10 min, `SUCCEEDED`).
  Lección: el flujo de pagos sí estaba cableado y sano.
- `Reel Orchestrator` (`9wusDPr3RgmVXvZt8tszm`, `valid=t`) — 6 OK (16-ago) + **15 FAILED**
  (13 del 16-ago, 2 del 11-sep): se dispara y falla → problema de contrato del body.
- `Reel Callback Receiver` (`v6pQk2m8RgVnLx4tAeBzJ`, `valid=t`) — 1 OK + 1 FAILED, ambos del 16-ago.
- `Video Generator - pipeline completo` (`TiRdZ7xkbD86d2eM7B9KJ`, **`valid=f`**) — 1 FAILED (29-ago).
- `Chat IA Goldie - DeepSeek`, `Flow bono Golden`, `Webhook Bono → Email Paradise` — sin corridas.

De ahí salen dos decisiones que no se ven en la UI: (1) el orquestador necesita corregir su body,
(2) el «Video Generator» duplica al motor del repo y se **retira** en vez de arreglarse.

## 6. Prohibiciones

- No escribas en `flow`/`flow_version` en el mismo barrido de auditoría: primero el snapshot read-only,
  y cualquier escritura, sobre una **versión nueva** del flow y con backup previo
  (ver la skill de edición de flows, de propiedad del usuario).
- No dispares webhooks «para comprobar»: produce corridas reales y contamina métricas y correos.
- No reportes `ENABLED` como «funcionando».
