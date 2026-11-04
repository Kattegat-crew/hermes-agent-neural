# QA-INTEGRIDAD — formato de ejemplo y detalle

## Ejemplo real de salida (empresa ficticia demo, 2026-08-25)

```
# QA-INTEGRIDAD — Reporte de campaña

**Campaña:** demo-campana | **Generado:** 2026-08-25T19:26:56
**Estado: ✅ OK — listo para QA de ejecución**

## Issues (bloqueantes)
- Ninguno ✅

## Warnings (revisar)
- ⚠️ PROMO: promoción vacía → se publicará como [PENDIENTE DE CONFIRMAR]
```

## JSON acompañante (misma data, parseable por bots)

```json
{
  "generated_at": "2026-08-25T19:26:56",
  "campaign_slug": "demo-campana",
  "status": "OK",
  "issues": [],
  "warnings": ["PROMO: promoción vacía → se publicará como [PENDIENTE DE CONFIRMAR]"]
}
```

Exit code: 0 ↔ status OK, 1 ↔ status REVISAR. Los bots deciden por status/exit, no por texto.

## Checks ejecutados por build_campaign.py

| Categoría | Check | Severidad |
|-----------|-------|-----------|
| LEGAL | regulador definido (no vacío) | issue |
| LEGAL | edad mínima >= 18 | issue |
| LEGAL | umbral de retención (numérico, != 0) | issue |
| LEGAL | nota de política de datos (Ley 1581/2012) | issue |
| MARCA | nombre comercial no vacío | issue |
| CAMPAÑA | mes no vacío | issue |
| CAMPAÑA | start_date válida YYYY-MM-DD | issue |
| CAMPAÑA | sin start_date | warning |
| SEDES | featured_sedes ⊆ company.sedes | warning |
| PROMO | promoción vacía | warning |

## Convención multi-tenant de conexiones (equipo de bots)

- Nombre de conexión AP/MCP: `{tenant}-{servicio}` — ej. `helmer-gmail`, `lucky-gmail`, `golden-meta-ads`, `jonathan-canva`, `jonathan-meta-ads`.
- Mapa lógico `tenant → conexión → servicio` en Engram con `topic_key: connections-map` (proyecto neuralcrew) — consultable por cualquier agente.
- Credenciales/refresh tokens NUNCA van a Engram: solo la referencia al nombre de conexión.
- Flujo: agente → consulta mapa → invoca AP con esa conexión → AP resuelve credenciales. Si la conexión no existe, reportar al operador (Vigía), nunca adivinar ni reutilizar la de otro tenant.
- OAuth multi-cuenta pesado (Gmail, Meta, Canva, MercadoLibre, Amazon SP-API, Search Console) → ActivePieces como hub; API key simple (Twenty, Engram, ElevenLabs, fal.ai, WhatsApp) → MCP/gateway directo, sin AP.