---
name: security-scan-ops
description: "Use when running or triaging a Strix security scan"
tags: [seguridad, security, strix, scan, pentest, triage, llm-backends]
version: 1.0.0
category: devops
---

# Security Scanner Ops (Strix + LLM backends)

Operating the local Strix automated scanner (image `strix-runner:local`) on
the VPS: model backend selection, run mechanics, artifact retrieval, and
real-world verification of findings before fixing. For manual exploitation
methodology use `web-pentest`.

## Hard rules

- Same authorization gate as `web-pentest`: owner's explicit OK before
  scanning any target.
- LLM backend calls stay on free tier ($0) unless the operator approved
  spend. A free-tier quota exhaustion (503 "daily cost limit") is a pivot
  signal, not a blocker.
- A scanner finding is a HYPOTHESIS. Verify against the live system before
  reporting it as fact or "fixing" it — this session had a MEDIUM-severity
  false positive that would have triggered a pointless container rebuild.

## 1. LLM backend (the brain)

Strix dies with 400 if the model emits thinking blocks / empty content.
Validated matrix (2026-08-27, NaN-Builders + B.AI):

| Model | Verdict |
|-------|---------|
| NaN gemma4 | STABLE — 4/4 non-thinking, structured JSON. Default choice. |
| NaN qwen3.6 | NO — intermittent thinking even with flags off; 400 guaranteed |
| NaN glm5.3-flash | NO — thinking model, empty content |
| B.AI (any model) | Free tier exhausts fast → 503 daily cost limit |

Proxy: `/opt/data/strix-scans/proxy_nan_qwen.py` — pass-through OpenAI
proxy :18901 → api.nan.builders:443 with a browser User-Agent (Cloudflare
1010 without it; see `nan-builders-api`). Do NOT inject anti-thinking
flags into requests: they break qwen3.6 and are unnecessary for gemma4.
Full resume recipe on disk: `/opt/data/strix-scans/REANUDAR-STRIX.md`.
Backend test methodology: `references/strix-llm-backends.md`.

## 2. Launching a scan

- ALWAYS `docker run -d` (detach). Foreground runs get killed by the
  terminal timeout (~420s), and with `--rm` the run artifacts die with the
  container even after 100+ successful LLM calls.
- Env file with key: `/opt/data/strix-scans/strix-nan.dockerenv`
  (chmod 600, key never printed).
- Progress signal: `grep -c " 200" /tmp/nan-proxy.log` (inside
  hermes-agent container) growing = LLM responding. A few 400s are
  absorbed by Strix's retry; sustained 400s = wrong backend.
- Final summary box prints `MEDIUM: n | INFO: n`, output dir, token totals.

## 3. Retrieving artifacts (host-path trap)

The Docker daemon resolves `-v` mounts against HOST paths. The scanner
writes to the host's `/opt/data/strix-scans/runs/strix_runs/<run>/`, which
is NOT the same directory this container sees at `/opt/data/...`.
Retrieve with a helper container (see `vps-ops` pitfalls):

```bash
docker run --rm -v /opt/data/strix-scans/runs:/src:ro \
  -v <my-container-side-path>/runs:/dst alpine \
  sh -c 'cp -r /src/strix_runs/<run-dir> /dst/ && chown -R 1000:1000 /dst/<run-dir>'
```

Key outputs per run dir: `penetration_test_report.md`,
`vulnerabilities.csv`, `findings.sarif`, `run.json`.
Copied dirs contain root-owned `.state/`; chown after copying.

## 4. Triage: verify findings before acting

Scanner output ≠ ground truth. Real cases from vault.neuralcrewlabs.com:

- **"User Registration Enabled" (MEDIUM, CVSS 6.5) — FALSE POSITIVE.**
  Vaultwarden's `/api/config` reports `disableUserRegistration:false`
  (hardcoded default) even when `SIGNUPS_ALLOWED=false`. The real test is
  a complete registration POST — server replies "Registration not
  allowed". Payload recipe: `references/vaultwarden-registration-check.md`.
- **`/api/config` info disclosure (MEDIUM) — REAL.** Fixed with an nginx
  `location = /api/config { allow <internal CIDRs>; deny all; }` block in
  the fronting proxy (edit workflow: `vps-ops` §read-only-binds pattern).
- `/admin` reachable (INFO) — normal for Vaultwarden; token-protected
  (404 on unauthenticated POST). Explain to the operator instead of
  "fixing".

## 5. Verifying fixes from an external vantage

Self-tests from the VPS are useless for IP rules: every connection
originated on the host (host curl AND bridged containers) arrives at the
published port with source 10.0.5.1 (Docker userland-proxy SNAT), which
matches typical internal-allow rules. After applying a fix:

1. Test from inside → confirms the service still works for internal users
   (web vault 200, identity/token 400-not-404, admin page renders).
2. Test from OUTSIDE (web_extract or an external checker) → confirms the
   block. This session: `/api/config` still returned 200 from the VPS
   after the fix but 403 from a real external fetch — only the external
   test proved the fix. Report the external result as authoritative.
   Note: `web_extract` on an API path returns the rendered page — read
   its title/content ("403 Forbidden" vs JSON), the effective status is
   embedded there, not in an HTTP status field.

## Related

- `web-pentest` — manual methodology (authorization gate, phases, report)
- `vps-ops` — container/nginx ops, host-path and SNAT pitfalls
- `nan-builders-api` — UA anti-Cloudflare requirement
