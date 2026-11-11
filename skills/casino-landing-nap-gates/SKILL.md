---
name: casino-landing-nap-gates
description: Use when editing sedes or JSON-LD in casino landing repos.
version: 1.0.0
author: ragnar
license: internal
metadata:
  hermes:
    tags: [seo, nap, json-ld, gates, casino, git]
    related_skills: []
---

# Casino Landing NAP Gates

## When to Use

- Any edit to sede addresses, vías, horarios, titles or JSON-LD in `golden-game-landing` or `paradise-casino-landing`.
- Running or interpreting the `napSedesCanonico` / `seoGeo` / `prerenderSeo` gates, including contradictions between them.
- End-of-session multi-repo git harvest and deciding what to do with uncommitted deletions.

The casino landing repos (`/opt/golden-game-landing`, `/opt/paradise-casino/paradise-casino-landing`) pin canonical business data with behavior gates in `tests/` (`napSedesCanonico.test.mjs`, `seoGeo.test.mjs`, `prerenderSeo.test.mjs`). Run them with `node --test tests/<gate>.test.mjs` before and after any data edit.

## Canonical data propagation (all surfaces, not one)

A sede/vía/horario change is only complete when propagated to EVERY published surface:

- `src/data/eventsData.js` (campaign copy)
- `src/pages/Terminos.jsx`, `TerminosAguinaldo.jsx`, `Contacto.jsx`
- `src/components/Footer.jsx` (domicilio labeled "Domicilio principal")
- `src/utils/seoMeta.js` AND the matching static `.html` `<title>` — these must stay identical
- `server/knowledge.js`, `public/llms.txt`
- `index.html` JSON-LD

Use the atomic multi-replace pattern (read → count occurrences → tempfile in same dir → `os.replace`) instead of sequential sed; report any occurrence count of 0 as a miss, never silently.

## JSON-LD structure (invariant)

The cadena has 5 sedes, so the domicilio fiscal must live in an **Organization** block (with `legalName` + `taxID`); the brand **LocalBusiness** block is separate and carries `openingHoursSpecification` (10:00–03:00) and `priceRange`. A LocalBusiness carrying the domicilio fails the NAP gate.

## Gate contradiction arbitration

Gates can contradict each other (e.g. seoGeo requires openingHours in index.html; prerenderSeo forbids them). Protocol: scope the newer assertion to its own stated intent (patch the test to match its error message, with a comment justifying it), never delete a gate, and leave any residual failure red with the contradiction documented to the owner — two gates both from recent work means the owner decides which premise retired.

## Repo harvest (end of session)

1. Sweep each repo: `git status -sb`, `git fetch`, compare local HEAD to `git ls-remote` — 'synced' means hash equality plus clean tree.
2. **Uncommitted deletions are data loss risks**: if deleted files exist nowhere else (no other branch, no remote), restore them instead of committing the deletion. Verify with `git log --all --oneline -- <path>` before treating a deletion as intentional.
3. Never push `prod-stable` or deploy branches without explicit authorization; they are not mirrored to GitHub by default.
4. `backups/` and `dist/` are gitignored — commit gates, specs (`.specs/`) and sources only.