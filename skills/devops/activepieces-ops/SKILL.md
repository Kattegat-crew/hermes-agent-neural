---
name: activepieces-ops
description: Use when flows or OAuth connections break in ActivePieces.
---

# ActivePieces PROD — diagnóstico y reparación

## Superficies
- App/API: `http://100.73.30.29:8088` (contenedores `ap-app`, `ap-worker`, `ap-db`, `ap-redis` en PROD `169.58.189.222`).
- MCP propio de AP: `http://100.73.30.29:8088/mcp`, auth `Authorization: Bearer <token>` desde `/opt/data/secrets/ap_<proyecto>.token` (clave `token`). Responde SSE (`event: message` + `data: {...}`). Cliente listo en `scripts/ap_mcp.py`.
- Tools útiles del MCP: `ap_list_flows`, `ap_flow_structure`, `ap_list_connections`, `ap_update_step`, `ap_test_step`, `ap_test_flow`, `ap_validate_flow`, `ap_lock_and_publish`, `ap_change_flow_status`, `ap_get_run`, `ap_list_runs`.

## Diagnóstico de un run FAILED
1. DB: `flow_run` usa columnas camelCase entre comillas (`"flowId"`, `"flowVersionId"`, `"failedStep"`). El nombre del flow vive en `flow_version."displayName"`, no en `flow`.
2. `environment` distingue `TESTING` (tests del builder) de `PRODUCTION`; `status` del flow es `ENABLED`/`DISABLED` y `publishedVersionId IS NULL` significa draft nunca publicado. Clasifica ANTES de escalar: runs `TESTING` de un flow `DISABLED` son pruebas manuales del builder, no incidentes de producción — reporta como ruido, no como caída, y verifica cuántos runs son `PRODUCTION` antes de hablar de incidente.
3. `failedStep` trae el error del piece — leerlo antes de especular.
4. Para reproducir el error del proveedor fuera de AP usa los secrets materializados `/opt/data/secrets/{conexion}.json` (client_id/client_secret/refresh_token): refresca con `POST https://oauth2.googleapis.com/token` `grant_type=refresh_token` y llama a la API directamente. Aísla en un paso si el problema es de AP o del proveedor, sin descifrar la DB.
4. Ojo con los IDs: el `auth` de un step referencia el **`externalId`** de `app_connection`, NO su `id`. Comparar `id` contra el step produce falsos positivos de "conexión borrada".

### 429 RESOURCE_EXHAUSTED con `quota_limit_value: "0"`
No es rate limiting: es la API sin cuota en el proyecto GCP del OAuth client, señal de que la API no está habilitada/aprobada (las de Business Profile exigen solicitud de acceso; sin aprobación la cuota queda en 0/min). Ningún retry ni re-autorización lo arregla — el fix es humano: habilitar/solicitar la API en `console.cloud.google.com` para el proyecto del client. Para confirmar el estado exacto de habilitación hace falta scope `cloud-platform` (ServiceUsage); con scope limitado, el propio cuerpo del 429 ya nombra el servicio y la cuota.

## Conexiones CLOUD_OAUTH2 muertas (401 del proveedor)
Síntoma: el step falla con 401 del proveedor mientras `app_connection.status` sigue `ACTIVE` y `updated` no cambia (el token nunca se refresca).

### Causa raíz por clase de client (verificado 09-nov-2026, conexión GBP)
- Si la conexión se creó con el **OAuth client gestionado por Activepieces** (`client_id 674512252699-…`, visible en `value` descifrado), el `client_secret` vive SOLO en el SaaS de AP: el refresh local es imposible por diseño y el `access_token` muere a ~1 h (401 verificado a las 2 h de creado). Re-autorizar desde el popup solo compra otra hora.
- **Fix permanente:** crear la conexión con un **OAuth client propio** (p. ej. proyecto GCP NCL `288239405432`, mismo client de calendar/drive/gmail cuyos secret+refresh_token ya viven en `/opt/data/secrets/`). Requisito: habilitar las APIs del piece en ese proyecto GCP (para GBP: `mybusinessaccountmanagement`, `mybusinessbusinessinformation`, `mybusinessverificationinfo`; el slug de performance es `businessprofileperformance`, NO `mybusinessbusinessprofileperformance`).
- Antes de reconectar a ciegas, identificar la clase: descifrar `value` y mirar el prefijo del `client_id`.

Diagnóstico:
1. Descifrar `app_connection.value` dentro de `ap-worker` (AES-256-CBC, key = `Buffer.from(process.env.AP_ENCRYPTION_KEY,'binary')`, `iv`/`data` en hex). También funciona fuera del contenedor: `docker exec ap-app printenv AP_ENCRYPTION_KEY` + Python `cryptography` (Cipher AES-CBC, unpad PKCS7) sobre el JSON `value` (que llega como string dentro de la fila). Revisar `claimed_at`: si está congelado en la fecha de creación, el refresh nunca corrió.
2. Refresh real: `POST https://secrets.activepieces.com/refresh` con `{refreshToken, pieceName, clientId, edition:'ce', tokenUrl}`. Si devuelve `access_token`, la credencial está viva y el problema es solo el value persistido.
3. Probar la API del proveedor con ese token fuera de AP. Si responde 200, el value en DB está corrupto, no la credencial.

Reparación: reescribir `value` con un token fresco y `claimed_at = now` (mismo cifrado, iv nuevo), luego `UPDATE app_connection SET value=..., updated=now()`.

Verificación obligatoria del refresh automático: volver a poner `claimed_at` en el pasado (>1h) y ejecutar `ap_test_step`. Si el run sale OK y `claimed_at` se actualiza solo, AP volvió a refrescar y el fix es estable. Si no, no publicar el flow.

## Crear una conexión OAuth2 sin popup (vía API)
El popup de AP se bloquea cuando el click no es gesto real de usuario. Alternativa determinista:
1. Construir la URL de autorización a mano con el `client_id` del piece (se ve en el `window.open` del frontend o en `value.client_id` de otra conexión del mismo piece), `redirect_uri=https://secrets.activepieces.com/redirect`, `access_type=offline`, `prompt=consent` y el `scope` del piece. Abrirla en el navegador (con `local=true` si se necesita la sesión del usuario) y completar el consentimiento; el `code` aparece en la URL final de `secrets.activepieces.com/redirect`.
2. `POST /api/v1/app-connections` exige **token de usuario** (`localStorage.token` del frontend), no la service key del proyecto — con service key responde `principal is not allowed for this route`.
3. Body (CLOUD_OAUTH2): `{externalId, displayName, pieceName, pieceVersion, projectId, type:'CLOUD_OAUTH2', value:{type:'CLOUD_OAUTH2', client_id, code, scope, props:{}}}`. `externalId` y `value.scope` son obligatorios; sin ellos da 400 genérico.
4. El `code` de Google caduca en minutos: crear la conexión justo después del consentimiento.
5. Verificar con `tokeninfo?access_token=...` que la cuenta autorizada es la esperada — no basta con que el step devuelva 200.

## Google Business Profile
`GET mybusinessaccountmanagement.googleapis.com/v1/accounts` solo lista cuentas (una personal). Las fichas se listan en `mybusinessbusinessinformation.googleapis.com/v1/accounts/{id}/locations?readMask=name,title,storefrontAddress,phoneNumbers,websiteUri&pageSize=100`. Si `accounts` devuelve 1 cuenta PERSONAL pero hay 12 sedes, es normal: las locations cuelgan de esa cuenta.

## Verificación end-to-end
- `ap_lock_and_publish` + `ap_change_flow_status ENABLED`, después `POST http://100.73.30.29:8088/api/v1/webhooks/<flowId>` y confirmar `flow_run` en `PRODUCTION` con status `SUCCEEDED`.
- Nunca declarar arreglado por el `SUCCEEDED` del test: confirmar el output real del step (`ap_get_run`).

## Lección
- Un `SUCCEEDED` de `ap_test_step` inmediatamente después de tocar la conexión puede usar el value cacheado del run anterior. Repetir el test antes de concluir.
