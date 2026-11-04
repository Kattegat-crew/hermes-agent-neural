# MCG test & CI verification (evidence-bound, offline)

Verified procedures for validating `marketing-campaign-generator` changes locally and reading its GitHub Actions CI without false PASS results. Core rule: a test command's success must come from **pytest's own exit code**, never from shell plumbing.

## Interpreter / PYTHONPATH — root cause of phantom collection errors

- The host session may export `PYTHONPATH` pointing at a **python3.14** site-packages tree while the MCG venv is **3.12**: compiled extensions (e.g. `rpds.rpds` under jsonschema/referencing) fail to import and dozens of tests die at *collection* with `ModuleNotFoundError`. Reproduced deliberately on 2026-11-03; not a repo bug.
- Always run `PYTHONPATH=$PWD <venv>/bin/python -m pytest ...` (or `env -u PYTHONPATH`). CI already sets `PYTHONPATH: github.workspace`. Check `sys.version` mismatch before diagnosing anything else.

## Never lose pytest's rc or traceback

- `pytest | tail -N` destroys both the return code and tracebacks. Use `set -o pipefail` **and** read the rc *after* pytest, not after a trailing `echo`; prefer `subprocess.run(capture_output=True)` in scripted checks.
- Repo `addopts` already includes `-q`; stacking `-q` (`-qq`) hides the summary line. For explicit counts invoke pytest directly with `-o addopts=`.
- A background-process notification's `exit code 0` is the wrapper's (`echo`/`tail`), not pytest's — re-read the captured log + rc before reporting PASS/FAIL.

## `scripts/run-tests.sh` allowlist

- The runner rejects undocumented options (`-o` → `error: unsupported factory pytest argument`, RC=2). That RC is a **CLI usage failure, not a test failure**; do not weaken the allowlist to force a flag through. Use documented options or invoke pytest directly on the curated offline group: `PYTHON=<venv>/bin/python MONID_API_KEY=offline-fixture-only bash scripts/run-tests.sh --group factory`.
- `MONID_API_KEY=offline-fixture-only` is for mocked offline fixtures only; never source `.env` in verification runs.

## CI repo facts (observed on main @ 14ffc1d, run #2 failure)

- A global `pytest -q` in CI is not viable by design: ~60 tests need gitignored campaign binaries/credentials/host paths; a shallow checkout breaks `git show <sha>:<path>` tests (`fetch-depth: 0` fixes that class); the runner lacks ffmpeg/pdfinfo/librsvg (apt).
- Guarded skips are acceptable only when each skip names its exact cause (path + why unversioned). A generic skip hiding a real contract failure counts as FAIL.
- CI read-back: MCP GitHub tools reach the private repo (public API 404s; `gh` needs auth). Observe runs only — never re-run a workflow without authorization.
- Reporting "CI fixed" from a green **local** run is wrong: remote CI stays FAIL until a new push is observed. Keep local-fix evidence and remote-run evidence separate.

## Isolated worktree convention

- `/opt/` root may be read-only for subagents: create audit worktrees with `git worktree add` (never clones) under an allowed writable path. Never stash/reset a dirty checkout that belongs to another session.

## Stub fidelity

- A test stub infidel to the real library hides real bugs (e.g. pyCapCut 0.0.4 rejects a second same-type track without `track_name`; the old stub didn't model that, so every music-bearing manifest silently degraded). Model the real API contract in the stub or the test lies.
