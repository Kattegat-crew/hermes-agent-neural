# F3 — Durable checkpoint (capability-claim-guard)

Written 2026-11-03 after the guard suite went green and the regression baseline ran.
Durable record: identity, diff scope, exact commands, real results, open gaps.

## 1. Identity

| | |
|---|---|
| Worktree | `/opt/hermes-agent-data/fleet/worktrees/hermes-agent/capability-claim-guard` |
| Base (main-lineage) | `cd397afc64` — `fix(agent): byte-exact prose excision + deterministic JSON repair for streaming-cut params` |
| Feature commit | `5f8f80f86c` — `feat(agent): capability claim guard for pre-output, interim and final text` |
| Lint-fix commit | `17fa30b279` — `refactor(agent): keep guard seams off the facade size ratchet` |
| Diff vs base | 23 files, +3456 / −14 |
| Push | none (no remote push without explicit human approval) |

## 2. What lands

New module `agent/capability_claim_guard.py` (938 lines) + 8 test files (1535 lines).
Seams in 8 existing units:

| File | Change |
|---|---|
| `agent/stream_delivery.py` | S1 holdback window, `_ccg_stream_gate`, `_ccg_stream_flush`, `_ccg_route_suppressed_text`, per-attempt gate state |
| `agent/chat_completion_helpers.py` | flush on response completion; suppressed-text route delegates to the mixin |
| `agent/turn_stop_gates.py` | pre-verify / on-stop repair nudge (S3) + repair budget reset |
| `agent/turn_finalizer.py` | fail-open `_ccg_seal` seam on the output transform |
| `agent/tool_executor.py` | evidence capture from the turn's real tool surface |
| `agent/agent_runtime_helpers.py` | repair rows are provisional candidates (superseded, not unioned) |
| `agent/conversation_loop.py` | per-turn reset of `_ccg_repairs` / `_ccg_evidence` |
| `hermes_cli/config_defaults.py` | `capability_claim_guard: {enabled: false, holdback_chars: 200, repair_limit: 2}` |

Invariants pinned by tests: detection is evidence-bound (session registry, not the wire
payload); publication stays monotonic (holdback + `release + keep` scan, never a retraction);
S2 gates commentary before it reaches a surface; S3 terminates with a truthful seal when the
repair budget is spent; guard state is profile-scoped; fail-open everywhere; default OFF is
byte-identical runtime.

## 3. Test commands and real results

Runner: `scripts/run_tests.sh` (never bare pytest), test venv
`/opt/hermes-agent-data/installs/7d924379cbfe12f1/test-environment/gen-be4a28b95cff45b9b8ba73b3e447b1ed/venv/bin/python`,
`HERMES_RUNTIME_DIR=/opt/hermes-agent-data/tools`, `env -u PYTHONPATH -u __HERMES_ACTIVATED -u VIRTUAL_ENV`.

Guard suite (8 files):

```
scripts/run_tests.sh tests/agent/test_capability_claim_guard_{stream,interim,final,findings,config,surfaces,evidence,detector}.py -q
=== Summary: 8 files, 120 tests passed, 0 failed (100% complete) in 10.4s (4 workers) ===
```

Focused regression on the touched surfaces (21 files, 3 batches):

```
batch A  codex_stream_supersession, chat_completion_helpers_provider_sort, turn_retry_state,
         kanban_stop, verification_stop, verification_stop_caching,
         verification_continuation_budget, verification_evidence
         -> 8 files, 66 passed, 0 failed (17.3s)

batch B  turn_finalizer_{cleanup_guard,final_response_persistence,interrupt_alternation,
         iteration_limit_exit}, conversation_loop_interpreter_shutdown,
         send_path_history_isolation, prompt_caching, subagent_lifecycle
         -> 8 files, 101 passed, 0 failed (7.5s)

batch C  partial_stream_continuation_prompt, nonstream_wait_notice,
         anthropic_stream_fallbacks, direct_contexts_stream_inline, aux_progress_streaming
         -> 5 files, 84 passed, 0 failed (20.7s)
```

The full Hermes suite was deliberately not run (scope: touched surfaces + guard corpus).

### RED baseline (proof the tests bind the seams)

Base tree `cd397afc64` extracted without any `_ccg*` seam, guard module and tests copied in:

```
cd <scratch>/ccg-red.wGO7g4 && scripts/run_tests.sh <same 8 guard files> -q
=== Summary: 8 files, 85 tests passed, 35 failed (100% complete) in 35.3s ===
  6 files with test failures (35 tests failed)
    test_capability_claim_guard_stream.py     14
    test_capability_claim_guard_surfaces.py    8
    test_capability_claim_guard_interim.py     5
    test_capability_claim_guard_final.py       4
    test_capability_claim_guard_findings.py    2
    test_capability_claim_guard_evidence.py    2
```

`detector` and `config` pass on the base (pure functions, no seam needed) — the 35 failures
are exactly the seam-dependent tests, so they cannot pass by accident on a tree without the
integration. Log: `cache/scratch/ccg-red-run.log`.

## 4. Lint A/B (touched files only)

```
ruff check <17 touched .py files>            -> All checks passed!  (exit 0)
python scripts/check --only health --base cd397afc64
   -> code health: 17 files vs cd397afc64c9: 0 blocking, 0 advisory (7.5s)  (exit 0)
```

Two reviewed waivers, both justified in the diff:

- `agent/turn_finalizer.py:491 BLE001` — deliberate fail-open boundary: a guard bug must never
  break a turn; the handler logs with `logger.exception` and returns the raw text.
- `hermes_cli/config_defaults.py:1 FILE_LINES` — pure-data defaults table; a new profile-scoped
  default has no sibling module to move into, so the entry is kept to docs+data.

Three ratchet findings surfaced by the first pass were fixed in the code, not waived:
`agent_runtime_helpers.py` and `chat_completion_helpers.py` growth was offset to their main-line
line counts, and `_ccg_seal` moved above its call site (F821).

## 5. Open points for the reviewer

1. **Review surfaces requested by the operator:** pre-output (S3 nudge ordering vs. the
   verification stop gate), commentary/interim (S2 on codex item streams), codex
   (`_is_codex_interim` rows are provisional candidates), recovery/retry (`_ccg_stream_flush`
   supersession: a retry must not publish the replaced attempt's held tail, #65991), profile
   (gate state and config are per owning profile, never ambient).
2. **No self-declared PASS.** 120 unit tests plus 251 regression tests and a red baseline are
   evidence, not a verdict.
3. Residual, out of scope by design: no E2E run through a live gateway adapter (unit-level
   matrix only); `holdback_chars` bounds only the live stream — a denial that starts after the
   window closes is caught by S2/S3, not by S1.
