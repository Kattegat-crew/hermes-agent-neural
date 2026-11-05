---
name: skill-ssot-promotion
platforms: [linux]
description: Use when promoting a skill to the canonical repo SSOT.
---

# Promoting a skill to the canonical SSOT (/opt/hermes-agent/skills)

Goal: the skill must exist in exactly ONE place — the versioned repo — so the fleet loads the reviewed copy, not a stale local one.

## 1. Loader precedence (why move, never copy)

`agent/skill_utils.py` (~:415) documents resolution order:

```
trusted project > local profile (/opt/data/skills) > skills.create_dir > external_dirs (/opt/hermes-agent/skills)
```

- Copying the skill into the repo while leaving the local copy = the repo copy is **shadowed** (loader warns, executes the local one). Promotion that ends here is fake.
- **Move** the local copy out to a retirement backup (e.g. `/opt/data/brain/ops/session-retros/retired-<name>-<date>/`), never `rm` it.
- After the move, `ls /opt/data/skills/...` must show no copy, and `skills_list(query="<name>")` must return exactly 1 result.

## 2. Pre-flight (Zero-Stale-State)

- `cd /opt/hermes-agent && git status` — must be clean; `git pull` first.
- Create an own branch: `git checkout -b feat/skill-<name>-vN`. Warning: the host working tree is **shared by all fleet agents** — your `checkout -b` switches the branch for everyone; identify your commit by hash, and expect concurrent commits to appear on top of yours.
- `cp -a` the skill into `skills/<category>/<name>/`; verify sha256 of each file matches the backup.
- Run the skill's own gates (selftest scripts) from the NEW repo path before committing.

## 3. Repo authoring gate (will fail on first try)

`tests/skills/test_authoring_standards.py` scans every `skills/**/SKILL.md`:

- `missing frontmatter fields: ['platforms']` → add `platforms: [linux]` when the skill depends on POSIX/machine-local paths (`/opt/data/...`, `state.db`).
- `dangling related_skills: ['X']` → every name in `related_skills` must exist **in the repo**; a skill that lives only in the local tier does not resolve from the repo.
- Run filtered: `/usr/local/bin/pytest tests/skills/test_authoring_standards.py -q -k <name>`. The unfiltered suite carries **hundreds of pre-existing failures from other skills** — do not confuse them with your regression.

## 4. Commit and push (verified paths)

- Conventional commit, message without AI attribution: `feat(skills): <name> vX — <one line>`. Commit with pathspec (`git commit -m ... -- skills/<category>/<name>`) so concurrent unrelated dirty files stay out.
- Pushes need explicit human approval. Verified remotes:
  - `origin` = `/opt/hermes-agent-data/git-mirror/hermes-agent.git` (local mirror) — **works**; verify with `git ls-remote origin refs/heads/<branch>` == local hash.
  - `github` = `git@github.com:Kattegat-crew/hermes-agent-neural.git` — host SSH key is a deploy key for m-c-g only; push fails with `Permission ... denied to deploy key`. Needs the Admin to add the host key with write access, or a manual push.
- Deny-rule gotcha: config denies `*git push*-f*`. A `-f` token anywhere on the push command line (e.g. `cut -f1` in the same compound command) triggers a false-positive block. Keep `git push` lines clean; do not retry or rephrase a blocked push.

## 5. Rollback

```
mv <retirement-dir>/<name> /opt/data/skills/<category>/<name>
cd /opt/hermes-agent && git checkout upgrade/vX.Y.Z
```
The commit stays on its branch (local + mirror) for later merge.
