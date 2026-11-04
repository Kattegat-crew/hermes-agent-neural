# Integration of the reviewed guard onto live HEAD — 2026-11-03

Card `t_88df1ba6` (Fase: integración de fuente + prueba, **sin activación**).
Worktree: `/opt/hermes-agent-data/fleet/worktrees/hermes-agent/capability-claim-guard-ragnar`
Branch: `feat/capability-claim-guard-ragnar` (new; the reviewed branch `feat/capability-claim-guard`
at `ce34c19c5c` is untouched, no rebase, no rewrite).

## 1. Base and lineage

| | |
|---|---|
| Live root | `/opt/hermes-agent`, branch `feat/ephemeral-progress-heartbeat-cleanup`, HEAD `9daf7b8fae2d84afae81033cf37403a04b9f35a5` |
| Integration base | `9daf7b8fae` (same commit — the new branch was created from live HEAD) |
| Reviewed base | `cd397afc64` (guard branch merge-base) |
| Divergence absorbed | 12 root commits since `cd397afc64` (config shield, PM retry, KV-cache refactor, memory prefetch, handoff scripts) |

Only **one** file is touched by both lineages: `agent/agent_runtime_helpers.py`.
The auto-merge kept both sides in disjoint regions and both were read back:

- root's `ebf9ec3db0` removal of the runtime execution guardrail block in `invoke_tool` — absent, as in root HEAD;
- the guard's `capability_claim_repair` provisional-candidate handling in `_merge_consecutive_assistants` (`:552-566`).

Everything else is either a new file (guard module, 8 test files, `.specs/`) or a file root did not touch.

## 2. Dirty snapshot of the original root (untouched)

`git status --porcelain` of `/opt/hermes-agent` at the start of this run: 48 entries
(17 modified — 16 `skills/*/SKILL.md` plus `scripts/backup_audit.py` — and 31 untracked: skill
references, `docs/`, `.specs/hermes-update-controller/`, two `scripts/*.bak` backups), sha256 of
the listing `603fac941b79c668e885a5a49e12a1d682e2971852147d41e5a0bfcf8c86e71b`
(committed alongside as `integration/root-dirty-snapshot-20261103.txt`). None of those paths is in
the guard diff.

During this run another actor added 3 more foreign `skills/` entries (`diff` = 3 lines, all under
`skills/specialists/`); root HEAD and branch did not move. No stash, reset, checkout, pull or
`git add` was run against the root tree.

## 3. Cherry-picks (authorship and messages preserved, no AI co-author)

| Original | Integrated | Message | Author |
|---|---|---|---|
| `5f8f80f86c` | `cba1f10dbe` | feat(agent): capability claim guard for pre-output, interim and final text | Ragnar-NexaLabs |
| `17fa30b279` | `a8106d317b` | refactor(agent): keep guard seams off the facade size ratchet | Ragnar-NexaLabs |
| `0a619a2544` | `856c93d66a` | docs(spec): F3 durable checkpoint for capability claim guard | Ragnar-NexaLabs |
| `ce34c19c5c` | `8ccc035c21` | fix(agent): close capability guard stream and detector gaps | Hermes gateway |

No conflict markers were produced; `git cherry-pick` reported auto-merge only on
`agent/agent_runtime_helpers.py`. The reviewed branch was 27 files, +4206 / −14 against its own base;
this branch is 30 files, +4603 / −14 against `9daf7b8fae` (the 27 plus these three documents), and no
root feature is dropped. Round 2 (§8) added the isolation probe, two code commits and one doc commit
(31 files, +4885 / −14); round 3 (§9) is documentation-only, so the delivered diffstat is **31 files,
+4928 / −14**.

## 4. Invariants checked by reading, not by assumption

1. **No intent/keyword classifier reintroduced.** `grep` for `classify_turn_intent`,
   `_GREETING_WORDS`, `_ACTION_DIRECTIVES`, `_CASUAL_INQUIRY_PATTERN` finds only the root test
   `tests/agent/test_turn_intent_triage.py:13` asserting the attribute is gone. The guard's regexes
   read **model output** (claim detection), not user messages.
2. **Roles / prompt / cache preserved.** The only loop change is `wire_turn(agent, s.turn_id)` in
   `conversation_loop.py` (per-turn state reset; no message mutation). `tests/agent/test_prompt_caching.py`
   and the turn-shape suites are green.
3. **Root's newer work not deleted.** Config shield (`agent/tool_guardrails.py`,
   `scripts/hooks/guard_config_model_mutation.py`) is untouched by the diff; PM retry
   (`pm/environments.py`), memory prefetch (`tools/memory_tool*.py`) and the handoff scripts are
   not in the diff at all.
4. **Default OFF.** `hermes_cli/config_defaults.py` adds
   `agent.capability_claim_guard: {enabled: false, holdback_chars: 200, repair_limit: 2}`.
   Real default home readback with the integrated code:
   `hermes config get agent.capability_claim_guard` → `enabled: false` / `holdback_chars: 200` /
   `repair_limit: 2` (`/opt/hermes-agent-data/config.yaml` unchanged, sha256 `8dd245e9…`).

## 5. Test evidence (this run, canonical runner)

Runner: `scripts/run_tests.sh`; interpreter via `HERMES_PYTHON` =
`/opt/hermes-agent-data/installs/7d924379cbfe12f1/test-environment/gen-be4a28b95cff45b9b8ba73b3e447b1ed/venv/bin/python`
with `env -u PYTHONPATH -u __HERMES_ACTIVATED -u VIRTUAL_ENV` (documented test env, no root-owned stamps
created — run as `hermes`).

```
guard suite (8 files)                    146 passed, 0 failed   (20.3s)
regression A (root-changed semantics)     84 passed, 0 failed   ( 9.5s)
  turn_intent_triage, guard_config_model_mutation, tool_guardrails, prompt_caching,
  turn_retry_state, codex_stream_supersession, chat_completion_helpers_provider_sort,
  conversation_loop_interpreter_shutdown
regression B (guard seams)                98 passed, 0 failed
  turn_finalizer_{cleanup_guard,final_response_persistence,interrupt_alternation,
  iteration_limit_exit}, tool_executor_checkpoint_paths, verification_stop,
  verification_stop_caching, verification_continuation_budget, verification_evidence, kanban_stop
regression C (stream/history/profile)     160 passed, 0 failed (11 files)
  send_path_history_isolation, subagent_lifecycle, partial_stream_continuation_prompt,
  nonstream_wait_notice, anthropic_stream_fallbacks, direct_contexts_stream_inline,
  aux_progress_streaming, stream_single_writer_guard, profile_home_override_precedence,
  secret_scope, config_set_coercion
TOTAL                                    488 passed, 0 failed
```

### RED baseline on the new base (proof the tests bind the seams)

Base tree `9daf7b8fae` extracted with `git archive` (scratch, no `.git`), guard module and the 8
test files copied in unchanged:

```
=== Summary: 8 files, 102 passed, 44 failed (100% complete) ===
  test_capability_claim_guard_stream.py   22
  test_capability_claim_guard_surfaces.py  8
  test_capability_claim_guard_interim.py   5
  test_capability_claim_guard_final.py     5
  test_capability_claim_guard_findings.py  2
  test_capability_claim_guard_evidence.py  2
```

`detector` and `config` pass on the base (pure functions); the 44 failures are exactly the
seam-dependent tests, so they cannot pass without the integration.

### Lint / health

```
ruff check <9 touched .py files + 8 guard test files>      -> All checks passed!  (exit 0)
python scripts/check --only health --base 9daf7b8fae       -> 20 files vs 9daf7b8fae2d:
   0 blocking, 0 advisory (15.2s)  (exit 0)
allowed-by-comment (unchanged from review):
   agent/turn_finalizer.py:491 BLE001  — deliberate fail-open boundary
   hermes_cli/config_defaults.py:1 FILE_LINES — pure-data defaults table
```

### Real-loop canary (simulated provider, loopback only)

`canary_v2.py` (reviewed artifact, `sha256 9771e44a…`) re-run with `sys.path`/cwd pointed at this
worktree: **31/31 PASS** (`canary_results_v2.json` in the scratch run dir). Covers incident replay,
interim/codex suppression, quoted/code-fence exemptions, ES/EN corpus drift 0/11, bounded repair,
seal-not-streamed, deferred `tool_search` surface, resume without stale taint, provider-error vs
capability-absence, per-home isolation, holdback bound (200 B), prefix stability (no retraction),
per-delta overhead (p50 0.112 ms / p95 0.215 ms over 1110 deltas). No real model, no paid API, no
gateway adapter, no messaging channel.

### Flag flip proven with the native CLI (throwaway home, not the real one)

```
hermes config set agent.capability_claim_guard.enabled true   -> ✓ Set … = True
probe is_enabled(<agent con home desechable>)                 -> enabled: True
hermes config unset agent.capability_claim_guard.enabled      -> ✓ Unset …
probe is_enabled(<agent con home desechable>)                 -> enabled: False (default)
```

Desde el fix de §8, `is_enabled()` **sin perfil propietario es False por diseño** (fail-closed): el
probe tiene que pasar un agente con `_session_db` apuntando a un home, como hace
`probes/ccg_probe_profile_scope.py`.

No YAML was hand-edited; the writer is the CLI's atomic config writer.

## 6. Deliverable state

- Branch `feat/capability-claim-guard-ragnar`, clean worktree, no push (credentials still
  read-only; no other identity was attempted).
- Root `/opt/hermes-agent`: HEAD `9daf7b8fae`, branch unchanged, only the foreign skills/docs
  drift described in §2.
- No activation, no restart, no deploy in this phase. The operational plan is
  `09-activation-plan-ragnar.md`, to be executed by the next authorised card after review PASS.

## 7. Rollback of this phase

Nothing deployed, so rollback is local: `git worktree remove` the integration worktree (branch
keeps its commits) or `git branch -D feat/capability-claim-guard-ragnar`. The reviewed branch
`feat/capability-claim-guard` at `ce34c19c5c` and the root tree are untouched.

The **runtime rollback path was dry-run for real**, not just written down: a throwaway detached
worktree at `9daf` fast-forwarded to the integration head (`338d5dfce6`) and then
`git revert --no-edit` over the five commits left `git diff 9daf..HEAD` empty and the tree clean
(`TREE_IDENTICAL=YES`, `DIRTY=0`); the worktree was removed afterwards. Repeated after round 2
(`ca2f01b5d6`, nine commits) and **again at the delivered head** using the range form
`git revert --no-edit 9daf7b8fae..HEAD`: clean reverts, `HEAD^{tree}` == `9daf^{tree}`
(`61ee4dd8c2`), `git diff --stat 9daf..HEAD` = 0 lines, `git status --porcelain` = 0 entries,
worktree removed. An enumerated hash list was rejected: reverting the documentation commits of this
branch out of order conflicts on `08`/`09` (`CONFLICT (content)`, repo left mid-revert), which is why
the plan uses the range. Evidence and the rollback table live in `09-activation-plan-ragnar.md` §4.

## 8. Round 2 — review findings closed (2026-11-03)

Two blocking findings and two cosmetic notes from the review of `78ed036423`; all four are closed here.

### B1 — the config gate answered for the ambient profile (fixed, fail-closed)

`_guard_options()` read `load_config_readonly()` whenever the agent had no session DB. That is a live
path, not a hypothetical: `agent/background_review.py:920` sets `_session_db = None` on the review fork
(`_persist_disabled = True`) and `:1102` still runs `run_conversation` → `wire_turn`. In a multiplexed
host (`hermes serve` / dashboard, whose `HERMES_HOME` is the launch profile) the fork therefore
inherited the **launch profile's** flag — the exact cross-profile leak the gate exists to prevent.

Fix: `_load_config_for_home()` lost its `None`/ambient branch and `_guard_options()` returns the
disabled fallback when no owning home resolves. The guard now answers only for the profile that owns
the session; nothing else can turn it on.

Test-first, on the pre-fix tree (`tests/agent/test_capability_claim_guard_config.py`):

```
FAILED test_is_enabled_without_owning_home_fails_closed_never_ambient
    assert True is False                      # ambient ENABLED leaked in
FAILED test_wire_turn_without_owning_home_captures_no_evidence
    assert <evidence> is None
=== Summary: 1 files, 2 failed, 7 passed ===
```

After the fix: `1 files, 9 tests passed, 0 failed`. The pre-existing test that blessed the ambient
fallback (`test_wire_turn_without_agent_home_uses_the_bound_scope`) was replaced — it encoded the bug.
`tests/agent/test_capability_claim_guard_evidence.py` gained an owning home in its three flag tests
(`_session_agent(home)` → `_session_db`), because a bare agent is now OFF by contract.

Runtime probe (`.specs/capability-claim-guard/probes/ccg_probe_profile_scope.py`, 4 throwaway homes,
never the real profile):

```
old code (ce34c19c5c):  FAIL fork under ambient ENABLED -> is_enabled: got=True want=False
                        FAIL fork under ambient ENABLED -> wire_turn evidence: got={...} want=None
                        4/6 expectations hold                       (exit 1)
fixed (93697dbb6e):     6/6 expectations hold                      (exit 0)
```

Suite results on the fixed tree: guard files `8 files, 147 passed`; streaming/turn/regression slice
`110 files, 997 passed, 6 skipped`; `scripts/check --only health --base 9daf7b8fae` → 21 files,
0 blocking, 0 advisory.

### B2 — the activation plan used a hand-rolled release (replanned)

§3-E of `09-activation-plan-ragnar.md` now uses the operational mechanism that already exists,
`releases/dashboard/bin/promote-release <sha>`, and documents what that script does and does not do.
The old steps (`git worktree add` inside `releases/`, `npm ci`+`npm run build`, hand-written
`ensure_install_launchers`, hand-made `ln -sfn`) are gone. Two gaps in the script are compensated
explicitly: it prints `/api/health`'s `commit` but never compares it to the requested SHA (new step
**E2-bis** asserts equality and rolls back on mismatch), and it needs root privileges
(`chown -R root:root`, `systemctl restart`) which this host's `sudo -n` does not grant — so the
executing card must hold root or stop as `needs_input`. Order changed accordingly: merge the code first
(E1), because promote-release resolves the SHA in `/opt/hermes-agent` and `clone --shared`s from it.

### N1 / N2 — cosmetic

`+4581` in §3 was wrong; the measured diff was `+4603` (now `+4928` after rounds 2–3 — see the
diffstat in §3 of this document). `agent/stream_delivery.py` had two consecutive `if not text: return`; the
first was dead (`_ccg_stream_gate` returns `""` on empty input and the text unchanged when disabled), so
it was removed and the remaining check documented as the single emptiness gate.

## 9. Round 3 — rollback recipe corrected at the delivered head (doc only)

The round-2 review of `ca2f01b5d6` found one blocking defect and one nit, both confined to
`09-activation-plan-ragnar.md`; no code, test or probe changed.

- **Blocking — §4 enumerated a frozen revert list.** The list was frozen at `93697dbb6e` (eight
  commits) while the head shipped was `ca2f01b5d6`; executing it verbatim produced
  `CONFLICT (content)` on `08`/`09` and left the repo mid-revert (`UU ×2`), because the later
  documentation commits rewrite those same two files. §4 now reverts the **range**
  (`git revert --no-edit 9daf7b8fae..HEAD`) and states the acceptance invariant explicitly: the
  resulting `HEAD^{tree}` must equal `9daf^{tree}` (`61ee4dd8c2`) with a clean status — the revert
  commit SHA is not the invariant, it depends on committer and date.
- **Nit — §3-V-2 file split.** "31 files (17 code, 8 tests, 14 spec)" summed to 39. The measured split
  is **9 code** (8 under `agent/` plus `hermes_cli/config_defaults.py`), 8 tests, 14 spec = 31.

Dry-run re-executed in a throwaway detached worktree at `ca2f01b5d6`: 9 reverts clean, `REVERT_HEAD`
`6203d2d111`, `HEAD^{tree}` == `9daf^{tree}` == `61ee4dd8c2`, `git diff --stat 9daf..HEAD` = 0 lines,
`git status --porcelain` = 0 entries, worktree removed; the same range command was re-run at the
delivered head before review.
