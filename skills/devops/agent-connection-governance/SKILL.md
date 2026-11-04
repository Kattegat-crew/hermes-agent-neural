---
name: agent-connection-governance
description: "Use when isolating OAuth connections per agent."
tags: [activepieces, oauth, multitenant, conexiones, agentes, enforcement]
version: "1.0"
author: Ragnar
created: 2026-08-25
category: devops
metadata:
  hermes:
    tags: [activepieces, oauth, multitenant, conexiones, enforcement, agentes, integraciones]
    related_skills: [activepieces-selfhost-ops, hermes-multiprofile-cron-ops]
---

# Agent Connection Governance — Multi-Tenant Integrations

## When to Use

- Diseñar cómo varios agentes (perfiles Hermes) comparten un hub de integraciones
  (ActivePieces) sin cruzar cuentas de clientes.
- Conectar correos/cuentas por tenant (helmer-gmail, golden-meta-ads, ...) y
  garantizar que cada agente solo use las suyas.
- Onboarding de clientes con OAuth sin fricción (botón "Conectar").
- Auditar qué conexión usó cada agente (compliance de credenciales).

## Regla de oro

**AP (Community self-hosted) NO impone aislamiento entre agentes.** Todas las
conexiones viven en un solo proyecto; Projects es premium (Team ~$166/mes).
El aislamiento real lo construyes tú: "el SOUL es el contrato, la Capa 5 es la ley".

## Modelo de 5 capas (orden de dependencia)

1. **SOUL.md** — contrato de identidad: cada perfil declara "solo uso conexiones `{tenant}-*`"
2. **Mapa de conexiones** — `connections-map` en Engram (topic_key estable, proyecto
   compartido) + `/opt/data/connections-map.json` local: `{tenant}-{servicio}` → owner.
   Las credenciales NUNCA van al mapa — solo el mapa lógico.
3. **Projects premium AP** — solo cuando >5 clientes o requisito de compliance
4. **Auditoría** — health-check cruza qué conexión usó cada agente
5. **Wrapper `ap_call` (LA LEY)** — todo acceso pasa por el script; bloquea si el
   perfil llamador no es dueño, ANTES de tocar AP

## Patrón del wrapper ap_call (Capa 5)

- Detecta perfil de `HERMES_HOME` (`/opt/data/profiles/<name>` → name; `/opt/data` → default)
- Valida contra el mapa: `owner != profile` → `BLOCKED: perfil X no es dueño de Y` (exit 1)
- Si es dueño: genera JWT HS256 tipo `mcp_oauth` (TTL 15 min, secret `AP_JWT_SECRET`
  del contenedor ap-app) y llama `POST {AP_URL}/mcp` con `tools/call`
- Registra TODOS los intentos (permitidos y bloqueados) en `/opt/data/logs/ap_call.log`
- Script funcional: `scripts/ap_call.py` (probado 25/08: bloqueo cruzado OK)

## Naming de conexiones (desde el día 1)

Formato `{tenant}-{servicio}`: `helmer-gmail`, `golden-meta-ads`, `jonathan-canva`,
`neuralcrew-gmail`. Un vistazo al mapa dice de quién es cada cuenta. Si el naming
se decide tarde, renombrar conexiones rompe referencias — decidirlo antes de crear.

## Flujo de conexión para clientes (sin fricción)

- El OAuth Client ID/Secret de cada servicio se configura **UNA vez** (dominio
  interno), no por cliente.
- El cliente solo hace: click en "Conectar mi Gmail/Canva/Meta" → "Permitir" en el
  proveedor → AP guarda refresh token en Postgres y lo refresca solo.
- AP soporta **embedded connections** (iframe SDK) para poner el botón dentro de tu
  propia web — el cliente nunca entra a AP.
- Para clientes con infra propia: link OAuth directo de Google (mismo principio, más manual).
- Correo de onboarding disparado solo cuando el `campaign.yaml`/brief ya validó
  (QA-INTEGRIDAD OK) — no molestar al cliente antes de empezar a trabajar.

## Límites Community self-hosted (verificado 25/08)

| Recurso | Community (self-hosted) | Premium |
|---------|------------------------|---------|
| Flows | Ilimitados | — |
| Tasks/ejecuciones | Ilimitadas | — |
| Conexiones OAuth | Ilimitadas | — |
| MCP servers | Ilimitados | — |
| Projects (workspaces con permisos) | ❌ | Team ~$166/mes |
| SSO / audit logs / git sync / RBAC | ❌ | Team/Ultimate |

## Pitfalls

- **Health checks de AP:** en prod AP bindea SOLO a la IP Tailscale
  (ej. `100.73.30.29:8088`), NO a `127.0.0.1` — un check contra localhost da 000
  falso negativo. `/mcp` responde 405 a GET (espera POST con JWT) — eso es correcto.
- **JWT secret:** `AP_JWT_SECRET` se lee de `docker exec ap-app printenv
  AP_JWT_SECRET`. El contenedor hermes-agent NO tiene SSH al host (llave solo
  GitHub) — inyectar el secret como env var o compartirlo en el `.env` del contenedor.
- **Community no tiene Projects:** no diseñar aislamiento asumiendo Projects;
  usar naming + mapa + wrapper.
- **Regla de datos:** nunca guardar credenciales en Engram/mapa — solo el mapa
  lógico (tenant → conexión → servicio).

## Referencias

- `references/multi-tenant-enforcement.md` — detalle de la sesión 25/08: inventario
  de prod, payload JWT, ejemplo del mapa, tabla de conexiones planeadas.
- `scripts/ap_call.py` — wrapper funcional de enforcement (Capa 5).

## Related

- `activepieces-selfhost-ops` (user-owned) — operación del stack AP (OOM, compose).
- `hermes-multiprofile-cron-ops` (user-owned) — crons por perfil y limpieza de
  entregas (`cron.wrap_response: false`).