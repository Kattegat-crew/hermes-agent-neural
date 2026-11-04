# API de cuota de nan.builders (verificada 11-sep-2026)

Descubierta en `prgr1no/gnome-nan-usage` (extensión GNOME) y **verificada en vivo
con nuestra propia key**: la API de inferencia (`api.nan.builders/v1`, LiteLLM) NO
expone uso; el backend del panel web sí, con la misma key como `Bearer`.

## Endpoints (SIN contrato público — degradar en silencio)

| Ruta | Devuelve |
|---|---|
| `GET https://cloud-api.nan.builders/api/usage/quota` | `periodStart` + `models[]` con `model`, `tokensUsed`, `cap`, `remaining`, `updatedAt`, `periodEnd`; los modelos de ventana traen además `fullWindowTokens` y `windowHours` |
| `GET /api/auth/me` | `handle`, `email`, `discordId`, `region`, `tier`, `role`, `features`, `userUUID`, `expiresAt` — **tiene datos personales: no devolver tal cual** |
| `GET /api/metrics/usage` | consumo agregado 24 h / mes / 30 d |

- CORS: preflight `204` **sin** `Access-Control-Allow-*` → un renderer (plugin de
  Desktop, widget de dashboard) **no** puede llamarlo directo; va por el gateway
  (`ctx.rest`) o por script de servidor.
- `GET` puro = sin costo y sin consumir tokens: sirve como health-check barato del
  proveedor y como base de un watchdog de gasto.

## Modelo de alerta por consecuencia (mejor que un umbral fijo)

- 🟠 ámbar si la proyección lineal al reset (usado / fracción transcurrida) ≥ **75 %** del cap.
- 🔴 rojo si a ese ritmo se agota antes del reset y el bloqueo estimado ≥ **10 %** del periodo.
- Si ha transcurrido < **5 %** del periodo, no extrapolar (la media es ruido).
- Modelos de ventana móvil (`fullWindowTokens` + `windowHours`, p. ej. 400 M / 4 h):
  mostrar % de ventana, sin proyección.

## Implementación en la agencia (11-sep-2026)

| Pieza | Ruta |
|---|---|
| Cliente + proyección (fuente única) | `data/scripts/nan_quota.py` |
| Watchdog (silencioso salvo alerta, reaviso 6 h) | `data/scripts/nan_quota_watch.py` |
| Cron | `nan-quota-watchdog`, `*/30 * * * *`, `no_agent`, deliver `discord:1542631941583409303` (#crons-anuncios) |
| Snapshot servido a la UI | `data/state/nan-quota.json` |
| Backend del plugin | `data/plugins/nan-usage/dashboard/{manifest.json,plugin_api.py}` → `/api/plugins/nan-usage/{summary,quota,account,refresh}` |
| Mitad UI | `data/drafts/nan-usage-desktop-plugin/plugin.js` (chip `statusBar.right` + panel `panes`) |

La key se lee de `providers.NaN-Builders.api_key` en `config.yaml` (regex, sin
PyYAML, para que el cron no dependa del venv) y **nunca** sale del servidor.
