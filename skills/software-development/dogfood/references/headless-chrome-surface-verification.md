# Headless-Chrome Surface Verification (without the interactive browser toolset)

Use when you must verify what a served HTML page actually RENDERS — redirects, mobile layout,
deployed bytes — using only shell/execute_code + headless Chrome CLI + vision analysis.
Typical triggers: PROD portals behind SSO the browser toolset cannot reach; need for hard
evidence of client-side navigation; layout checks at real phone widths.

All three techniques below were verified live (2026-10-13, portal cutover on
reels.neuralcrewlabs.com), including one real bug the textual checks missed.

## 1. Prove a client-side redirect actually navigates — server request log

- `--dump-dom` does NOT follow navigation, and curl/fetch never execute meta-refresh or JS.
  No textual check can prove navigation happened.
- Harness: local Python `http.server` subclass whose `log_message` appends to a list, serving
  the EXACT bytes deployed (pull them down first with `ssh cat` / `scp` — render the real
  artifact, never a reconstruction from memory).
- Point headless Chrome at `http://127.0.0.1:PORT/`. If the log shows `GET /` followed by
  `GET /destino/`, the redirect navigates. That log IS the evidence.
- Gotcha: Chrome can hang past `--virtual-time-budget` on the final page. Run each visit in
  its own subprocess with a timeout; treat the request log, not the screenshot, as the result.

## 2. Real sub-500px mobile viewport via file:// iframe

- Headless Chrome clamps `--window-size` to a ~500px minimum; CDP emulation may fail in
  restricted environments.
- Verified workaround: a page 520px wide embedding `<iframe style="width:390px;height:130px">`.
  The iframe is its own real viewport.
- Required flag for file:// iframes: `--allow-file-access-from-files`.
- Draw dashed colored borders around each iframe so the vision reviewer can distinguish frame
  from content. Strip the meta-refresh/script tags from the copies under test so a fallback
  layout stays visible long enough to screenshot.

## 3. Deployed-byte visual inspection beats grep (real bug caught)

- Failure pattern: `html.replace("plain phrase...", "...")` silently no-ops when the phrase is
  split by an inline tag (e.g. an `<a>` in the middle). Result: wrong page deployed, while
  grep for the destination URL still passes on BOTH pages. Found only by rendering and having
  the vision model transcribe both variants and compare.
- Guards:
  1. After any content replacement, assert the string actually changed before deploying.
  2. Verify deployed bytes via ssh grep of the DISTINCTIVE phrase per page (not the shared URL).
  3. Final gate = render + vision transcription; grep green is not surface verification.

## Cost/limits

- Each Chrome run ~2-15s; one screenshot + vision call per artifact; server-log harness is
  ~30 lines of Python.
- Local HTTP server must be shutdown or the kernel keeps the port; use daemon threads.
