---
name: akari-video-editing
description: "Use when editing campaign video with Akari editor."
tags: [akari, video, edicion, reels, stories, captions, tailscale]
version: 1.0.0
author: Ragnar
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [akari, video, editing, reels, stories, overlays, captions, approval]
---

# AKARI Video Editing

AKARI Video (AkariLabs/akari-video, MIT, akari.video) is an **AI video editor the agent drives**. You (the agent) do the editing; the human reviews and approves at milestones. Use this for campaign video editing (cut, captions/cartelas, subtitles, narration) — NOT ad-hoc ffmpeg/PIL, which is how Jonathan had us doing it before, and he corrected us to use the proper tool.

The catalog has 23 skills (one per stage + two cross-cutting) in `skills/<name>/SKILL.md`. This skill is the map; for procedure read the relevant SKILL.md inside the project.

## Where it lives (this environment)

- Source/install: **dev .250 host** at `/root/.akari/app` (v0.1.36 app, launcher v0.1.10). It is on the HOST, NOT in the Hermes container and NOT on prod .222. Access the host filesystem via the docker socket (`docker run --rm -v /:/hostfs alpine ...`).
- The `marketing-campaign-generator` pipeline repo also lives on the dev .250 host at `/root/marketing-campaign-generator` (accessible inside the Hermes container at `/host/root/marketing-campaign-generator`, NOT on .222) — separate from Akari.
- `node` is on the host; we drive Akari through a `node:22` container mounting the app:
  `docker run --rm -v /root/.akari/app:/app -w /app node:22 node packages/akari-launcher/bin/akari.mjs <cmd>`

## Install / dependencies (done 03/09/2026)

- `akari-launcher` is **zero npm deps** (Node stdlib + vendor) — runs immediately, provides the `akari` entry point (scaffold, doctor, store, narration/assets/capability).
- The editing packages need npm deps installed (npm workspaces, from the repo root):
  `npm install -w packages/render-cut -w packages/media-bin -w packages/template-render -w packages/preview-server -w packages/akari-tools`
  - `media-bin` postinstall downloads bundled ffmpeg/ffprobe to `packages/media-bin/vendor/linux-x64/`.
  - `template-render`/`render-cut` need `puppeteer-core`; `preview-server` needs `esbuild`; `render-cut` needs `hyperframes`.
  - **Node engine**: puppeteer-core requires node >=22.12. Install AND run with `node:22` (a `node:20` install logs EBADENGINE warnings — harmless but prefer 22). Do NOT install the `apps/shell` (Theia/Electron) on a headless VPS.
- Running as agent: you are the agent. Read the project SKILL.md files and drive the CLI. You do not need to launch a separate opencode/Claude instance.

## Project flow (23 skills → the edit)

1. **create-project** — `akari new <dir>` copies `templates/project-default/` (records report HTML; git init only if safe; never overwrites existing files). Leaves `.akari/intake.json` (status: draft), `.akari/connections.json`, `edit.json`, `exports/`, `planning/`, `CLAUDE.md`.
2. **Fill intake** — `tasks` (what to make), `target` (duration & orientation e.g. "20 seconds vertical"), `autonomy` (`checkpoint` default = approve at milestones). Set status `submitted`.
3. **analyze-footage** — proxy, transcription, keyframes → `analysis.json` (`akari media`; cloud transcription only with approval).
4. **analyze-project** — cross-clip interpretation + read-only report.
5. **edit-plan** — direction proposal → explicit approval → `edit.json` v0 + overlays.
6. **overlay-authoring** — captions/cartelas/scene overlays (CSS keyframes / WAAPI / declarative Three.js).
7. **generate-narration** — script → narration audio (VOICEVOX local free; fal Qwen3-TTS cloud behind approval).
8. **edit-lint** — deterministic checks on edit.json; frame inspection after PASS.
9. **render-cut** — lint PASS → explicit approval → export MP4 to `exports/` → verify.
10. **verify / export-nle** — verification ladder; optional FCPXML/FCP7XML/SRT export.

Approval gates live in `.akari/events/` / `decisions.json`; `autonomy: checkpoint` means approve at plan + before export.

## Preview / UI (the part the human sees)

- Browser preview is a **headless Node server** (NOT Electron): `akari.sh --preview [project] [port]` runs `packages/preview-server/src/server.mjs`, default port **4567**.
- Binding: on the host/VPS it listens on localhost. Expose it to the human **only over Tailscale (tailnet-only HTTPS)** — never public internet. See the `setup-remote` skill. The human opens the URL and sees the edit live; the Theia desktop app is a heavier alternative (avoid on headless).
- `?frameEngine=0` switches the preview to the legacy viewer.
- Store/connection registry + free read-only doctor: `akari status` (manage-connections). `akari capability <query> --json` searches the shipped skill/contract surface.

## Secrets / config

- Credentials live in `~/.config/akari-video/credentials.env` (chmod 600) and `.akari/connections.json` per project. Never print values.
- `manage-connections` is the ONLY gateway to paid generation and external publishing. Track cost-approval policy there.

## Placement decision (Jonathan's environment)

- **Dev .250** is the right home (same host as the video-ai-generator + campaign pipeline): generate → edit (Akari) → publish (Composio) in one place. Preview via Tailscale works from there.
- **Prod .222** should NOT host the editor — it's client-serving infra (landings, NPM, connections, gateway). Don't mix a build/creative tool with the production gateway host.

## Gotchas

- **IG story safe zones**: ~250px (~13%) top and bottom are covered by the IG UI — keep text/message content inside the safe band, and text should be <60% width on a 1080x1920 story.
- **Brand story design rules (Jonathan-approved, corrected 03/09)** — these override the old instinct:
  - **Logo goes TOP-LEFT, small** (not right side, not large). Position ~top:5%, left:5.5%, width ~13%.
  - **NO hashtags on a story** — hashtags belong to feed posts, never to an IG story. Remove them entirely from story overlays.
  - **Text must be legible** — never use yellow/again two-tone text that disappears over a bright casino background. Use white/ivory with a strong dark drop-shadow, or a dark scrim behind text.
  - **Prize amount must look premium, not flat** — a big number like "1.600.000" rendered as plain text reads as MS-Paint. Put it on a rounded card with a gold gradient, inner highlight, soft outer shadow, a small uppercase label above it, and a thin rule. Deep, not flat.
  - Brand palette per client (Golden gold/red; Lucky/Paradise red/gold/green) — see the persona/logo assets.
- The 23 skills are the canonical procedure — read the project's `skills/<name>/SKILL.md` before each stage; do not improvise the stage commands.
- `akari new` on an existing dir only ADDS missing files (never overwrites) — good for supplementing.
- Cross-cutting: `verify` runs the stack build/tests (L0/L1/L2); don't skip before shipping.

## Pitfall verified 03/09 — `akari new` writes into the RUNNING process's filesystem

`akari new <dir>` creates the project in the filesystem of the process that executes it. If you run it inside a docker container that only mounts the app `/root/.akari/app`, the project (intake.json, edit.json, templates, git) lands in the **container's ephemeral FS** and vanishes when the container exits — you then think intake.json "didn't get created."

Fix (create the project in a persistent host dir you mount):
```sh
docker run --rm -v /root/.akari/app:/app -v /root/.akari/workspace:/workspace -w /app node:22 \
  node packages/akari-launcher/bin/akari.mjs new /workspace/<project-name>
```
Then verify it is really on the host: `docker run --rm -v /:/hostfs alpine cat /hostfs/root/.akari/workspace/<project-name>/.akari/intake.json`.

## Preview exposure (verified headless, Tailscale-only)

The preview server binds `127.0.0.1` by default → unreachable from outside. Expose it to the human **only over the tailnet** by binding `--host 0.0.0.0` and publishing on the host's Tailscale IP (dev .250 host = `100.86.8.81`):
```sh
docker run -d --name akari-preview \
  -v /root/.akari/app:/app -v /root/.akari/workspace/<project>:/project -w /app \
  -p 100.86.8.81:4567:4567 node:22 \
  node packages/preview-server/src/server.mjs /project --port 4567 --host 0.0.0.0
```
Confirm it serves (title is the giveaway): the page returns `<title>AKARI Video Preview</title>` over `http://100.86.8.81:4567/`. Never publish port 4567 to the public host IP; the `-p <tailscale-ip>:4567:4567` form keeps it tailnet-only.

## Transcription for analyze-footage / QA (faster-whisper, verified)

Whisper is available, but **not** in the Hermes container python (3.13) — import fails there. Use `uv` (already installed) to run it, and the model is already cached at `/opt/data/.cache/huggingface/hub/models--Systran--faster-whisper-{base,tiny}`:
```sh
# extract audio (ffmpeg is in the container)
ffmpeg -y -i input.mp4 -vn -ac 1 -ar 16000 -f wav /tmp/audio.wav
# transcribe (es)
uv run --quiet --with faster-whisper python -c "
from faster_whisper import WhisperModel
m = WhisperModel('base', device='cpu', compute_type='int8')
segments, info = m.transcribe('/tmp/audio.wav', language='es', beam_size=5)
for s in segments:
    print(f'[{s.start:.2f}->{s.end:.2f}] {s.text.strip()}')
"
```
This gives you the real narration + timings to pick the 20s climax segment and write the cartela. (The `whisper` bundled skill assumes openai-whisper/torch — not what's installed; use faster-whisper above.)

## Pitfall — intake `tasks` must be VALID Akari task IDs (verified 03/09)

`edit-lint` FAILS with "unknown task id" if you fill `intake.json#tasks` with free text. `tasks` is an enum; the only valid IDs (from `packages/schemas/intake.schema.json` → `x-akari-labels` / `$defs.taskId`) are:
- `transcribe-captions` (transcription/title/telop) — use for a branded title card/cartela
- `silence-cut` (cut unwanted pauses/NG) — use for trimming to target length
- `bgm-sfx` (BGM/sound effects)
- `narration`
- `3d-inserts`

Correct example for a 20s story with a cartela:
```json
{ "version":1, "tasks":["silence-cut","transcribe-captions"],
  "target":{"duration_s":20,"keep_length":false,"taste":"..."},
  "autonomy":"checkpoint", "status":"submitted", "submitted_at":"<ISO>", "title":"..." }
```
`target` requires both `duration_s` and `keep_length` (mutually exclusive with each other); `status` must be `submitted` to run.

## edit.json v0 + overlay HTML (the format, verified 03/09)

Reference: `packages/schemas/examples/edit-v0-sample/edit.json`. Structure:
```json
{ "version":0,
  "output":{"width":1080,"height":1920,"fps":30},
  "source":{"path":"assets/clip.mp4","proxy":null},
  "cuts":[{"in":34.5,"out":54.5}],
  "overlays":[{"id":"cartela","html":"overlays/cartela.html","start":0.0,"duration":20.0,
    "transform":{"x":0,"y":0,"scale":1,"rotate":0},"vars":{}}] }
```
`cuts` timing is in SOURCE seconds; `overlays[].start/duration` is timeline seconds; `transform` positions/scale/rotates the single root element.

Overlay HTML (see `edit-v0-sample/overlays/cap-a.html`):
- **One single root element** (`<div class="...root">`), inline `style="--x:0px; --y:0px; --scale:1; --rotate:0deg; --font-size:40px; --color:#fff"`.
- Position the root with `absolute` % (left/bottom/top) relative to the output frame; the container applies `transform` from edit.json.
- Expose anything a human may tune as CSS vars (`var(--name, fallback)`) — position, scale, font-size, color.
- **No independent timing** inside the fragment — timing lives in `edit.json overlays[].start/duration` only.
- Local assets (logo) → embed as a data URI to avoid path-resolution issues; a 250px logo PNG as `data:image/png;base64,...` is ~65KB and fine.

## Render-cut invocation (CHROME required — verified 03/09)

Contract: `validate → plan → human explicit approval (THIS export) → render → verify`. Never skip plan; lint must PASS first (`.akari/lint.json` verdict `pass`).
```sh
# 1. lint
node packages/edit-lint/bin/edit-lint.mjs <project>
# 2. plan only
node packages/render-cut/bin/render-cut.mjs <project> --plan-only
# 3. after the human explicitly approves THIS export (render.json phase=planned → present it, get OK)
node packages/render-cut/bin/render-cut.mjs <project>
```
`render-cut` and `template-render` need **Chrome** (puppeteer-core rasterizes overlay HTML). The node images don't ship it, and `node:slim` lacks the shared libs. Chrome is already on the host at `~/.cache/puppeteer/chrome/<ver>/chrome-linux64/chrome` (and a `chrome-headless-shell` variant). Pass it via env and mount it:
```sh
-e AKARI_CHROME_PATH=/root/.cache/puppeteer/chrome/linux-151.0.7922.47/chrome-linux64/chrome \
-v /root/.cache/puppeteer:/root/.cache/puppeteer
```
Also needs `ffmpeg`/`ffprobe` on PATH. Build ONE reusable render image (chrome libs + ffmpeg) rather than re-fighting libs each run — see `references/render-environment.md`. `render.json` phase goes `planned` → `rendered`; exit 0 = verify PASS.

## Reusable driver + repo (verificado 03/09)

- El repo `video-ai-generator` (dev .250 host, `git@github.com:Kattegat-crew/video-ai-generator.git`) ya tiene
  el driver reutilizable: `scripts/akari_edit_story.py` (crea proyecto + intake + edit.json v0 + cartela de
  marca + lint + plan de render) y la doc `docs/akari-editing-integration.md`. Usa el driver en vez de
  re-armar el proyecto a mano. Commiteado y pusheado a `main` (09fa98d9).
- Para pushear ese repo (vive en el HOST, no bajo `/opt/data`): corre git en un contenedor montando el repo
  y la key SSH del host (`-v /root/.ssh:/root/.ssh` + `GIT_SSH_COMMAND="ssh -i /root/.ssh/id_ed25519 ..."`),
  con `git config --global --add safe.directory /repo` (root-owned → "dubious ownership"). Los `.mp4`
  generados los excluye el `.gitignore` del repo. Detalle del flujo de push en `github-push-container`
  (si se adopta).

## Design-cartela workflow tip

Tie the 20s cut to the strongest segment: extract a contact sheet with `ffmpeg -vf "fps=1/3,scale=<w>:<h>,tile=5x4"`, view it to pick the climax, and cross-check the narration timing from faster-whisper. For real event footage, the audio hook ("último bingo… por 150 mil") and the on-camera staff climax may be in different windows — pick the 20s that contains both the payoff narration and the best visual.
