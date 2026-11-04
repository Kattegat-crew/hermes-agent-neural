# Strix LLM backend selection & testing methodology

State of 2026-08-27. Matrix lives in SKILL.md §1; this file is HOW to
re-validate when providers/models change.

## Smoke test (before any scan)

Run 4 sequential minimal chat completions through the SAME proxy the
scan will use. A backend passes only if all 4:

- return HTTP 200,
- have non-empty `content` (reject empty-content backends — Strix 400s),
- contain zero thinking/reasoning blocks (check raw response body, not
  just parsed content),
- emit parseable structured JSON when asked.

gemma4 via NaN passed 4/4 with no anti-thinking injection. qwen3.6
failed intermittently even with thinking flags off — do not retry-hop;
a flaky smoke = dead backend for Strix.

## Proxy mechanics

- `proxy_nan_qwen.py` on :18901 → api.nan.builders:443, pass-through
  (adds browser User-Agent only; Cloudflare 1010 without it).
- Runs inside the hermes-agent container; scanner reaches it at the
  container IP (10.0.7.2:18901), not localhost.
- Start via `start_proxy.sh`; log `/tmp/nan-proxy.log`.

## Live progress signals during a scan

- `grep -c " 200" /tmp/nan-proxy.log` growing = brain responding.
- Scattered 400s = Strix retry absorbs them; sustained 400s = wrong
  backend, kill and re-smoke.
- One-off model hiccups (single 400) are normal over 200+ calls.

## Provider failure signatures

- B.AI free tier: 503 "daily cost limit" mid-run → pivot to NaN+gemma4,
  resume recipe in `/opt/data/strix-scans/REANUDAR-STRIX.md`.
- OpenCode-Go key: if POST completions with the real key and with a
  garbage key return the IDENTICAL 401, the key is dead for inference
  (GET /models stays public — a 200 there proves nothing).

## Ops rules

- Scan containers ALWAYS `docker run -d`; foreground dies at terminal
  timeout (~420s) and `--rm` deletes artifacts with it.
- Env files with keys: chmod 600, never print (mask with sed).
