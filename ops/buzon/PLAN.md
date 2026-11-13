# PLAN — Buzones de agentes: de polling cada minuto a push por webhook

Estado: **F0 en verde**. Autorización del Admin: 2026-11-13 ("trabaja en worktree aislado usando la skill reviewer con opencode deepseek, arma el plan por fases primero, orquesta y que nada quede sin revisarse y todas las fases tienen que quedar en verde").

## Problema medido (línea base, 13-nov 12:0x)

| Hecho | Evidencia |
|---|---|
| 8 perfiles corren `buzon-*` con `*/1 * * * *` | `cron/jobs.json` por perfil |
| Cada corrida levanta un worker del scheduler | 10 `cron.scheduler` simultáneos, ~90 MB RSS c/u |
| Despertares reales en toda la historia | 14 (`logs/buzon_handoff.log`) |
| Coste en tokens del polling | 0 (`{"wakeAgent": false}` corta el turno) |
| `agent_handoff.py` solo escribe el JSON | no dispara nada; el receptor pregunta |

Conclusión: el polling no cuesta dinero, cuesta CPU y memoria. El arreglo es push, con un barrido lento como red de seguridad.

## Contrato del receptor (leído en el código, no supuesto)

`gateway/platforms/webhook.py`:
- `POST /p/{profile}/webhooks/{route}` (el adaptador declara `serves_profile_prefix = True`).
- Auth **Generic V2**: `X-Webhook-Timestamp` (epoch, ventana anti-replay) + `X-Webhook-Signature-V2` = hex HMAC-SHA256 de `"<timestamp>.<body>"`.
- Idempotencia: `_header_delivery_id` prioriza `webhook-id`; TTL 3600 s, primero gana.
- `event_type` se toma de `payload["event_type"]`; el prompt de la ruta interpola campos con `{campo}`.
- `_route_allows_profile` puede restringir la ruta a perfiles concretos.

## Fases

### F0 — Preparación (VERDE ✅)
- `opencode` 1.18.35 + proveedor `nan` (`https://api.nan.builders/v1`) y modelo `deepseek-v4-pro`.
- Smoke test: `opencode run 'Responde solo: OPENCODE_SMOKE_OK' --model nan/deepseek-v4-pro` → `OPENCODE_SMOKE_OK`.
- Worktree aislado `/opt/hermes-agent-data/worktrees/buzon-push`, rama `feat/buzon-push-webhook`, base `d04667851e`.
- Criterio de verde: smoke responde y el worktree está limpio sobre el base.

### F1 — Módulo notificador `ops/buzon/notify.py` (código puro, sin efectos)
- Firma HMAC V2 + `webhook-id` estable por ticket.
- Contrato: **nunca lanza**; devuelve `NotifyResult(sent, status, reason)`.
- Timeout corto (2 s por defecto) y sin reintentos: el barrido lento es el reintento.
- Test-first con un servidor HTTP local que verifica la firma con la misma regla del adaptador.
- Casos: firma válida aceptada, firma inválida rechazada, timeout, 500, host inalcanzable, idempotencia del `webhook-id`.
- Criterio de verde: suite completa en verde (6/6) y `ruff`/`py_compile` sin errores.

### F2 — Integración en `agent_handoff.py`
- Tras el depósito atómico del JSON → `notify()` best-effort.
- El depósito **no puede fallar** por el webhook: si falla, se registra y sigue (el cron lo recoge).
- `--no-webhook` como flag CLI (regla del repo: nada de `HERMES_*` para config no secreta).
- Test-first: depósito OK con webhook caído → archivo presente + resultado `Failed`.
- Criterio de verde: tests en verde + depósito real verificado en disco.

### F3 — Ruta `buzon` en la config del gateway
- `platforms.webhook.extra.routes.buzon`: `secret` por ruta, `prompt` con `{ticket_id}`/`{de}`/`{asunto}`, `events: [buzon.nuevo]`.
- Requiere ventana de override del guard (`config_guard_override.json`) por ser cambio de config.
- Criterio de verde: `POST` firmado devuelve 202 y la sesión aparece en `state.db`.

### F4 — Canario con el polling AÚN encendido
- Un handoff real a un perfil → exactamente 1 sesión nueva, `.seen` marcado, el cron de 1 min no duplica.
- Criterio de verde: 1 sesión, 0 turnos duplicados.

### F5 — Retirar los 8 crons de cada minuto
- Backup de los 8 `jobs.json`; `*/1` → `*/30` (barrido de huérfanos).
- Criterio de verde: 8 jobs con `*/30`, `next_run` correcto, y un handoff con el webhook forzado a fallar sigue siendo recogido por el barrido.

### F6 — Revisión independiente (opencode + deepseek)
- Reviewer = `opencode run --model nan/deepseek-v4-pro`, READ-ONLY, dos rondas.
- Ronda 1: hallazgos clasificados + `VERDICT`.
- Ronda 2: checklist [FIXED|PARTIAL|NOT FIXED] por hallazgo.
- Criterio de verde: `VERDICT: APPROVE` y cero hallazgos BLOCKER abiertos.

### F7 — Cierre
- Commit convencional en la rama, sin atribución de IA, sin push.
- Informe final con los conteos reales y la nota en brain.

## Reglas de ejecución
- Nada se declara verde sin salida real de comando.
- Toda fase de código pasa por el reviewer; un veredicto intermedio no cierra la fase.
- Si una fase no puede quedar verde, se declara el bloqueo con su causa; no se maquilla.
