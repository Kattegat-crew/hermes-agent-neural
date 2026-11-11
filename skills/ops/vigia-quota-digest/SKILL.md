---
name: vigia-quota-digest
description: "Use when reporting or fixing quota cron digests."
tags: [quota, cron, vigia, nan-builders, codex, antigravity, opencode]
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
---

# Informe de cuotas de suscripciones (Vigía)

Pipeline: `scripts/quota_digest.py` (datos) → `profiles/vigia/scripts/vigia_quota_digest.sh`
(wrapper) → job `quota-digest-2x` del perfil `vigia` (`0 8,20 * * *`, America/Bogota).

## Fuentes y granularidad

- **Codex / OpenCode Go / Antigravity**: leen `$HERMES_HOME/quota_cache.json`, escrito por
  el plugin `quota` (`quota_cache.refresh_quota_cache()`). Ventanas 5 h / semanal / mensual.
- **NaN (nan.builders)**: `scripts/nan_quota.py` → `GET /api/usage/quota` con API key `sk-`
  (tokens por modelo, `extraTokens` = packs). El **% de créditos del plan, el saldo y la
  caducidad de packs** salen de `GET /api/usage/credits`, que **no acepta la API key** (401
  `session_required`) y exige la cookie `nan_session` del dashboard. NaN entra por magic
  link al correo `digitalexpresions1@gmail.com` (cuenta `killer420w`):

  ```bash
  python3 scripts/nan_session_login.py --request            # pide el link (HTTP 202)
  # leer el correo (Gmail MCP, cuenta digitalexpresiones1) y copiar la URL
  python3 scripts/nan_session_login.py --link "<URL del correo>"  # canjea y guarda
  ```

  El canje son dos pasos: la URL devuelve una página con `name="flow" value=...` y hay que
  hacer `POST /api/auth/login/verify` con `token`, `client=browser` y `flow` (el 302 trae el
  `Set-Cookie: nan_session`). El secret queda en `/opt/data/secrets/nan-session.json` (0600)
  y caduca a los ~14 días: el informe avisa cuando faltan 4 o menos. **Nunca imprimir la
  cookie ni el token del link.**

## Trampas verificadas (no repetir)

- **`hermes quota` muestra % RESTANTE**, no usado (`commands.py`: `rem = 100 - used`).
  El caché y el informe usan `used_percent`. Un 77 % en la CLI es 23 % usado.
- **Token de Discord del perfil vigia**: el perfil no tiene la plataforma configurada, así que
  `--deliver discord:...` falla. Publicar con `scripts/vigia_post_thread.sh`, que resuelve el
  token en este orden: variable de entorno → `/opt/data/secrets/discord-nca-bot.token` →
  `.env` legacy. Un grep solo en `.env` devolvía vacío y los avisos se perdían con exit 0
  (falso verde en el cron) — pasó del 25-oct al 11-nov sin que nadie lo notara.
- **`nan_quota.analyze()`** pone `period_end` con el `periodEnd` del **primer** modelo; los
  modelos `kind='window'` (4 h) traen su propio reset. Usar `resets_at` por modelo primero.
- **Discord corta a 2000 chars**: limitar filas (MAX_NAN_ROWS) y dejar el pie visible.
- **Scripts sueltos no ven los secretos del gateway**: `hermes quota ...` hidrata 26–41
  secrets; por eso el refresh se pide al CLI y no se reimplementan los fetchers.

## Cambiar settings del plugin quota (D-I-V-E obligatorio)

`config.yaml` está protegido por `hooks/guard_config_model_mutation.py`. La ventana
`/opt/data/state/config_guard_override.json` **solo** autoriza
`python3.12 scripts/cfgctl.py apply <candidato>`; ni `cp` ni `hermes config set` pasan.

1. `python3.12 scripts/cfgctl.py snapshot --label <motivo>`
2. Construir el candidato insertando **al final del bloque `plugins:`** (antes de la
   siguiente clave de nivel 0, p. ej. `hooks:`). Insertar tras la última clave de plugin
   parte el bloque de ese plugin y `cfgctl validate` NO lo detecta.
3. `cfgctl.py validate <cand>` y **comprobar la semántica con PyYAML** (`yaml.safe_load`:
   valor aplicado + plugins vecinos intactos) antes de aplicar.
4. `cfgctl.py apply <cand> --yes` → verificar de nuevo el config vivo → cerrar la ventana
   dejando `[]` en el override.
5. Verificar efecto real: `hermes quota refresh` y mirar las ventanas del provider.

Agy (Antigravity) requiere `plugins.entries.quota.settings.antigravityEnabled=true`; lee el
token de `~/.gemini/antigravity-cli/antigravity-oauth-token` del usuario del gateway.

## Verificación de la entrega

`post:200` no basta: hay que releer el hilo y confirmar el mensaje con el id devuelto por la
API de mensajes del canal. Sin esa relectura el cron puede marcar «ok» con el aviso perdido.
