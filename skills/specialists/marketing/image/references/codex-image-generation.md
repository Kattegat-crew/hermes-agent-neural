# Codex CLI native image generation (verified recipe)

Operational procedure for producing images with the OpenAI Codex CLI's native `image_generation` tool (ChatGPT-authenticated — subscription-based, NOT a per-image paid API). Verified end-to-end producing Amazon listing product photos from real reference photography.

## Authentication

- `codex login --device-auth` prints a device-code URL + code valid ~15 minutes; the user completes sign-in in their browser.
- On `401 Unauthorized — token_revoked`, the saved session is dead: re-run device auth; retrying exec will not recover it.
- Verify with `codex login status` → expect `Logged in using ChatGPT`.

## Invocation (verified working form)

```bash
ssh host 'cd <workdir> && codex exec --ignore-user-config --enable image_generation \
  --skip-git-repo-check --sandbox workspace-write -C <workdir> \
  -i ref1.jpg -i ref2.jpg - < prompt.md'
```

## Pitfalls

- **Pass the prompt via stdin when using `-i` refs.** A positional prompt string after multiple `-i` flags is consumed by the flags' argument parsing, yielding exit 1 `No prompt provided via stdin.` Always end the argument list with `-` and feed the prompt through stdin (or `subprocess.run(args + ["-"], input=prompt_text, text=True)`).
- **Normalize references to avoid `invalid_image_file`:** convert originals to JPEG, RGB, strip metadata, downscale to max side ≤2048 px keeping aspect ratio (Pillow).
- **Work in an isolated subdir** (`-C <dir>` + `--sandbox workspace-write`); keep it out of any git working tree.
- **Capture the output path the tool itself reports** — never glob "latest generated file" when parallel generations may be running.
- A failed tool request produced no image; never substitute shell-drawn mockups or switch to other paid APIs to fake a result.

## Reference-driven fidelity (product photography)

- Attach 3–5 real product photos as `-i` refs; optionally add one previously approved generated image for lighting/style only, stating in the prompt that real photos override it for product identity.
- Pin in the prompt: exact layout/proportions, countable items, forbidden additions ("no invented pockets/colors/features"), aspect ratio, requested resolution (e.g. 2048×2048 — report actual dimensions, no silent upscale).
- Generate **photo-only plates**: no text, labels, arrows, or measurement graphics. Add typography, dimension callouts and infographic panels afterwards deterministically (Pillow overlay) — text is then pixel-perfect and editable.
- One candidate per run; retry only on request-format errors, never fall back to alternate paid generators.
