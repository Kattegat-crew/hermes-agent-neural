# Multi-Tenant Enforcement — Detalle sesión 25/08/2026

## Contexto

Diseño acordado en equipo (Jonathan + Ragnar + Roshi + Vigía) para el hub de
integraciones de NeuralCrew Labs: ActivePieces self-hosted en prod
(169.58.189.222), versión 0.82.0 Community. Documentos fuente:
- `/opt/data/plans/DISENO-INTEGRACIONES-PERSISTENTES-MULTI-TENANT.md`
- `/opt/data/plans/PLAN-IMPLEMENTACION-COMMS-BOT.md`

## Inventario prod (verificado 25/08)

- `ap-app` Up, `ap-worker` Up, `ap-db` Up, `ap-redis` Up
- UI: HTTP 200 en http://100.73.30.29:8088/ (SOLO IP Tailscale, no 127.0.0.1)
- MCP: HTTP 405 en /mcp a GET (correcto — espera POST con JWT)
- RAM host: 23Gi total, 15Gi libre → sin presión
- 0 conexiones creadas aún (tabla connection vacía) — arrancamos de cero

## Payload JWT para MCP de AP (mcp_oauth, HS256, TTL 15 min)

```json
{
  "sub": "<user_id>",
  "projectId": "<project_id>",
  "platformId": "<platform_id>",
  "type": "mcp_oauth",
  "aud": "MCP_OAUTH_ACCESS",
  "iat": <now>,
  "exp": <now + 900>
}
```
Secret: `AP_JWT_SECRET` (docker exec ap-app printenv AP_JWT_SECRET)
Issuer: `activepieces`

## Ejemplo del mapa (connections-map.json)

```json
{
  "jonathan-gmail": {
    "owner": "default",
    "service": "gmail",
    "hub": "activepieces",
    "tenant": "jonathan",
    "status": "pending",
    "updated": "2026-08-25"
  },
  "neuralcrew-gmail": {
    "owner": "comms",
    "service": "gmail",
    "hub": "activepieces",
    "tenant": "neuralcrew",
    "status": "pending",
    "updated": "2026-08-25"
  }
}
```

## Conexiones planeadas (orden de negocio)

| Conexión | Tenant | Servicio | Owner |
|----------|--------|----------|-------|
| helmer-gmail | Helmer | Gmail | helmer |
| golden-gmail | Golden Game | Gmail | golden |
| lucky-gmail | Lucky Brothers | Gmail | lucky |
| jonathan-gmail | Jonathan | Gmail | default |
| neuralcrew-gmail | NeuralCrew Labs | Gmail | comms |
| jonathan-canva | Jonathan | Canva | default |
| golden-meta-ads | Golden Game | Meta Ads | golden |
| lucky-meta-ads | Lucky Brothers | Meta Ads | lucky |
| jonathan-meta-ads | Jonathan | Meta Ads | default |
| golden-search-console | Golden Game | Search Console | golden |
| jonathan-mercado-libre | Jonathan | MercadoLibre | default |
| digital-expr-amazon-sp | Digital Expressions | Amazon SP-API | default |

## Pruebas realizadas (25/08)

- `ap_call.py --connection jonathan-gmail` con HERMES_HOME=helmer →
  `{"blocked": true, "reason": "perfil helmer no es dueño de jonathan-gmail"}` exit 1 ✅
- Uso legítimo llegó a la fase JWT; el contenedor hermes-agent NO tiene SSH al
  host (solo llave id_ed25519_github) → pendiente inyectar AP_JWT_SECRET como env.

## Lecciones del flujo de conexión para clientes

- El setup pesado (Google Cloud Console: OAuth client, redirect URIs, scopes) se
  hace UNA vez por servicio, nunca por cliente.
- AP Community expone botón "Conectar" por servicio; embedded connections (iframe
  SDK) permiten poner el botón en la web propia.
- El cliente solo aprueba en la pantalla del proveedor ("Permitir"). AP guarda el
  refresh token y lo refresca solo.
- Google Identity Services es la alternativa sin AP para "Continuar con Google"
  directo en la web (pierdes multi-servicio de AP).
