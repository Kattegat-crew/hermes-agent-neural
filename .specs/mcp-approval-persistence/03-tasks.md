# 03-tasks: Implementation Checklist & Verification

## Checklist

- [x] **Task 1: Red-Phase Test Suite Creation**
  - Extended `tests/tools/test_mcp_trust_gating.py` with `TestMCPApprovalPersistence` (4 tests).
  - *Observed RED proof:* 4 failed, 19 deselected in 11.98s before implementation.

- [x] **Task 2: Decoupled Storage Layer in `tools/approval.py`**
  - Implemented `_mcp_session_approved`, `_mcp_permanent_approved_by_home`, `_mcp_permanent_baseline_by_home`.
  - Implemented `is_mcp_approved()`, `approve_mcp_session()`, `approve_mcp_permanent()`, `revoke_mcp_permanent()`.
  - Reconciled with active profile's `config.yaml` under `mcp_allowlist`.
  - Verified `clear_session()` cleans session-level MCP authorizations.

- [x] **Task 3: Structured Consent Handler in `tools/approval_prompt.py`**
  - Implemented `request_mcp_tool_consent()` with `(verdict, scope)` return tuple.
  - Preserved standard `_consent()` untouched for protocol-level MCP elicitations.

- [x] **Task 4: Gate Integration in `tools/mcp_tool_handlers.py`**
  - Updated `_trust_gate_check()` to check `approval.is_mcp_approved()` prior to prompting.
  - Automatically records `approve_mcp_session` or `approve_mcp_permanent` based on user selection.
  - *Observed GREEN proof:* `pytest tests/tools/test_mcp_trust_gating.py -k "TestMCPApprovalPersistence"` -> 4 passed in 2.47s.
  - *Observed Full Suite:* `pytest tests/tools/test_mcp_trust_gating.py` -> 22 passed in 4.76s.

- [x] **Task 5: Slash Command Management (`/approvals`)**
  - Updated `_handle_approvals_command` in `gateway/slash_commands.py` to support:
    - `/approvals mcp`: lists permanent and active session MCP approvals.
    - `/approvals revoke mcp <server:tool>`: revokes authorization from memory and disk.
  - *Observed GREEN proof:* `pytest tests/gateway/test_discord_slash_commands.py` -> 14 passed in 19.00s.

- [x] **Task 6: Roshi Profile Verification (Discord & Twenty CRM)**
  - Confirmed isolation via `test_profile_isolation_roshi_and_ragnar`: approvals in Roshi write strictly to Roshi's `config.yaml` (`home_key`) and never leak to default/Ragnar profile.

- [ ] **Task 7: Retiro del Workaround en Ragnar & Validación Operativa**
  - Pending user operational confirmation before reverting Ragnar's temporary `trust: full` to `trust: untrusted`.

