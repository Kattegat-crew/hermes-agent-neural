# Baseline de consumo de la flota DEV — sep-2026

Medición del **11-sep-2026** sobre los 12 `state.db` de DEV (default + 11 perfiles),
periodo **1-sep → 11-sep**. Sirve para comparar mes contra mes con
`scripts/audit_token_usage.py`.

## Totales

| Tarea | Tokens | % | Llamadas |
|---|---|---|---|
| Conversación principal (chat + delegación) | 1.347,7M | **84,7 %** | 10.190 |
| `background_review` (curador de skills) | 240,6M | **15,1 %** | 1.344 |
| `compression` | 1,4M | 0,09 % | 49 |
| `vision` | 0,7M | 0,04 % | 162 |
| `approval` (guardrail SOUL) | 0,1M | 0,01 % | 230 |
| `title_generation` | 0,1M | 0,01 % | 99 |
| **TOTAL** | **1.590,6M** | 100 % | 12.235 |

Por modelo: `deepseek-v4-flash` 1.134M (71 %) · `glm5.3-flash` 192M · `qwen3.8-flash` 128M ·
`mimo-v2.5` 98M · `deepseek-v4-pro` 25M · `gemma4` 12M.

**cache_read ≈ 92 % del total**; prefijo medio ≈ **137k tokens/llamada** en el modelo principal
(≈189k en `background_review`). Verificado: la suma in+out+cache_read del DB ≈ `tokensUsed`
que reporta la API del proveedor → **el cap cuenta los cache reads**.

## Concentración por sesión (top 6 de 251)

| Sesión | Tokens |
|---|---|
| discord «Consultar APIs de fall.ai en vault» | 155,0M |
| telegram «Saludo amistoso» | 97,4M |
| telegram «Confirmar grafo y cron configurados» | 90,1M |
| desktop «Reels Golden» | 82,7M |
| whatsapp «Saludo amistoso inicial» (2 sesiones) | 65,6M |
| subagentes (32 sesiones) | 44,2M |

Las 14 mayores ≈ 900M = **71 %** del total.

## Estado de la config al medir

- 12 configs idénticos: principal y las 9 auxiliares en `deepseek-v4-flash`;
  `smart_model_routing.cheap_model = qwen3.6` (roshi y vigia sin `cheap_model`).
- `compression.threshold`: 0,5 en default y roshi; **0,75 en los otros 10 perfiles**.
- `session_reset`: `mode: both`, `idle_minutes: 120`, `at_hour: 6` en los 12.
- `curator`: `enabled: true`, `interval_hours: 168` (default); los perfiles no declaran
  bloque `curator` (heredan defaults — los perfiles son islas, no heredan del default).
- `auxiliary.background_review` **no declarado** en ningún config → hereda el runtime del
  padre con caché caliente (`routed=False`).

## Cuota del proveedor en la misma fecha

`GET cloud-api.nan.builders/api/usage/quota`: `deepseek-v4-flash` 42,4 % con proyección
**114,8 %** al reset del 1-oct (cap 3.000M) → 🔴; `qwen3.8-flash` 26,4 % (proy. 71,5 %);
`glm5.3-flash` 14,6 % (proy. 39,5 %, cap 2.000M); `mimo-v2.5` 7,2 %. Detalle de la API en
`devops/hermes-desktop-plugins → references/nan-builders-quota-api.md`.

## Plan derivado

`brain/plans/plan-consumo-nan-dev-2026-09-11.md` (curador a `glm5.3-flash` + compresión más
agresiva + reset de inactividad a 60 min + rollout idempotente a los 12 configs).
Si el plan se aplicó, **re-medir** antes de dar nada por bueno.
