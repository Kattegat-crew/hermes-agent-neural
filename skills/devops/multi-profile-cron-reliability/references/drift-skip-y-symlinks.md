# Live diagnostic: profile cron failing (drift_skip + broken skill links) — 2026-08-26 prod

This is the exact reproduction that produced `multi-profile-cron-reliability`.

## The symptom
Profile `roshi` cron `guardar-diario-memoria` (4657b286f619):
- `last_status: error`, `failure_streak: 2`
- `last_error`: `[Errno 13] Permission denied: '.../cron/output/4657b286f619/.output_*.tmp'`

## First (wrong) hypothesis — permissions
- `cron/output/` and the job subdir were `drwx------` held by uid 10000.
- Root could `touch`; uid 10000 could also `touch` (verified with a test file).
- Team applied `chmod 775/chown` and even `chmod 777`. **Did not fix it.** The
  permission error was a red herring; ownership was never the blocker.

## Real cause #1 — drift_skip (unpinned job)
The manual run (via `cronjob action=run`) surfaced the truth in its **output md**:

```
RuntimeError: [drift_skip] Skipped to prevent unintended spend: global inference
config drifted since this job was created (provider 'nan-builders' -> 'custom'),
and this job is unpinned. No inference call was made.
```

Fix applied: pin the job to the current provider/model:
```
hermes --profile roshi cron edit 4657b286f619 --provider "NaN-Builders" --model deepseek-v4-flash
```
Manual run then completed `status: ok`.

## Real cause #2 — broken skill-catalog symlinks
The same run output ALSO showed:
```
Skill(s) not found and skipped: engram-memory-system, guardado-doble-memoria
```
Investigation:
- `roshi/skills/engram-memory-system` was a symlink → `/opt/data/skills/engram-memory-system`.
- `ls /opt/data/skills` → **No such file or directory**. The canonical catalog is
  `/root/hermes-agent-legacy-docker/data/skills/` (+ `skills-especialistas/`), NOT `/opt/data/skills`.
- Scan: **358 symlinks in roshi/skills, 356 broken** (all pointing at `/opt/data/skills/*`).
- `guardado-doble-memoria` is nested under `engram-memory-system/`; the cron skill loader
  resolves by **flat name**, so even if the parent resolved, the nested skill needed its
  own top-level symlink.

Fix: `scripts/repuntar-skills.py` repointed 356/356 to the real catalog; a top-level
symlink was added for the nested `guardado-doble-memoria`. Verified: 0 broken links,
both SKILL.md files resolvable.

## Takeaways
1. `jobs.json` `last_error` and permission-looking errors can be misleading — the real
   cause (`drift_skip`) shows only in the run output md. Always trigger a manual run
   and read the output file before changing permissions.
2. Pin every cron to provider/model at creation (`--provider/--model`); unpinned jobs
   silently skip when global config drifts.
3. Profile `skills/` dirs may carry a full tree of `/opt/data/skills/*` symlinks that
   are dead on this host. Canonical path is `/root/hermes-agent-legacy-docker/data/skills/`
   (+ `skills-especialistas/`). Nested skills need top-level symlinks for the flat loader.