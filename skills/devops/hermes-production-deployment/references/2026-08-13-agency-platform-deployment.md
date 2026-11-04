# Agency Platform Deployment — NeuralCrew Labs Case

## Context

Deployment plan for a multi-client AI agency selling qualified leads to casinos (Golden Game, Lucky/Paradise). Stack: Twenty CRM + Hermes v0.20.0 (one per client) + ActivePieces + Formbricks + Langfuse + Nan API.

## Key Decisions (13/08/2026)

### Router: NO LiteLLM
**Why:** Supply chain breach 12/08/2026 — TeamPCP compromised LiteLLM versions 1.82.7/1.82.8 via Trivy → PyPI token theft → malicious `.pth` Python hook. 153GB exfiltrated from 2,488 organizations (Nvidia, AWS, Samsung, Boeing, Intel, Salesforce, Cisco...). 118,829 CI/CD runner dumps with secrets in plaintext.

**Alternative:** Use Hermes native fallback chain (config.yaml `provider.fallback`/`model.fallback`) + OpenRouter as second provider. No external router needed for <5-8 clients.

### Rate Limiting
**Current:** Nginx `limit_req_zone` + middleware in the bridge widget (10 msg/min per session_id, Bearer token per client). No router needed.

**Future (>5-8 clients):** Evaluate Portkey Gateway (open source, MIT, ~12k⭐, similar to LiteLLM but without breach history).

### Cost Tracking
**Tool:** Langfuse self-hosted. Sample at 10-20% (not 100%) to save RAM/CPU.
**Method:** Each trace is tagged with client identifier. Langfuse estimates token cost per model per client. Actual Nan API costs are calculated from token volume × Nan's pricing.

### Bridge Widget → Hermes
Transport: `POST https://hermes.neuralcrewlabs.com/api/chat`
```
Request: { session_id, message, client }
Response: { reply, session_id, actions }
Auth: Bearer token per client
Rate limit: 10 msg/min per session_id
Fallback: If Hermes no response in 5s → "Un asesor te contactará" + create lead
```
CORS restricted to landing domains. Session stored in localStorage.

### Thirty CRM
Deployed in dev at port 3020, workspace "NeuralCrew Labs", admin digitalexpresions1@gmail.com.
GraphQL + REST API, multi-workspace via `IS_MULTIWORKSPACE_ENABLED=true`.
Built-in Workflows (triggers: record events, schedule, manual, webhook → actions: CRUD, send email, HTTP request, code).

## Timeline (for reference)

```
W1: Twenty CRM dev testing → VPS prod setup
W2: Twenty CRM prod → Hermes per client (Golden + Lucky)
W3: ActivePieces + Formbricks + Chat Widget integrations
W4: Full integration testing + go-live
```

## Document

Full plan at: `/opt/data/brain/entities/neuralcrew-agency-platform-plan-v1.1.md`

## Modelos de LLM

| Rol | Modelo | Contexto |
|-----|--------|----------|
| Principal | deepseek-v4-flash | 1M tokens |
| Smart routing | qwen3.6 | <160 chars, <1.5s |
| Web extraction | mimo-v2.5 | 1M tokens |
| Fallback | OpenRouter (proveedor con crédito) | — |