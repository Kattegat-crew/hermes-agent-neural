---
name: independent-infra-audit
description: "Use when auditing a deployed pipeline read-only."
tags: [auditoria, read-only, evidencia, cron, verificacion, infra]
version: 1.0.0
author: Ragnar
---

# Independent Infrastructure Audit (read-only, evidence-bound)

Use when: asked to audit/verify a deployed system (crons, wrappers, publish flows, dashboards, agents) before closing it — or when *you* are the agent about to claim a system is "100% operativo".

This system's owner does not accept "listo / 100% verificado" from the agent that built the thing. The expected artifact is a **fresh-context, read-only audit** ending in `APROBADO / APROBADO CON HALLAZGOS / RECHAZADO`, with PASS/FAIL/BLOCKED + the exact command output behind every check. "Un check sin evidencia real es FAIL."

Support files:
- `templates/independent-audit-prompt.md` — reusable reviewer prompt (11-check skeleton, prohibitions, verdict format).
- `scripts/audit_ticker_ownership.sh` — read-only forensics: which ticker owns the cron runs, output-dir permissions, root-owned residue, git state as uid 10000.
- `references/bingo-calendar-audit-2026-09.md` — worked example: the calendar bingo-sep2026 publication audit and the four findings it produced.
- `references/mcg-test-verification.md` — MCG-specific test/CI verification: PYTHONPATH 3.14/3.12 contamination, `run-tests.sh` option allowlist, pytest rc/traceback preservation, CI run facts, worktree convention.

## 1. Golden rule: an audit that writes is worthless

Prohibited unless the user explicitly authorizes it: publishing, external messages, commit/push, editing repo/config/cron, paid generation, Drive writes.

- `py_compile` ALWAYS with `PYTHONPYCACHEPREFIX=/tmp/audit-pycache` — plain `python3 -m py_compile` drops `__pycache__/*.pyc` **inside the audited repo**.
- Temp artifacts in `/tmp` only. Fingerprint before and after: `git status --porcelain` must stay empty and `git rev-parse HEAD` must not move.
- **Before running a wrapper whose script commits/pushes**, prove the commit path is a no-op: run the inner step with `--dry-run` (e.g. `sync_from_drive.py --dry-run` → expect `0 cambios del humano`) and confirm `HEAD == origin/main`. Only then execute the wrapper — otherwise your "audit" creates the commit it was supposed to only observe.
- If the no-op proof fails, report the check **BLOCKED** with the reason instead of running it.

## 2. Run the check as the real user, in the real namespace

Cron here runs as **uid 10000** with `HOME=/opt/data`. Two equivalent runs, both required for E2E checks:

```bash
# host view (uid 10000)
setpriv --reuid=10000 --regid=10000 --clear-groups env HOME=/opt/data bash <wrapper|cmd>

# gateway view — the faithful environment (same ns + env)
docker exec -u 10000 -e HOME=/opt/data hermes-agent bash -lc 'bash /opt/data/scripts/<wrapper>'
```

Why both: wrappers resolve paths bilingually (`/opt/data/repos/...` first, then `/root/hermes-agent-legacy-docker/data/repos/...`). On the host `/opt/data/repos` does not exist, so the host run exercises the fallback branch and the container run the primary one. A pass in only one namespace is partial proof.

Establish the volume map before trusting any path:

```bash
docker inspect hermes-agent --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
```

Typical: host `/root/hermes-agent-legacy-docker/data` == container `/opt/data` (one physical tree, `10000:10000`). Host `/opt/data` and container `/root` are **different, near-empty trees** — a path that exists in one may be missing in the other. **Audit the path that exists and report the discrepancy**: a checklist naming `/root/<repo>` or a bare `/opt/data/...` usually describes the wrong namespace; state the corrected path as its own (minor) finding instead of silently auditing elsewhere.

## 3. Ticker forensics: who actually ran the job

Two schedulers can claim the same `jobs.json`: the container gateway (uid 10000) and the root Hermes Desktop SSH backend (`hermes serve --isolated`, `HERMES_HOME=/root/hermes-agent-legacy-docker/data`, `HERMES_DESKTOP=1`, host mount ns).

Cheapest forensic — **ownership of the run artifact**: every run writes `cron/output/<job_id>/<timestamp>.md`. `root:root` ⇒ the root ticker claimed it; `10000:10000` ⇒ the gateway. `scripts/audit_ticker_ownership.sh` prints all of it; essentials:

```bash
find /root/hermes-agent-legacy-docker/data/cron/output -user root -newermt 'today 00:00' -printf '%TH:%TM %u:%g %s %p\n' | sort
find <repo> -user root -not -path '*/.git/*' | wc -l
```

Why it matters: a root-claimed run of a *write* job leaves `root:root` files (JSONL, XLSX, dashboards, `.pyc`, even `.git/objects`) in a tree uid 10000 must keep writing to → the next legitimate run fails or silently diverges. Root can also push (its own `/root/.ssh/id_ed25519` authenticates against the GitHub remote), so nothing fails loudly. Repair: `chown -R 10000:10000 <path>` with numeric ids (the group `hermes` does not exist on the host). Severity: **medio** — the pipeline still runs, but ownership is a latent outage.

## 4. Check the state machine in BOTH directions

For approval-gated pipelines (JSONL/DB = source of truth), the obvious invariant is not enough:

- `publicado ⇒ media_ids` present — the literal checklist criterion.
- **`media_ids` present ⇒ `publicado`** — the inverse. Rows left `aprobado` WITH `media_ids` are published-but-mis-recorded. If the self-heal guard is gated on a time window (`0 <= now - slot <= 2h`), a **past slot can never self-repair** → permanent drift in every report that reads the JSONL. Fix: correct the row + regenerate and re-upload the human-facing surface (XLSX) to *every* copy, or the next sync reverts it again.
- **Cross-row field-schema consistency**: the same field can carry two shapes if the writer changed (`media_ids` as list `[ig_id, fb_id]` vs dict `{"instagram":…,"facebook":…}`); any consumer assuming one shape breaks on the other.
- Count states explicitly (`publicado / aprobado / listo_para_aprobacion / a_producir`) and report how many are pending approval.

Also check the human-editable sync surface can't overwrite state backwards: if `Estado` lives in the sync's EDITABLE map, a stale XLSX reverts the JSONL on every tick.

## 5. Guardrails: prove the gate, quote the line

- Find every entry point that can perform the critical action (grep the API/tool call, not the word "publish") and confirm the only caller is the gated cron.
- Quote exact `file:line` for: the state filter, the anti-duplicate guard (`media_ids` present ⇒ skip and mark, never re-post), and the raise/exit blocking non-approved rows.
- Check whether a CLI flag can bypass the gate (`--force`): if it exists in the function signature but is not exposed via `argparse`, say so precisely.
- Note `--dry-run` paths that `return` **before** the approval guard: harmless (dry never publishes), but a green dry-run does not prove the row is publishable.
- Note crons that are not `no_agent`: a script + agent turn means an LLM with tools runs after the script, and the gate lives in the script, not the prompt.

## Verificar afirmaciones publicadas por OTRO agente (verificado 03-nov-2026)

Cuando el audit consiste en validar lo que otro agente declaró ("publiqué el
mensaje X, exit 2, sha256 Y"):
- **Read-back, no confianza en el POST**: releer el artefacto publicado por su
  id real (`GET /channels/{tid}/messages/{mid}` con token del bot): autor,
  bot=true, longitud de chars, timestamp y contenido íntegro. Un POST exitoso
  del reportador no prueba el contenido.
- **Reproducir códigos de salida EN MEMORIA, sin tocar prod**: importar el
  módulo con un destino falso (monkeypatch de la función que publica) y
  confirmar la rama de `main()`/`sys.exit` — nunca fabricar un fallo en vivo
  contra el destino real.
- **Interpreter/contexto del cron, no del host**: los scripts de cron corren
  DENTRO del contenedor `hermes-agent`. `/opt/hermes/.venv/bin/python3` existe
  en el contenedor y NO en el host; `127.0.0.1:3000-3002` (gateways) escucha
  solo dentro del contenedor. Un "No such file or directory" o puerto vacío
  observado desde el host NO es un bloqueo real — es la vista equivocada.
  Validar `py_compile` y paths con `docker exec hermes-agent ...` (el mismo
  intérprete que usará el cron) antes de declarar BLOCKED.
- **Cifras contra fuente, no contra el resumen**: sumar/count los registros de
  la fuente primaria (JSONL/DB) para la fecha reportada y comparar al peso
  (ej.: Golden 7 reportes / neto 4.255.374 en historico.jsonl).

## 6. Deliverable shape

1. Verdict first (one line), then scope/method/time window.
2. Table of the N checks: **PASS / FAIL / BLOCKED** + one-line evidence (exact output, hash, HTTP code, uid).
3. Findings, each classified (crítico / medio / menor) with a concrete correction — including defects in the checklist itself and any side effect the audit caused.
4. Close with what was NOT done: "no se publicó nada, no se commiteó, `git status --porcelain` vacío, HEAD idéntico antes y después".

Tone: skeptical and specific. A check you could not actually run is FAIL or BLOCKED, never PASS.

## Pitfalls

- Inline shell commands with nested quotes (e.g. a `grep` pattern mixing `'` and `"`) get **command-blocked** as an oversized/unparseable inline payload. Use `search_files` for content greps, or write the payload to a file and run it.
- `setpriv ... bash -c` needs `env HOME=/opt/data` explicitly, or paths like `~/.ssh` resolve to the wrong home.
- `hermes cron list` is necessary but not sufficient: read the run artifact in `cron/output/<job_id>/` and `enabled: true` in `jobs.json` — a job can be `[active]` yet deliver nowhere, and `last_status: ok` on a `no_agent` script says nothing about the agent turn.
- Silent success is the design here (empty stdout ⇒ no delivery): exit 0 with **0 bytes** of stdout is the expected "nothing was due" result, not a broken run. Assert byte counts, don't eyeball.
- Related skills (`hermes-cron-runtime-verification`, `marketing-calendar-publishing`, `cron-runtime-verification`) hold overlapping context but are user-owned/not curator-managed: my writes to them are refused. If they drift, ask for `hermes curator adopt <name>` rather than duplicating their content here.
