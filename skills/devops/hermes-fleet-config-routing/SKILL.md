---
name: hermes-fleet-config-routing
description: Use when editing Hermes fleet configs or model routing.
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: internal
metadata:
  hermes:
    tags: [config, routing, compression, cfgctl, fleet]
    related_skills: [hermes-agent]
---

# Fleet Config Routing (Hermes DEV)

## When to Use

- Changing per-profile Hermes configs: model routing, compression thresholds,
  aux timeouts, or applying config changes fleet-wide.
- Diagnosing why compaction did not fire or aborted ("Compression aborted").

## Tooling

- Policy tool lives in the ops worktree `/opt/hermes-agent-data/worktrees/fleet-routing`
  (`scripts/fleet_model_routing.py` + `scripts/fleet_model_routing.policy.yaml`),
  committed on branch `feature/fleet-model-routing`. Subcommands: `plan | render | apply | verify`.
  `apply` renders a candidate per profile and hands each one to the sanctioned applier
  `scripts/cfgctl.py` (never writes configs directly).
- cfgctl: `CFGCTL_CONFIG=<target> python3.12 /opt/hermes-agent-data/scripts/cfgctl.py apply <candidate>`
  (also `snapshot | restore | validate`). Every apply auto-backups the previous file as
  `<config>.bak-cfgctl-prev-<ts>` and logs sha before/after to `ops/cfg/cfgctl.log`.

## Guard for config mutations

- Direct edits to `/opt/hermes-agent-data/config.yaml` or any profile config are blocked by
  `hooks/guard_config_model_mutation.py` (matches cp/mv/tee/redirect on config paths).
- Sanctioned path: anything invoked through `cfgctl.py` bypasses the guard by design.
- Escape hatch for one-off exceptions: write a window to
  `/opt/data/state/config_guard_override.json` — a JSON **list** of
  `{"objetivo": "<substring of the command/code>", "expira": "YYYY-MM-DDTHH:MM:SS"}` (local time).
  Requires `objetivo` inside the command AND a cfgctl-based applier.

## Model routing policy

- Per-profile `model.default` is pinned by profile with provider + `base_url`; subagent routing
  via `delegation.model`/`delegation.provider` is static per profile — per-task pinning exists
  only for kanban workers (`kanban_create` accepts `model` + `provider`).
- Rollout order: flash-class profiles → qwen profiles → primary; one profile at a time with
  post-apply verification.

## Compression tuning (verified 2026-11-10)

- 11 of 13 fleet profiles had NO `compression.threshold_tokens`, inheriting
  `compression.threshold: 0.75` — i.e. compaction only fired at 75 % of a 1 M window
  (750 k tokens carried per turn). Set an explicit `threshold_tokens` everywhere.
- Rule applied: `threshold = max(80k, min(200k, 0.45 × model context_length))`.
- A real compaction run took ~190 s (`aux_call_duration_ms: 188929` for a 43.6 k-token
  summary); with `auxiliary.compression.timeout` at 120 s any latency spike = aborted run.
  Raised to 300 s fleet-wide.
- Telemetry for diagnosing: `effective_threshold`, `aux_call_duration_ms`,
  `tokens_reclaimed`, `current_estimated_tokens` in session logs.
- "Compression aborted … No messages were dropped" comes from
  `agent/conversation_compression.py:3471` when `_last_compress_aborted` is set; the
  recorded failure class is `commit_fence_cancelled` (session interrupted during the
  ~190 s summary window). Lower thresholds reduce exposure but the fence-cancel is
  gateway code, not config.
- New sessions pick up config changes immediately; live sessions keep old values until
  renewed. Force via gateway restart (drain) only with explicit human approval.

## cfgctl schema pitfall

- cfgctl rejects a candidate whose `plugins.enabled`/`plugins.disabled` is `null`
  ("plugins.disabled no es lista"), even if the existing file has the same null.
  Several profile configs carried `plugins.disabled: null`. The policy tool normalizes
  null → `[]` (same semantics) before rendering. Check for this before blaming the tool.

## Verification loop

- `python3.12 -m unittest discover -s scripts/tests` (pure-function tests, 22 cases on
  tmpdir fixtures).
- After apply: `fleet_model_routing.py verify` must print `VERIFY OK: flota alineada`,
  plus a direct readback of each config (threshold/protect/aux/model) and
  `hermes config get compression.threshold_tokens`.
- Keep the applied-state note in `ops/routing/<date>-<topic>.md` with values, why,
  expected effect and rollback lines.
