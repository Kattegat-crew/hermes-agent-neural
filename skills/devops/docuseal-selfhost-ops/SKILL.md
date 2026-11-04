---
name: docuseal-selfhost-ops
description: "Use when a DocuSeal signing link or page breaks."
tags: [docuseal, firma-electronica, cloudflare-access, smtp, bypass, self-hosted, contratos, rails]
license: Apache-2.0
metadata:
  author: "neuralcrew"
  version: "1.2"
---

# DocuSeal self-hosted operations

## Activation Contract
Use when operating DocuSeal self-hosted: making the signature link public without exposing the admin, debugging a "broken contract" (blank signing page), sending/resending signature emails, or adjusting DOCUSEAL_URL/SMTP.

## Hard Rules
- Signing is **anonymous by design**: the link key (`/s/<slug>`) is the authorization. It must NOT require a login. If it does, a proxy (Cloudflare Access) is intercepting it.
- **Public-signing route set** (from `config/routes.rb` + live flow) — open ALL of these with Cloudflare Access Bypass→Everyone, or the page breaks:
  `/s/*` (submit form + subroutes), `/d/*` (start_form), `/p/*` (draw signature), `/packs/*` (Shakapacker JS/CSS — REQUIRED), `/disk/*` (ActiveStorage page images — REQUIRED, see gotcha), `/preview/*`/`/file/*`/`/blobs_proxy/*` (signed PDFs/blobs), `/up` (health), `/api/submitter_form_views` (analytics POST fired by EVERY signing form on load; without bypass it 302s to CF login and throws CORS errors per signer).
- **Keep the admin protected**: do NOT bypass `/`, `/sign_in`, `/settings/*`, `/templates/*`, `/submissions*`, `/users`, `/api/*` (except `/api/submitter_form_views`), `/jobs`, `/manage`, `/upgrade`.
- DocuSeal env: `DOCUSEAL_URL` must be the public URL (e.g. `https://docuseal.neuralcrewlabs.com`). SMTP via env `SMTP_ADDRESS/.../SMTP_FROM` (SMTP_FROM is mandatory); admin Settings→Email is bypassed by envs.
- `docker compose` from the app's `docker-compose.yml` (uses Caddy for HTTPS); behind Cloudflare/NPM use `:3008` or the exposed port.

## Decision Gates

| Symptom | Likely cause | Fix |
|---|---|---|
| Blank/broken contract but page loads | `/disk/*` images blocked by Access | Bypass `/disk/*` (and `/packs/*`) |
| Login window instead of signing form | Signing path not bypassed / wrong policy | Bypass `/s/*` (or `/d/*`) with Everyone |
| Email not arriving | SMTP env misconfigured or watchtower image bump | Check SMTP envs; VPS `/opt/docuseal/docker-compose.yml` |
| Signing key no longer works | Link slug expired/archived | Verify in admin Submissions; resend |
| "Signature is too small or simple. Please redraw." | Client-side signature quality validation rejects quick/lazy drawings (strokes ≤2 points, >2 near-straight strokes, or cropped ink <20×20px) | Guide signer: use **Type** mode, or draw BIG cursive filling the box. Not a proxy issue if form loads |

## Signature validation (client-side, v3.x) — diagnosed 2026-08-21
- `app/javascript/submission_form/validate_signature.js`: drops strokes with ≤2 points (taps) and skips up to 2 near-straight strokes (avg deviation <3px). Needs ≥1 valid stroke.
- `crop_canvas.js`: cropped ink must be ≥20×20px or it rejects with the same alert.
- The alert is ALSO shown for any fetch/upload failure (misleading catch in `signature_step.vue`), so check for blocked `/api/attachments` too.
- Verified pass paths (real browser): big cursive drawing, Type mode. Fail: small quick squiggle, straight line, taps.

## Make signing easier for clients (typed mode + bigger fields) — verified 2026-08-21
Goal: non-technical clients just TYPE their name (no drawing, no validation failures) and the final signature renders bigger on the PDF.

1. **Data model**: field areas live in `field['areas']` (array, one entry per document/page: `{x, y, w, h, attachment_uuid, page}`), NOT `field['area']`. Preferences live in `field['preferences']`.
2. **The form renders `submission.template_fields || template.fields`** — submissions carry a SNAPSHOT taken at send time. Editing the template does NOT affect already-sent submissions; edit the submission's `template_fields` snapshot too.
3. **Enlarge keeping aspect ~2.67:1** (canvas is 3:1; field was designed at 2.67:1). Keep the BOTTOM edge fixed (the printed signature line) and grow up/left into blank space. Check neighbors: date fields often sit right at `x≈0.25-0.27` on the same page, so grow left, not right. Pro-tip: download the page PNG from `/disk/<key>/<page>.png` and measure blank space with PIL before enlarging.
4. **Typed-only format**: `field['preferences']['format'] = 'typed'` → the signature step shows ONLY the name input (prefilled if `submitter.name` is set) + NEXT; draw/upload buttons disappear; stroke validation is skipped.
5. Apply via rails runner:
```ruby
docker exec -w /app docuseal bundle exec rails runner '
SIG = %w[<field-uuid-1> <field-uuid-2>]
fix = lambda do |fields|
  fields.each do |f|
    next unless SIG.include?(f["uuid"])
    f["preferences"] ||= {}
    f["preferences"]["format"] = "typed"
    (f["areas"] || []).each do |a|
      bottom = a["y"] + a["h"]
      a["x"] = 0.05; a["w"] = 0.19; a["h"] = 0.071
      a["y"] = (bottom - 0.071).round(4)
    end
  end
end
t = Template.find(<id>); fix.call(t.fields); t.save!
s = Submission.find(<id>); tf = s.template_fields; fix.call(tf); s.update!(template_fields: tf)'
```
6. **Verify live**: load `/s/<slug>` in a browser — field overlay style should show the new % (e.g. `left: 5%; width: 19%; height: 7.1%`), the signature step shows an input (no CLEAR/draw buttons), typing + NEXT fires `POST /api/attachments`. NOTE: when testing with the POST aborted, the catch handler still shows the "too small or simple" alert — the alert does NOT mean validation failed if the POST was attempted.
7. Client instructions: open in Chrome/Safari (not WhatsApp webview), type name, NEXT; complete all remaining required fields (dates etc.).

## Execution Steps
1. Identify the app behind Access: `GET /accounts/{acct}/access/apps?per_page=50` → find the hostname app (e.g. `docuseal.neuralcrewlabs.com`).
2. Make signing paths public: for each path, create a Bypass app (1 per path, `domain: "host/path/*"` in a single string) + policy Bypass→Everyone.
3. Verify: `curl -sk -o /dev/null -w '%{http_code} %{redirect_url}' "$BASE/s/<slug>"` → must return origin status (200/404), NOT `302 https://<team>.cloudflareAccess.com`. Repeat for `/packs` CSS/JS and `/disk` images.
4. Confirm admin stays protected: `/`, `/sign_in`, `/settings` must still `302` to CF access login.
5. E2E: open the real signing link in incognito (no cookies), sign, confirm `completed` state in admin panel.

## Output Contract
Return: list of apps created (path → app id → policy id) for the bypass, the verification table (route → status/redirect), and whether admin remained protected.

## References
- `/root/.config/opencode/skills/cloudflare-access-api/SKILL.md` — how to configure the Bypass apps/policies and the `domain`-string-only gotcha
- `/root/.config/opencode/skills/cloudflare-dns-cutover/SKILL.md` — DNS that the subdomain sits on
- `/root/.config/opencode/skills/gmail-smtp-app-password/SKILL.md` — DocuSeal SMTP via Gmail app password