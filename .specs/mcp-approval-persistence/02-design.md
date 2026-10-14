# 02-design: Technical Design for MCP Tool Approval Persistence

## 1. Architectural Architecture & Component Boundaries

```
[ Model calls MCP Tool (server, tool, args) ]
                    │
                    ▼
   mcp_tool_handlers.py :: _trust_gate_check()
                    │
                    ├──> 1. Is server trust == full OR tool readOnlyHint == true?
                    │       └──> Yes: proceed (return None)
                    │
                    ├──> 2. Is (server:tool) approved in memory or config?
                    │       tools/approval.py :: is_mcp_approved(session_key, server, tool)
                    │       └──> Yes: proceed (return None) [NO SPAM]
                    │
                    └──> 3. Not approved: Request Human Consent
                            tools/approval_prompt.py :: request_mcp_tool_consent(...)
                            │
                            ├──> Dispatches to active surface (WhatsApp, Discord, TUI)
                            │    Payload includes redacted arguments summary
                            │
                            └──> Human Decision:
                                 ├──> "deny" / timeout: return tool_error (fail-closed)
                                 ├──> "once": proceed without saving
                                 ├──> "session": approve_mcp_session(session_key, server:tool)
                                 └──> "always": approve_mcp_permanent(server:tool)
                                                -> atomic write to active profile's config.yaml
```

## 2. Data Structures & State Management

### A. In-Memory Stores ([`tools/approval.py`](file:///opt/hermes-agent/tools/approval.py))
```python
# Session-level authorizations: session_key -> set("server:tool")
_mcp_session_approved: dict[str, set[str]] = {}

# Profile-level permanent baseline: home_key -> set("server:tool")
_mcp_permanent_approved_by_home: dict[str, set[str]] = {}
```

### B. Persistent Storage (`config.yaml`)
Stored in the profile's respective `config.yaml` (`$HERMES_HOME/config.yaml`):
```yaml
mcp_allowlist:
  - "twenty_write:find_many_people"
  - "twenty_write:create_note"
  - "cloudflare_write:list_zones"
```

Reconciliation with disk follows the existing `save_permanent_allowlist()` atomic pattern:
```python
def save_permanent_mcp_allowlist(items: set[str]) -> None:
    config = load_config()
    on_disk = set(config.get("mcp_allowlist", []) or [])
    with _lock:
        key = _baseline_key()
        baseline = _mcp_permanent_baseline_by_home.get(key, set())
        merged = on_disk | (set(items) - baseline)
        config["mcp_allowlist"] = sorted(merged)
        save_config(config)
        _mcp_permanent_baseline_by_home[key] = set(merged)
        governing = _mcp_permanent_set()
        governing.clear()
        governing.update(merged)
```

> [!NOTE]
> **Authoritative Revocation Path:** Reconciling with `baseline` separates items approved prior to boot from items approved in the current process lifetime. To ensure permanent removal without resurrecting entries during subsequent tool approvals, revocations MUST be performed via `/approvals revoke mcp <server:tool>` (or programmatically via `approval.revoke_mcp_permanent()`), which atomically clears both disk, baseline, and governing sets.
>
> **Admin-Only Enforcement:** In shared channels and DMs, all mutation and inspection subcommands (`/approvals mcp`, `/approvals revoke mcp`) are strictly gated by `policy.is_admin(user_id)`. Non-admin users cannot inspect allowed lists or mutate profile allowlists.


## 3. Profile Isolation Mechanics (Ragnar vs Roshi)

| Metric | Ragnar | Roshi |
| :--- | :--- | :--- |
| **`HERMES_HOME`** | `/opt/hermes-agent-data` | `/opt/hermes-agent-data/profiles/roshi` |
| **Target Config** | `/opt/hermes-agent-data/config.yaml` | `/opt/hermes-agent-data/profiles/roshi/config.yaml` |
| **Primary Channel** | WhatsApp (`whatsapp:<phone>`) | Discord (`discord:thread:<id>` / `discord:channel:<id>`) |
| **`_baseline_key()`** | `""` (root launch profile) | Hash of `roshi` directory path |
| **Cross-Contamination** | Zero: isolated memory set & isolated config file | Zero: isolated memory set & isolated config file |

## 4. Session Expiration & Subagent Inheritance
1. **WhatsApp Sessions:**
   - Bound to `whatsapp:<phone_number>`.
   - In-memory entries in `_mcp_session_approved` are purged upon:
     - `clear_session(session_key)` (triggered by session reset cron at 05:00 BOT or turn boundary restart).
     - Inactivity exceeding session TTL (2 hours without turns).
2. **Discord Sessions (Roshi):**
   - Bound to `discord:thread:<thread_id>` (or channel).
   - In-memory entries are scoped strictly to the thread/channel room where the grant occurred.
3. **Subagent Delegation:**
   - Subagents running under an active coordinator pass their parent's `session_key` to `_trust_gate_check`, inheriting active session grants without re-prompting.

## 5. Security & Blind Approval Prevention
- Before prompting, `_trust_gate_check` extracts the tool's invocation arguments.
- Sensitive values (API keys, passwords, bearer tokens) are redacted using `agent.redact.redact_sensitive_text`.
- The human receives a card:
  - Header: `Hermes / Roshi wants to run write tool '{tool}' on server '{server}'`
  - Arguments Preview: `target: "contacts", payload: {"name": "Empresa X", ...}`
  - Buttons: `[1 Vez]` `[Esta Sesión]` `[Siempre]` `[Denegar]`
