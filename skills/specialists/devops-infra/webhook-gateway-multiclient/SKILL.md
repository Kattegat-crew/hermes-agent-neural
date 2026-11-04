---
name: webhook-gateway-multiclient
description: "Use when building a multi-client webhook chat gateway"
tags: [webhook, gateway, express, multiclient, postgres, activepieces, leads, nginx]
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.0"
---

# Webhook Gateway (Multi-Client)

## Activation Contract

Use when connecting browser chat widgets to a Hermes/agent gateway that requires a server-side API key, while persisting leads/conversations and firing per-client automation.

## Hard Rules

- Never expose the Hermes `API_SERVER_KEY` to the browser: the widget calls a same-origin `/webhook/...` path proxied by nginx to this gateway; the gateway injects the Bearer key.
- Hermes cold start can take 20–90s. Set gateway fetch timeout to 90s AND bump the widget's `AbortController` timeout from 20s to 90s, or requests abort before a reply.
- Use one PostgreSQL pool per client DB (e.g. `golden_game`, `paradise_casino`); tables live inside each DB, not in a shared schema.
- Keep one ActivePieces webhook URL per client flow (IDs differ per client); a single global URL sends every lead to one client's flow.

## Decision Gates

| Concern | Action |
|---------|--------|
| Client routing | Listen on separate ports (e.g. 3099 golden, 3100 paradise) or prefix paths |
| Auth | `Authorization: Bearer $API_SERVER_KEY` to `$HERMES_GATEWAY/p/<profile>/v1/chat/completions` (OpenAI format) |
| Persistence | `INSERT INTO leads (...)`, `INSERT INTO conversaciones (session_id, mensaje_usuario, respuesta_ia)` |
| Automation | Fire-and-forget `fetch(ACTIVEPIECES_WEBHOOK_URL_<client>)` after lead insert, with AbortController 8s timeout |
| Safety | CORS whitelist of client domains, `express-rate-limit` (20/min signup, 10/min chat), sanitize input, cap history length |

## Execution Steps

1. Create Express app: helmet, CORS whitelist from env, JSON body limit 16kb, rate limiters.
2. Build `pg.Pool` per client DB; sanitize name/phone/email/sede and history.
3. Implement `callHermes(profile, history, message)` → POST to `/p/<profile>/v1/chat/completions`, return `choices[0].message.content`.
4. Wire routes: `/webhook/<client>-vip-signup`, `-chat`, `-contact` per client; each with its own DB pool + AP webhook URL.
5. Deploy as docker compose (node:22-alpine) binding to the host docker-gateway IP (e.g. `10.0.1.1:3099/3100`) so landing nginx configs can reach it.
6. Verify: `/health`, a chat round-trip, a lead insert + AP flow run `SUCCEEDED`.

## Output Contract

Return: gateway routes and ports, per-client DB pools and AP URLs, timeout values, and E2E verification results (chat reply + lead row + AP run status).

## References

- `activepieces-lead-automation` — AP flow shape and webhook IDs.
- `nginx-proxy-manager-api` — exposing the gateway/domains.
