# 01-spec: MCP Tool Approval Persistence (Session & Always)

## 1. Problem Statement
When Hermes executes write-capable tools on MCP servers configured as `trust: untrusted`, [`tools/mcp_tool_handlers.py:_trust_gate_check`](file:///opt/hermes-agent/tools/mcp_tool_handlers.py#L60-L86) enforces an approval prompt on every single invocation.

Although the gateway surfaces (WhatsApp, Discord, Telegram, Web UI) present buttons for `Once`, `Session`, `Always`, and `Deny`:
1. [`tools/approval_prompt.py:_consent`](file:///opt/hermes-agent/tools/approval_prompt.py#L280-L285) collapses `("once", "session", "always")` indiscriminately into `"accept"`.
2. The user's intended scope (`session` vs `always`) is discarded before reaching the gate.
3. `_trust_gate_check()` does not maintain or consult any prior approval cache for MCP tools.

This causes extreme approval fatigue (e.g. 15 consecutive WhatsApp notifications during a single Bre-B reconciliation in Ragnar, and constant blockers when Roshi operates on Twenty CRM / ActivePieces via Discord).

## 2. Business Intent & Operational Goals
1. **Zero Repeated Prompts in Session:** When an operator approves with `"session"`, subsequent calls to `server:tool` within that active session execute immediately without prompting.
2. **Durable Persistence Across Restarts:** When an operator approves with `"always"`, the authorization persists across gateway restarts in the active profile's configuration.
3. **Multi-Profile Isolation (Ragnar vs Roshi vs Vigía):** A permanent or session approval granted to Ragnar must NEVER bleed into Roshi or other profiles. Each profile manages its own `mcp_allowlist` in its own `config.yaml`.
4. **Multi-Channel Compatibility:** Seamless operation on WhatsApp (session bounded by conversational window / daily reset), Discord (session bounded by thread/channel), Telegram, and API Server.
5. **No Blind Approvals:** The approval prompt must summarize the target payload/arguments (redacted of secrets) to avoid granting blank checks on generic dispatcher tools (e.g. `execute_tool`).
6. **Chat-Based Revocation:** Operators must be able to inspect and revoke granted permissions directly from chat via `/approvals`.

## 3. Explicit Non-Goals & Antipattern Vetoes
1. **No Mixing with Shell Allowlists:** MCP authorizations must NOT be injected into `command_allowlist` (which is reserved for terminal/regex shell commands).
2. **No Global `_consent()` Mutation:** MCP server-initiated elicitations (per-call protocol sampling) must remain per-call. Only client-side tool trust gating supports duration scopes.
3. **No Blanket Trust:** Solving approval fatigue must NEVER be done by setting `trust: full` across all servers. Servers remain `trust: untrusted` while specific vetted tools gain durable approval.

## 4. Acceptance Criteria
- **AC-1 (Session Scope):** In both Ragnar (WhatsApp) and Roshi (Discord), a tool approved with `"session"` requires exactly 1 prompt; subsequent calls in the same session execute with 0 prompts.
- **AC-2 (Always Scope):** A tool approved with `"always"` is persisted in the profile's `config.yaml` under `mcp_allowlist` using atomic file locking.
- **AC-3 (Profile Isolation):** `always` approval in Roshi updates `/opt/hermes-agent-data/profiles/roshi/config.yaml` and does NOT appear in Ragnar's `/opt/hermes-agent-data/config.yaml`.
- **AC-4 (Deny & Fail-Closed):** Denying a prompt blocks execution immediately without retry. Timeouts and disconnected transports fail closed.
- **AC-5 (Revocation):** Executing `/approvals revoke mcp <server:tool>` removes the rule from memory and disk; the next invocation prompts for approval again.
