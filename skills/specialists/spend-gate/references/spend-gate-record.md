# Spend gate record (minimal schema)

```json
{
  "purpose": "one poster run rev 04",
  "approved_by": "human name + channel + date",
  "recorded_by": "agent (approved_by names the human, not the writer)",
  "evidence_literal": "exact user quote authorizing cap and runs",
  "cap_usd": 0.25,
  "max_runs": 1,
  "runs_used": 0,
  "expires_at": "<=24h from approval>",
  "state": "ABIERTO | CONSUMIDO"
}
```

Manifest fields per run: `request_id`, `estimated_usd`, `actual_usd` (`null` when unreported), `provider`, `params`, `refs_sha256`, `gate_state_after_run`.
