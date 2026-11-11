---
name: seo-landing-audit
description: "Use when QA/SEO-auditing a client landing site pre-launch."
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: MIT
tags: [seo, qa, landing, auditoria, prerender, spa, production]
related_skills: [static-portal-generator]
metadata:
  hermes:
    tags: [seo, qa, landing, auditoria, prerender, spa, production]
    related_skills: [static-portal-generator]
---

# SEO Landing Audit

Audit a client landing site (Golden Game, Paradise, Lucky Brothers style: SPA + prerender behind Cloudflare) before declaring it launch-ready. The core discipline: **every claim is verified against production with a real command output** — never against a previous report, a local build, or memory.

## When to Use

- Plon (or a ticket) asks to "auditar" / re-check / validate the QA or SEO state of a client landing site or portal before a launch or campaign push
- A previous QA report claims "N/N READY" and needs independent verification against production
- Re-running or hardening a landing QA gate (`qa_landing.py`-style checklist scripts) — use it to find what the gate cannot detect
- Cross-brand/consistency reviews of live marketing sites (dates, TyC, sedes, map links, og:meta)

## Always-On Rules

- **Audit production, not artifacts.** Never present a local `dist/` checklist (e.g. `--project-dir` mode) as evidence about HEAD. `dist/` is gitignored and rebuilt by nobody; it routinely lags HEAD by many hours and diverges in content (missing map links, leftover placeholders). Live-URL checks are the only green that counts.
- **A gate that cannot fail where it should is a false green.** Before trusting "N/N tests passed", grep the gate script itself for the detector each checklist item implies (placeholders, forbidden content, required fields). Whatever the gate does not implement, run manually and label it as a gate gap in the report.
- **Verify a "missing" before reporting it.** For every absence claim (GSC verification, sitemap, robots), check the alternate path first — e.g. GSC is usually verified via DNS TXT (`dig +short TXT domain`), not a meta tag in HTML. Reporting a non-issue erodes the audit's credibility.
- **Content consistency is a legal check, not cosmetic.** Promo dates, campaign names, and legal basis (e.g. Ley 1581) must be identical everywhere they appear (home, TyC, campaign/event pages). Sweep all routes with one date-pattern grep; a contradiction on a sweepstakes page is a launch blocker.
- **Report by severity** (Alta/Media/Baja), each finding with the exact evidence (URL, grep count, header line, similarity number), plus a section of what was *verified sane* with evidence. Distinguish clearly between "fixed and verified live" and "claimed fixed".
- Deliverables go to the Discord ticket (full MD attached via MEDIA:) with a compact summary in chat — the ticket is the home of the work.

## Procedure

1. **Repo pre-flight.** `git status` + `git pull` (or verify local hash == `git ls-remote`) on each repo involved; note HEAD commit + timestamp. Note `dist/` mtime: if it predates HEAD, all local-mode results are void (say so in the report).
2. **Sitemap inventory.** Fetch `sitemap.xml`, hit every URL with `curl -s -o /dev/null -w "%{http_code}"` on both www→apex and http→https to verify redirects.
3. **Raw-HTML sweep** (what crawlers and link previews receive first):
   - titles + meta descriptions unique and non-empty per route;
   - placeholders `[PENDIENTE|TODO|XXX]` case-insensitive across all routes (expect 0);
   - structured data blocks (JSON-LD, openingHours) match what was actually approved — grep for banned/invented keys;
   - og:image real dimensions (`identify` or bytes + HTTP 200);
   - outbound map links carry UTM and use `place_id` (text-query links land on wrong listings — count them).
4. **Rendered-DOM sweep** — for SPA/prerender sites the shipped HTML ≠ what users see; check BOTH. See `references/audit-commands.md` for the proven chromium + similarity commands.
   - dump DOM per route (headless chromium, `--virtual-time-budget`), compare `<title>` vs rendered `<h1>`: a stale campaign title on the live campaign page is a top-severity finding;
   - text-similarity of raw vs home raw per route: near-1.0 means the prerender copies the home body into every route (duplicate content at scale, broken for no-JS clients);
   - venue-safe check on ad landing pages: no online-betting language in rendered text.
5. **Headers & delivery.** Status, HSTS, `cache-control`, `content-encoding` (with `Accept-Encoding: br`), `cf-cache-status`, TTFB (`-w "%{time_starttransfer}"`). Static HTML served `no-store`/`DYNAMIC` = no edge cache (report as Baja).
6. **Gate execution.** Run the project's QA script twice: `--url` against production (the evidence) and local mode (only to demonstrate its blind spots). Run its test suite. Then diff what the gate *measures* vs what the checklist *claims*.
7. **Off-page context.** GBP/listing status vs published sedes (suspended/unverified listings behind live map links), DNS records (GSC TXT), search-console indexing state when accessible.
8. **Report.** Rank findings, propose an ordered fix plan, and end with a verdict that distinguishes "checklist green" from "launch-ready" — they are not the same when the gate has gaps.

## Brand-contact & campaign-identity canonicalization

When the Admin mandates new brand contact data (phones, WhatsApp, addresses) or a seasonal campaign changeover, a sweep of live marketing sites must verify the swap end-to-end. Recipe: `references/contact-canonicalization.md`. Non-negotiables:

- **Normalize digits before matching.** A phone appears as `3166910728`, `316 691 0728`, `316-691-0728` and `+57 316 691 0728`; a guard that greps one literal format is a false green. Normalize both sides to digits, then compare.
- **One source of truth, per brand.** Keep the canonical numbers in the brand's brain entity; every repo/gate reads from there, not from chat messages.
- **Never blanket-replace across unrelated repos.** The same digits can be a legitimate contact of a different entity (e.g. a band's own WhatsApp) — scope replacement to the brand's repos and check the brain before declaring a hit "obsolete".
- **Seasonal changeover = full head sweep per event route.** og:image, twitter:image, preload links, keywords and JSON-LD (`Event` names/dates) all carry the old season; grep for season tokens across raw HTML, not just visible text.

## Fix verification (Coolify landings)

When the audit leads to a fix deployed via Coolify (PROD landings), close the loop on the deployment itself, not just the site:

- **HTTP 200 ≠ new commit live.** Cloudflare serves cached HTML; a green status code proves nothing about which build is running. Trigger the deploy (deploy webhook/script), then poll `GET {coolify}/api/v1/deployments/<uuid>` until `status=finished` and assert `commit == <HEAD hash you pushed>` — that is the only proof the fix shipped.
- **Verify the fix on live raw HTML, per route, with the same detector that found the bug** (same grep, same similarity script). Post-fix numbers go in the report next to the pre-fix ones.
- **Duplicate-content remediation pattern (A2):** when raw-vs-home similarity ≈ 1.0 across routes, the durable fix is per-route prerender shells declared in one data file (`routeShells.js`-style: own H1, lead, verified points, internal links per sitemap route) that the prerender injects into `#root` — React replaces them on mount. Invariant to encode in a guard test: **no sitemap route may inherit the home shell**. Facts only from approved sources (seoMeta, published TyC, operation data) — never invent copy to fill a shell.
- **Word-boundary matching on dates.** `grep "1 de noviembre"` matches `11 de noviembre` (substring); pattern `[^0-9]1 de noviembre` or regex with a leading non-digit — a naive count both false-positives and false-negatives on campaign dates.

## Pitfalls

- 🔴 **Chromium headless needs `--no-sandbox` in containers** and a `--virtual-time-budget` (~4000ms) or JS routes render empty and you will misread a healthy page as blank. Dump to a temp file per route, then parse with Python (strip script/style, tag-strip, normalize whitespace).
- 🔴 **Do not trust a single render pass as the whole page.** Titles live in the static `<head>` (prerender/seoMeta), H1s come from JS — comparing only one of the two hides the mismatch class entirely.
- 🟡 **Raw HTML is compressed on read but size reflects encoding**: check `content-encoding` with an explicit `Accept-Encoding` header, otherwise sizes mislead.
- 🟡 **When both raw and rendered differ, the finding is the raw one** — Googlebot/preview bots act on the first HTML; "it renders fine in a browser" is not a rebuttal.
- 🔴 **og:image / twitter:image must be ABSOLUTE URLs** — Meta and link-preview bots ignore relative image URLs silently (page looks fine in a browser, preview breaks everywhere). After generating any og asset, grep the built HTML for `content="https://` (not `/assets/...`), and check the JSON-LD `image` too.
- 🟡 **WhatsApp contact verification**: `wa.me/<digits>` must return 200 and redirect to `api.whatsapp.com/send`; that proves the number is real but NOT that it is Business — confirming Business Account status requires an external check (phone/WhatsApp audit), so label it as such in the report.
- 🔴 **A banned/unapproved structured-data field that persists in live HTML after source cleanup means the build injects it.** Real case: JSON-LD published invented `openingHoursSpecification` (Mon–Sun 10:00–23:00, never approved); removing it from source changed nothing because the SPA's prerender script emits its own JSON-LD blocks (one per venue). Grep `scripts/prerender*` and build entry files for the field, not just `src/`/`index.html` — and add a repo guard test that fails on invented/unapproved schema fields (hours, phones) so it can't regress silently.
