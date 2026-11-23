# Tasks: Single-Row Save for Session Metadata

* **Status**: In progress
* **Spec**: `01-spec.md` · **Design**: `02-design.md`

| # | Task | Skill | Depends | Verification |
|---|---|---|---|---|
| T0 | Pre-flight: branch, clean tree, baseline counts (28,823 routing rows; 755 new/day) | `hermes-agent` | — | ✅ `git status` limpio en `prod-stable` |
| T1 | Prune ended sessions + orphaned routing rows (with backup) — hygiene, not the fix | `hermes-cron-ops` | T0 | ✅ sesiones 7.774→305; rutas 29.643→334; backup 41.8 MB + 49.8 MB |
| T2 | Write failing test: `set_session_metadata` must use `_save_entry`, never `_save` | `python-testing-patterns` | T0 | ✅ RED: `test_set_session_metadata_never_rewrites_full_index` |
| T3 | Implement `_update_entry(..., fast=False)` branch to `_save_entry` outside the lock | `python-patterns` | T2 | ✅ GREEN |
| T4 | `set_session_metadata` passes `fast=True` | `python-patterns` | T3 | ✅ GREEN (20 passed) |
| T5 | Regression: session suite + fast-path suite | `python-testing-patterns` | T4 | ✅ 65 passed (test_session + time-persistence + mutation-retirement) |
| T6 | Adversarial review gate, engine opencode, model Hy4 | `adversarial-review-gate` | T5 | ✅ **PASA** (r5: 0 critical / 0 high / 0 medium, 116 s) — r1 invalidada · r2 lost-update → corregido · r3 deadlock fallback → corregido · r4 2 medium doc/AC2 → corregidos |
| T7 | Conventional commit (no AI attribution, no push) | `code-review-and-quality` | T6 | ✅ `2ee98139a6` en `prod-stable`, árbol limpio, sin push |
| T8 | Activate the new code: gateway restart so the in-memory routing map reloads pruned state | `hermes-gateway-p0-playbook` | T7 | ⏳ **Admin action required**: the agent cannot restart the gateway (documented block, PROJECT_MEMORY 2026-11-23 §WhatsApp). Valid path: `/restart` in Discord, or shell outside the gateway. |

## Acceptance mapping

- T2/T4 → AC2, AC3 (durability + clock)
- T3 → AC1, AC5
- T5 → AC4 (JSON-only fallback covered by existing suite)
- T8 → operational proof: no new `Fatal discord adapter error`
