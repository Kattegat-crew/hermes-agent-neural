# Phonic — Speech-to-Speech Voice Agents (verified 2026-10-29)

Provider for full-duplex AI voice agents (NeuralCrew Connect voice receptionist). Status at verification: plan Starter ($30 free credits), no phone number attached yet — calls are cost-gated.

## Secret handling (mandatory order)
1. API keys arriving via chat go FIRST to Vaultwarden (gestor único) as an item, then materialize a working copy at `/opt/data/secrets/phonic-api.json` (0600, owner hermes). Never hardcode in repos or scripts.
2. Every request authenticates with the `api_key` from that secret file as a standard Bearer token in the Authorization header. Read the key in Python/JSON at runtime — never paste it into commands, logs or docs.

## Verified API recipe (base https://api.phonic.co/v1)
- **Auth/health:** `GET /agents` — a 200 with the agents list confirms auth.
- **Voices:** `GET /voices` — base voices only (39 at verification; voice cloning is separate). Spanish-CO pick: `valeria`.
- **Create agent:** `POST /agents` with JSON body `{"name":..., "voice":"valeria", "timezone":"America/Bogota", "prompt":...}`.
- **Verify after create AND after every update** (PATCH can silently no-op fields): `GET /agents` and confirm the exact fields (id, voice, timezone) came back. Ids look like `agent_<uuid>`.
- Recommended built-ins on receptionist agents: `natural_conversation_ending` + `choose_not_to_respond` (enable at create; do not rely on defaults).

## Capability map
- **In-call tools:** `custom_webhook` (call our endpoints mid-conversation → ActivePieces/Twenty), `custom_websocket`, `custom_context`, MCP tools, transfer to human/other agent (SIP REFER).
- **Built-ins:** DTMF keypad, natural hang-up, silent-turn skip.
- **Post-call webhooks:** `conversation.ended`, `conversation.analysis` (transcript + analysis), `conversation.transferred` → pipe into our CRM/leads stack.
- **Extraction schemas:** structured fields from the call (name, phone, intent) → CRM.
- Also available: pronunciation dictionary (brands/locations), mid-call language switching, evals, and **replay** (test prompt changes on recorded calls without burning minutes).

## Cost discipline
- Real phone calls consume paid credits → spend_gate rules: present plan and get explicit Admin OK before attaching a number or placing calls. Agent config/exploration on a free account is not billable.

## Position vs the rest of this skill
- Phonic = live conversational S2S agent with its own API + telephony (peer of Bland/Vapi, with richer mid-call tool/webhook integration).
- Twilio direct call (`twilio-call`) remains the right tool for one-way prerecorded voice delivery; Phonic/Bland/Vapi for live conversation.
