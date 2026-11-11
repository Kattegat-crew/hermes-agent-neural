---
name: activepieces-flow-ops
description: Use when building or testing ActivePieces flows over MCP.
---

# ActivePieces Flow Ops (Internal MCP)

Headless, full-lifecycle flow building on ActivePieces using its internal MCP
server — no UI, no paid API key. Complements `activepieces-lead-automation`
(which covers lead pipelines, caches, logs and the REST publish path).

## When to Use

- Creating or editing AP flows programmatically (trigger + steps)
- Testing a draft flow and reading its structure
- Debugging "No connections found" / piece-prop validation errors

## When NOT to Use

- Lead-capture specifics, cache purge, run-log inspection → `activepieces-lead-automation`
- Direct DB writes to `flow_version` (forbidden — see lead-automation skill)

## Handshake (SSE MCP)

MCP endpoint is the instance's `/mcp` path. Every request needs header
`Accept: application/json, text/event-stream`; responses are SSE — keep only
lines starting with `data: ` and parse each as JSON.

1. Authenticate with a minted MCP OAuth JWT (HS256, 15 min TTL — see the
   lead-automation skill §1 for minting from the instance's JWT secret).
2. POST `initialize` → capture the `Mcp-Session-Id` response header.
3. POST `notifications/initialized` carrying that header.
4. `tools/call` with `{"name":"ap_...","arguments":{...}}` + the session header.

Regenerate the JWT on any 401 (15-minute expiry is the usual cause).

## Tool Contracts (verified by real calls)

- `ap_create_flow {"flowName":...}` → returns flowId; flow starts with an EMPTY trigger.
- `ap_update_trigger`: required `flowId, pieceName, pieceVersion, triggerName, input`.
  Webhook trigger = piece `@activepieces/piece-webhook`, trigger `catch_webhook`,
  `input:{"authType":"none"}`. Trigger inputs live under `input` — never `settings`.
- `ap_add_step`: required `flowId, displayName, parentStepName,
  stepLocationRelativeToParent, stepName, stepType, pieceName, pieceVersion,
  actionName, input`. To insert after the trigger: `parentStepName:"trigger"`,
  `stepLocationRelativeToParent:"AFTER"`. `displayName` is REQUIRED even when
  redundant with `stepName`.
- `ap_get_piece_props`: needs `pieceName, pieceVersion, actionOrTriggerName, type`
  where `type` is `action` or `trigger` (required!). Returns the exact input
  schema — always consult it before composing `input`.
- `ap_flow_structure {"flowId":...}` → DFS step list, valid insert locations,
  and output-reference syntax (`{{stepName.field}}`, no `.output.` in the path).
- `ap_test_flow {"flowId":...}` runs the draft; it refuses while the trigger is
  still invalid — fix the trigger first.
- `ap_update_step {"flowId", "stepName", "input"}` — rewrites an existing step's
  input in place without deleting it (verified: swapping a hardcoded auth token
  for the `{{connections["<externalId>"]}}` reference).

Discover pieces/actions with `ap_list_pieces` (`includeTriggers:true`) and the
server's own `tools/list`.

## Connections Are Project-Scoped

`app_connection.projectIds` lists which projects can see a connection. A flow
created in (or an MCP JWT minted for) a different project gets
`"No connections found"` in piece props even though the connection row exists.

Fix: create the flow — and mint the JWT — inside a project listed in that
column (check with a read-only query on `app_connection`).

Also note: personal API keys authenticate some read endpoints but are rejected
on flow-mutation routes; the minted JWT is the reliable credential.

## Common Mistakes

| Error | Real cause | Fix |
|-------|-----------|-----|
| Trigger "still invalid" after update | Inputs nested under `settings{}` | Put them under `input{}` |
| `ap_add_step` invalid_type on displayName | Field omitted | Always pass it |
| `ap_get_piece_props` invalid_value | `type` missing | Add `"action"` or `"trigger"` |
| "No connections found" in authHint | Project scoping (see above) | Match flow + JWT project to the connection |
| `ap_test_flow` refuses | Trigger invalid | Fix trigger, retry |
| MCP 401 mid-session | JWT expired (15 min) | Mint a fresh one |
| custom_api_call → 401 de Google | Token CLOUD_OAUTH2 vencido (~1 h); self-hosted NO lo refresca | Reconectar en UI y correr el flow dentro de la ventana; detalle en `activepieces-connection-api` |
| Heredoc/shell corrompe el JSON con `{{connections[...]}}` o `$vars` | El shell interpola el cuerpo | Pasar los argumentos por archivo (`@/tmp/args.json`) y leerlos en el wrapper |
