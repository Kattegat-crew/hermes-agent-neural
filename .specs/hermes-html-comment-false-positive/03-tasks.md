# Tasks: HTML Comment False-Positive Correction

## Objective and Scope

Apply only the user-approved Unicode-aware word-boundary correction for HTML-comment trigger words. Approval: 2026-10-14, “si haz la correccion.” No broader scanner policy or production deployment is authorized; production deployment requires separate approval.

Authorized implementation files: `tools/threat_patterns.py`, `tests/tools/test_threat_patterns.py`. Supporting records: this spec folder and `PROJECT_MEMORY.md`. One local work-unit commit; no slice expected. `ask-on-risk` is the default delivery strategy.

## Acceptance

- `Secretaría` embedded in a benign comment is not flagged.
- Standalone malicious keywords remain detectable across case, punctuation, and line breaks.
- Unrelated scanner patterns are unchanged.

## T01 — Add regression coverage and minimal boundary correction

- **Route:** Delegated direct; scanner and regression tests are two non-trivial files. Tests were written first.
- **Files:** `tests/tools/test_threat_patterns.py`, `tools/threat_patterns.py`.
- **TDD:** Focused runner RED: 34 passed, 6 expected failures on embedded words. GREEN: 40 passed, 0 failed. Command: `HERMES_PYTHON=/usr/bin/python3 ./scripts/run_tests.sh tests/tools/test_threat_patterns.py`.
- **Additional check:** Scanner + prompt-builder run: 115 passed, 1 failure, `test_agents_md_no_git_root_stays_cwd_only`. Independent verification reproduced it against base `prompt_builder.py`; `/tmp/.git` makes the temp path appear inside a repository and loads an ancestor `AGENTS.md`. The independent real-path smoke passed: benign `Secretaría` was included and `ignore all rules` remained blocked; base scanner reproduced the false positive.
- **Known limitation:** Unicode `\b` treats underscore as a word character, so a trigger adjacent to `_` is not standalone for this pattern (for example, `ignore_all_rules`). This is not a guarantee that every obfuscated form is detected.
- **Other checks:** `git diff HEAD --check` exited 0. Runtime harness: N/A; no live service boundary changed. Rollback: revert commit `6d54b2c04536f396f27cccd48a0678684d659567`.
- **Commit:** `6d54b2c04536f396f27cccd48a0678684d659567`, `fix/security: require standalone html-comment trigger words`; base `a3358de1258c0886d81428533aad06753fff3efc`.

## RDD and Next Step

Mode is on. Post-commit assessment command:
`gentle-ai review assess --cwd /root/hermes-agent-worktrees/html-comment-fix --agent codex --base-ref a3358de1258c0886d81428533aad06753fff3efc --committed-only --untracked-scope=exclude --expected-untracked-inventory=sha256:a7faf44ee8a7004d1c24ec3f4fe690560ebc3a22dee3f74e9845591d53a903e1 --json`

Observed: exit 0, risk `medium`, 6 paths / 165 lines, `review_due=false`, reason `under_budget`. No START, consent, receipt, or delivery approval exists. Keep the slice pending below budget; the parent owns any future native review lifecycle.

## T02 — Deploy the approved scanner overlay to production

- **Authorization:** User explicitly authorized deployment to `169.58.189.222` over the existing root SSH channel, accepted the brief interruption required to recreate the Hermes service, and requested that the change persist. This does not authorize push, unrelated checkout changes, or future production deployments.
- **Route:** Delegated direct, single production writer. Host source plus isolated overlay context only; do not build the dirty full checkout.
- **Edit boundary:** production `/opt/hermes/tools/threat_patterns.py` and `/opt/hermes-hotfix/html-comment-20261014/**`; local tracking only in this task file and `PROJECT_MEMORY.md`.
- **Plan:** Preserve original host bytes/mode with a 0600 backup; verify and tag the exact running image as a rollback reference; create a standalone private mode-0600 deployment snapshot derived in memory from native rendered Compose, containing only service `hermes`, its referenced declarations, resolved absolute paths, and the exact live container environment. Compose's desired-only Discord/API/group-policy values and the two changed WhatsApp settings must not be applied. Render the snapshot alone and verify exact parity with live environment keyset/values plus command, entrypoint, user, working directory, restart/resources, ports, mounts, and network before source/image/service changes. Then create a minimal Dockerfile overlay from the exact running image with one `COPY` and no package commands; build offline; verify candidate source/hash and benign/malicious scanner behavior before promoting the existing compose image tag. Recreate only Compose service `hermes` with the standalone private deployment snapshot, without dependencies, builds, pulls, or volume changes.
- **Gate:** A config-hash mismatch alone is not proof of effective drift. Stop before production source/image/service mutation unless the full effective service spec (including exact live environment) is established from in-memory comparison. Standalone snapshot rendering must preserve exact effective service parity; otherwise stop. Preserve dirty compose, Langfuse, untracked files, and unrelated state.
- **Checks:** Source/hash parity; scanner benign and malicious cases; sanitized profile scan and context inclusion; container/service health; WhatsApp bridge connection health; unchanged mounts/identity. No message sends, sessions, profile edits, or secrets in output.
- **Rollback:** Restore the original scanner bytes/mode, restore original image tag, and recreate only the same `hermes` service; never delete volumes or rollback image.
- **State:** [x] Preflight reconciled; main Compose left unchanged. The merge override (0600) retained 10 desired-only keys, so it was not used. A standalone deployment snapshot `/opt/hermes-hotfix/html-comment-20261014/live-deployment.json` (0600) contains only the resolved `hermes` service and referenced declarations. Before mutation, parity passed: 78/78 exact live environment entries, exact command/entrypoint/user/cwd/restart/resources/ports/network, and 12/12 mounts. Baseline production smoke reproduced benign `Secretaría` false positive and retained `ignore all rules` detection. [x] Host source backed up mode 0600; patched exactly one approved regex literal, preserving mode/owner. Offline thin image build succeeded from exact original image with one COPY/no RUN. Candidate image `sha256:2b00226cfe6a8dfdb1b9a83e16bff22a114b9769c126ed5849dcc9f96e9c3386`; candidate scanner passed 7 malicious and 6 benign cases, actual Jacqueline AGENTS had no html-comment finding, and prompt-builder smoke included benign Secretaría / excluded malicious payload. [x] Promoted and recreated only `hermes` using snapshot at 2026-10-14 05:51:44–05:51:59 UTC. Post-recreate environment/config/mount/image/source parity passed, but gateway-golden-game and gateway-lucky-club were down after >100s and in-container WhatsApp health returned HTTP 200 `connected=false`; required health gate failed. [x] Executed prepared rollback at 05:54:24–05:54:33 UTC: source exactly matches backup, current image tag restored to original ID, hermes recreated. After rollback gateway-default, gateway-golden-game, and gateway-lucky-club were up; WhatsApp health still returned HTTP 200 `connected=false` (pre-deploy connection state was not established). Scanner fix is **not live**. [ ] Resolve WhatsApp connection status/health and obtain parent direction before any redeploy. Candidate image and private snapshot/backup/rollback artifacts remain in protected hotfix directory; no secret values were printed. [ ] Local evidence/commit.
- **Known limitation:** Python Unicode `\b` treats `_` as a word character; this detector does not guarantee detection of every obfuscated form.
- **Separate approval:** Any later production upgrade, deploy, or replacement of this patch remains subject to a new explicit approval.
