# Technical Design: Local Skills Catalog Hygiene, Discovery Exclusions & Memory Heading Fix

* **Associated Spec**: [01-spec.md](./01-spec.md)
* **Status**: Approved
* **Architect**: Antigravity (`agy`)
* **Target Revision**: `6f1af4d1a7` (`prod-stable`)

---

## 1. On-Disk Skills Catalog Hygiene (`/opt/hermes-agent-data/skills/`)

1. **Permanent Backup Deletion (G1)**:
   - Remove `/opt/hermes-agent-data/skills/.backup_pre_consolidation` completely (`rm -rf`).
2. **Duplicate & Broken-Rollback Reconciliation (G2)**:
   - Delete all 6 `*.rollback-broken` directories (`autonomous-ai-agents/hermes-agent.rollback-broken`, `core/hermes-fleet-runtime.rollback-broken`, `hermes-plugin-e2e-verification.rollback-broken`, `core/mapa-de-carpetas.rollback-broken`, `specialists/hermes-internal/hermes-vps-update.rollback-broken`, `specialists/marketing-ads/meta-ads-discord-reporter.rollback-broken`).
   - Reconcile `hyperframes*`: remove stale/duplicate `creative/hyperframes` (`15,730 B` old v1.0.0), `creative/hyperframes-animation`, and `creative/hyperframes-audio` so the canonical symlinks at `/opt/hermes-agent-data/skills/hyperframes* -> ../../../root/.claude/skills/hyperframes*` are the sole active source.
   - Reconcile the 9 cross-category duplicates keeping the richer/canonical copy:
     - `devops-infrastructure`: preserve all 73 `references/*.md` in `core/devops-infrastructure/`, merge `devops/devops-infrastructure/references/api-key-rotation-verification.md` and the newer Nov 17 `SKILL.md` checklist into `core/devops-infrastructure/`, then remove `devops/devops-infrastructure/`.
     - Keep `research/blocked-page-recovery` (remove `web/blocked-page-recovery`).
     - Keep `productivity/email-inbox-triage` (remove `email/email-inbox-triage`).
     - Keep `creative/gif-search` (remove `media/gif-search`).
     - Keep `productivity/himalaya` (remove `email/himalaya`).
     - Keep `productivity/obsidian` (remove `note-taking/obsidian`).
     - Keep `core/systematic-debugging` (remove `software-development/systematic-debugging`).
     - Keep `devops/vps-forge` (byte-identical to top-level `vps-forge`; remove top-level `vps-forge`).
     - Keep `productivity/xurl` (remove `social-media/xurl`).

---

## 2. Core Code Changes (`/opt/hermes-agent`)

### 2.1 `agent/skill_utils.py` (`EXCLUDED_SKILL_DIRS` & `iter_skill_index_files`)
- Add `".backup_pre_consolidation"` to `EXCLUDED_SKILL_DIRS` and skip any directory inside `iter_skill_index_files()` (`L895-904`) whose name starts with `"."` (except explicit root `.hermes`/`.agents` when passed as `skills_dir` itself, since `os.walk` filters child `dirs[:]`), starts with `".backup_"`, or ends with `".rollback-broken"`.
- Ensure symlinked top-level skill directories still traverse cleanly (`followlinks=True`).

### 2.2 `tools/memory_tool_store.py` (`_split_markdown_sections`, `L100-125`)
- Require ATX heading syntax `re.match(r"^#{1,6}\s+\S", stripped)` (and track fenced code blocks ```` ``` ```` / `~~~` so `# comment` inside code blocks never splits sections!).
- Preserve `#tag` / `#ElevenLabs...` lines without a space after `#` as normal body text instead of H1 headings, preventing false heading-only suppression at `L882`.

---

## 3. Verification Contract
- Unit tests in `tests/agent/test_skill_utils.py` (dot-prefixed / `.backup_*` / `*.rollback-broken` pruning) and `tests/tools/test_memory_tool.py` (`#ElevenLabs` hashtag & code-fence heading regression).
- Live verification of `_skill_catalog(skip_disabled=True)` on `/opt/hermes-agent-data/skills/`: `0` ambiguous entries, `0` `.backup_*` / `.rollback-broken` entries.
