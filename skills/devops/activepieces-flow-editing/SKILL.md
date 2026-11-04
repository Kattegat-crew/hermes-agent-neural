---
name: activepieces-flow-editing
description: "Use when editing ActivePieces flows via Postgres."
tags: [activepieces, flows, postgres, sql, email-template, run-verification, self-hosted, plantillas]
author: Ragnar
version: "1.0"
created: 2026-08-25
category: devops
metadata:
  hermes:
    tags: [activepieces, flows, webhook, email-template, db-editing, run-verification, self-hosted, lead-automation]
    related_skills: [activepieces-selfhost-ops, activepieces-lead-automation, webhook-gateway-multiclient]
---

# ActivePieces Flow Editing & Run Verification (self-hosted, via direct DB)

## When to Use

- Changing a flow's **email HTML/layout**, recipients, or step timing, then confirming the executed run/email output.
- The AP **API/MCP auth returns 401/406** (or hangs) — the reliable route is **direct DB**, not the API.
- Flow runs are missing / templates look stale / an address field overflows — likely a `trigger_source` misalignment.
- You need the **actual emitted output** (email `accepted`, sheet row) from a run, not just `SUCCEEDED`.

## Core rule (the #1 gotcha)

The engine resolves **which flow version a webhook executes from `trigger_source.flowVersionId`**, NOT (only) `flow.publishedVersionId`.
If `trigger_source.flowVersionId` points at a **deleted** version, the webhook runs a **stale/cached template** and runs become unstable (404s, missing fields, wrong layout). Editing `flow_version.trigger` alone does NOT take effect.

So: edit → rewire `trigger_source` → restart BOTH engines → verify version.

## Steps (exact order)

1. **Backup** the trigger: `docker exec ap-db psql -U postgres -d activepieces -tAc "SELECT trigger::text FROM flow_version WHERE id='<vid>'" > backup.json` (back up before every write).
2. **Read** `flow_version.trigger` (JSON). The email HTML lives at step `displayName` → `settings.input.body.html`. Body may be a **dict** `{html, text}` OR a **plain string** — handle both. Walk steps via `nextAction`.
3. **Edit** the HTML. Placeholders are `{{trigger.body.<field>}}` (e.g. `{{trigger.body.sede}}`, `{{trigger.body.bonus_display}}`).
4. **Write back**: `UPDATE flow_version SET trigger='<json>'::jsonb, updated=now() WHERE id='<vid>'`. **Must** escape every `'` as `''` in the JSON (`.replace("'","''")`); a stray `'` silently breaks the literal.
5. **Rewire trigger_source** (every row of the flow): `UPDATE trigger_source SET "flowVersionId"='<published_vid>' WHERE "flowId"='<id>'`. Confirm `flow.publishedVersionId` equals the edited version.
6. **Restart BOTH `ap-app` AND `ap-worker`** (`docker restart ap-app ap-worker`). The **app** resolves webhook→version; the **worker** executes steps and caches the flow version. Restarting only one leaves the stale template in play.

## Verify a run used your edit + its output

```bash
# 1) Which version actually ran
docker exec ap-db psql -U postgres -d activepieces -tAc \
  "SELECT \"flowVersionId\", status FROM flow_run WHERE \"flowId\"='<id>' ORDER BY \"startTime\" DESC LIMIT 1"
# If this != your edited <vid>, trigger_source/publishedVersionId are misaligned.

# 2) The run's REAL output (email recipients, etc.) — stored compressed in `file`
FID=$(... SELECT "logsFileId" FROM flow_run WHERE id='<runId>')
# SELECT encode(data,'base64') FROM file WHERE id='<FID>'  ->  base64 -d  ->  zstd -d > run.json
# run.json: executionState.steps.*.output ; email step output has "accepted": [email]
```

## Timing + query pitfalls

- **El nombre del flow NO está en `flow.name`** — se lee de `flow_version."displayName"` (el que usamos para "probar" que corre un nombre, verificar por la fila de `flow_version` con el `flowId`). En SQL: `SELECT "displayName" FROM flow_version WHERE "flowId"='<id>' ORDER BY created DESC LIMIT 1`.
- **Patrón de prueba de leads (03/09):** nunca mandar un lead real del cliente a un flow que aún se está verificando. Usar el marcador **"PRUEBA INTERNA NO CLIENTE"** en el cuerpo/payload de prueba → verificar el run que se disparó (que llegó al destino esperado, p. ej. el email salió y el `accepted` contiene el correo de prueba) → **borrar el run de prueba** con `DELETE FROM flow_run WHERE id='<runId>'` para no contaminar métricas reales.
- AP returns `200 {}` on the webhook immediately but creates the flow run **~20–30 s later** (sandbox install/build). Do NOT conclude "no run" after 10–15 s.
- `flow_run.startTime` is **UTC**; comparing against a literal timestamp string is a timezone trap. Use `WHERE "startTime" > now() - interval '10 minutes'`.
- Don't pipe a big JSON query through your **local shell** (quoting breaks) — write the query/script to a file and `scp`+run on the host, or pass SQL as a psql **argument** (stdin `-i` was unreliable for large output).

## notifyActivePieces "fetch failed" (webhook server → AP)

The webhook container must reach the AP webhook URL (`http://<AP_IP>:8088/api/v1/webhooks/<flowId>`). Reproduce from inside the container:
`docker exec <webhook> node -e 'fetch(process.env.ACTIVEPIECES_WEBHOOK_URL,...).then(r=>console.log(r.status))'`.
Harden `notifyActivePieces` in `webhook-server.js` / `webhook-server-paradise.js`: raise the per-attempt timeout (8s→15s) and add N retries with backoff (1s,2s,3s). Validate with `node --check`, then restart the webhook container.

## References

- `references/edit-and-verify-recipes.md` — concrete SQL/commands for the whole flow, Google-Maps profile-link extraction, and the exact prod layout (Golden 3oGBil1naEsVErmbBz6KY, Paradise jIrDwFPupZwZJ9Z1y97YT; containers webhook-gateway/webhook-paradise; AP webhook `http://<AP_IP>:8088/api/v1/webhooks/<flowId>`).


<!-- absorbido de devops/activepieces-db-surgery (censo 2026-09-24) -->
## Topología del caso NeuralCrew (ACTUALIZADA 29/08 tras migrar AP a prod .222)

- AP vive en .222 (Tailscale 100.73.30.29); el reel-worker en dev .250 (Tailscale 100.86.8.81:8090). Los flows POSTean a `http://100.86.8.81:8090` — la URL vieja `10.0.1.1:8090` quedó MUERTA con la migración (dentro de ap-app no resuelve; probado 29/08). Verificar alcance: `docker exec ap-app curl -m 8 http://100.86.8.81:8090/health`.
- Acceso: SSH root@100.73.30.29 con la key del host → `docker exec -i ap-db psql -U postgres -d activepieces < /tmp/x.sql` (el `-f /tmp/x.sql` NO funciona: busca el archivo DENTRO del contenedor).
- Publicación: `flow.publishedVersionId` SÍ existe en esta versión de AP (los flows del reel pipeline lo tienen apuntando a su última versión). Sin embargo AP ejecuta la versión DRAFT — editar la fila DRAFT de `flow_version` alcanza; setear publishedVersionId solo alinea UI/estado.
- Webhook de producción por API: `POST http://localhost:80/api/v1/webhooks/<flowId>` dentro de ap-app (la ruta `/v1/...` SIN prefijo `/api` devuelve el HTML del SPA, no la API). Un POST de prueba con body mínimo devuelve `{}` 200 y genera un run; el paso piece-http fallará (400) si el body no pasa la validación del worker — eso confirma auth+conectividad sin crear jobs reales.

## Reglas del esquema (verificar con information_schema antes de fiarse — AP cambia entre versiones)

- IDs de `flow`/`flow_version` son `varchar(21)` base62 (tipo `TiRdZ7xkbD86d2eM7B9KJ`). **NO usar `gen_random_uuid()`** (36 chars → error de longitud). Generar en Python: `secrets.choice(ALPHABET)` 21 veces.
- NOT NULL de `flow_version`: `connectionIds` y `agentIds` son **ARRAY** (`ARRAY[]::text[]`, un JSON `'{}'` falla), `notes` es **JSONB pero AP lo crea SIEMPRE como ARRAY** (`'[]'::jsonb` — un `''` falla y un objeto `'{}'::jsonb` crashea la UI), `valid` bool, `state` ('DRAFT'), `trigger` jsonb.
- **Pitfall `notes` objeto (29/08):** INSERT con `'{{}}'::jsonb` deja `notes={}` y al abrir el flow la UI explota: `Unexpected Application Error! t.map is not a function` (el front hace `.map` sobre notes). Fix: `UPDATE flow_version SET notes='[]'::jsonb WHERE "flowId"=(SELECT id FROM flow WHERE "externalId"='<x>') AND jsonb_typeof(notes)='object';` + usuario refresca el navegador.
- `flow`: `externalId` (nombre visible/URL-safe), `status` ('ENABLED'), `deleted`='false' (check constraint — no null).
- El header/credencial de un piece-http vive en `trigger->nextAction->settings->input->headers` (jsonb). Trigger webhook = `settings.triggerName: catch_webhook`, piece `@activepieces/piece-webhook`; acción = piece `@activepieces/piece-http` action `send_request` con `url/method/body/headers/body_type`.

## Cómo pasar el SQL sin morir en el quoting

El quoting anidado docker→ssh→bash→psql rompe cualquier SQL con comillas inline. **Receta ganadora**: script Python que (1) construye el JSON con `json.dumps`, (2) escapa literales SQL duplicando `'`, (3) base64 del .sql, (4) SSH que ejecuta `echo <b64> | base64 -d > /tmp/x.sql && docker exec -i ap-db ... < /tmp/x.sql`. Correr ese Python por stdin en un contenedor con la key SSH montada:
`docker run --rm -i -v /root/.ssh:/keys:ro alpine sh -c 'apk add -q python3 openssh-client; python3 -' < inject.py`
(Usar `INSERT ... SELECT FROM flow WHERE "externalId"=...` para resolver el FK sin hardcodear ids.)

## Verificación obligatoria después de escribir

1. `SELECT` de vuelta: flow ENABLED + flow_version con el header correcto (verificar prefijo/sufijo del token contra uno freshly-minted).
2. E2E funcional: POST real al endpoint del worker con token minteado igual → esperar el código de éxito (202 en el worker AKARI; sin token → 401).
3. Los tokens JWT nunca se imprimen en el chat; generar y usar directo en el payload.

## Modelo de trigger canónico (reel pipeline, 28/08)

`webhook catch` → `piece-http POST http://100.86.8.81:8090/jobs` con `Authorization: Bearer <JWT firmado con REEL_WORKER_JWT_SECRET>` y `body: {"data": "{{trigger.body}}"}` (URL corregida 29/08; los 3 flows compartían la 10.0.1.1 muerta). Flows existentes: `reel-orchestrator` (9wusDPr3RgmVXvZt8tszm), `reel-callback` (v6pQk2m8RgVnLx4tAeBzJ), `video-generator` (TiRdZ7xkbD86d2eM7B9KJ) — todos ENABLED, publicados y E2E verificados 29/08 (mintear JWT con scripts/make_worker_token.py del repo video-ai-generator).
