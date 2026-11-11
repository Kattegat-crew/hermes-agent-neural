---
name: dev-project-scaffolding
description: Use when creating a new project or repo under /opt on DEV.
---

# DEV project scaffolding (/opt, host 147.93.3.250)

## Context

Directories created via `ssh dev` default to `root:root 755`. The Hermes
runtime user on DEV is `hermes` (uid/gid 10000). A root-owned repo is
unwritable by Ragnar/agents, and `git` inside the container rejects it with
`detected dubious ownership` — the two failures surface at different moments
(write time vs. first git operation), which makes them easy to miss until
someone actually commits.

## Procedure (verified 2026-11-09 on /opt/neural-context-plugin)

1. Create the directory and `git init` on the host via SSH (runs as root; fine
   at this stage).
2. Set `origin` in the repo's `.git/config` to the SSH remote (e.g.
   `git@github.com:<org>/<repo>.git`).
3. **Ownership fix (the critical step):** recursively hand the whole tree
   (including `.git`) to the runtime user:

   ```bash
   ssh dev 'find /opt/<project> -xdev -user root -group root -exec chown hermes:hermes -- {} +'
   ```

   Note `--` before `{}`: project names contain `-`, but some paths may start
   with `-` after globbing, and chown misparses leading dashes without it.
4. **Verify all three gates before reporting success:**

   ```bash
   ssh dev 'stat -c "%U:%G %a %n" /opt/<project> /opt/<project>/.git; \
            git -C /opt/<project> status --short --branch; \
            find /opt/<project> -xdev ! -user hermes -print -quit'
   ```

   Then from the container: `test -w /opt/<project>` and `test -w
   /opt/<project>/.git`. All must pass — the stat alone proves nothing about
   the runtime user's write ability.

## Pitfalls

- **Do not run `git status` on DEV-host paths from the container.** The path
  isn't shared into the container filesystem, so git fails with dubious
  ownership / missing repo errors that look like a broken repo. Always inspect
  host repos via `ssh dev 'git -C /opt/<project> ...'`; reserve container-side
  checks for `test -w` write probes.
- **A directory that is 755 but root-owned is a silent trap:** agents can read
  and list it, and the first write or commit fails. Never skip the chown step
  just because the directory exists.
- The `find ... -exec chown` must include `.git` contents — the initial `git
  init` creates dozens of root-owned files under `.git/objects`, `.git/refs`,
  and `.git/hooks` that a plain `chown /opt/<project>` misses.
- **The org's GitHub SSH deploy key is read-only: pushes fail with
  `Permission denied to deploy key`.** Push over HTTPS instead, embedding the
  GitHub token from the MCP config in the remote URL (or credential helper);
  then verify the remote branch by API (`GET /repos/<org>/<repo>/branches/<name>`)
  and compare its SHA against the local `git rev-parse HEAD` — a push whose
  branch did not exist remotely also CREATES it, and the API read-back is the
  only proof it landed with the intended content.
- **Not every working repo has a `remote`:** fleet script trees under
  `/opt/hermes-agent-data/` (e.g. `scripts/`) may be gitignored or remote-less
  while looking versioned. Before telling the user "ya está comiteado", run
  `git remote -v` and `git ls-remote` — no remote means the work exists only
  on disk, and "committed" is a false claim; propose creating a repo or
  routing the scripts into the versioned tree instead of reporting done.

## Scope

Applies to new `/opt/*` project directories on the DEV host. Existing repos
with established ownership (e.g. /opt/marketing-campaign-generator) are not
affected. Do not use recursive chmod/chown outside /opt project dirs.