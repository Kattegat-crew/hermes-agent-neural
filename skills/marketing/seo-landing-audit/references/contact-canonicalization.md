# Brand-contact canonicalization & campaign changeover (proven recipe)

Session-proven workflow (Nov 2026): unifying WhatsApp contact numbers across Golden Game / Paradise landings + tooling.

## Canonical numbers (source of truth)
- Goldie (Golden Game): +57 304 356 1269 → `573043561269`
- Lucky (Paradise): +57 311 492 5556 → `573114925556`
- Kept in `brain/entities/golden_game.md` / `lucky_brothers.md`; landings + gates read from there.

## 1. Inventory before touching anything
Grep ALL variants across every brand repo (landing, prerender, seoMeta, T&C borradores, llms.txt, tooling footers):

```bash
grep -rEn '316 ?691 ?0728|316 ?690 ?9310|601 ?384 ?3934' --include='*.{html,js,ts,json,md}' \
  /opt/<repo> | grep -v node_modules | grep -v dist/
```

Normalize-to-digits comparison is mandatory: `re.sub(r'\D','',s)` catches `316-691-0728` style separators that literal greps miss.

## 2. Scope guard
Check `brain/entities/` before declaring a number obsolete — the same digits can legitimately belong to another entity (e.g. band Bendabal uses 316 691 0728 as its own WhatsApp). Replace ONLY inside the brand's repos.

## 3. Replacement sweep (worktree per front)
- Golden: footer, contacto, 3x terminos, politica-datos, juego-responsable, seoMeta, llms.txt, 7-sede shell, JSON-LD LocalBusiness/Organization (E.164 real: `+573043561269`).
- Paradise: same surfaces + prerender of sedes + PoliticaDatos (remove "teléfono fijo" wording when the fixed line is retired; visible number keeps `+57 ` prefix).
- Tooling: qa_landing gate, carousel link builder (wa.me links must be `wa.me/<digits>`, never `wa.me/<domain>` — invalid link class), campaign report footers, T&C borradores.

## 4. Guard tests (both repos)
`tests/phoneCanonical.test.mjs`: assert every HTML fixture contains the canonical number and ZERO old variants (digit-normalized scan). RED first (fixture with old number), then GREEN.

Gate check (S21 in qa_landing.py): placeholder scan + obsolete-phone scan with digit normalization; scan only `[...]` bracketed placeholders to avoid false positives on phrases like "todo el día".

## 5. Deploy + live verification
Coolify deploy per landing, then verify in production (the only evidence that counts):

```bash
# 22 sitemap URLs: 200 + zero old digits
curl -s https://<domain>/sitemap.xml | grep -oE 'https://[^<]+' | while read u; do \
  code=$(curl -s -o /tmp/p -w '%{http_code}' "$u"); \
  hits=$(python3 -c "import re;print(len(re.findall(r'316 ?691 ?0728|3166909310|6013843934', re.sub(r'\D',' ',''.join(re.findall(r'316[\s-]?691[\s-]?0728|316[\s-]?690[\s-]?9310|601[\s-]?384[\s-]?3934', open('/tmp/p').read())))))")" 2>/dev/null || echo err); \
  echo "$code $hits $u"; done

# canonical wa.me links
curl -s https://<domain>/ | grep -oE 'wa\.me/[0-9]+' | sort | uniq -c
```

## 6. WhatsApp legitimacy audit
- `curl -s -o /dev/null -w '%{http_code}' https://wa.me/573043561269` → 200 (redirects to api.whatsapp.com/send = number real).
- Business Account status (ficha "Golden Game Casinos" / "The Grand Paradise Club Casino") verified externally — cannot be proven from HTTP alone; state that in the report.

## 7. Seasonal changeover (same session: Halloween → Aguinaldo)
Event routes carry the old season in: og:image, twitter:image, `<link rel=preload as=image>`, meta keywords, JSON-LD `Event` (name, description, startDate/endDate). Sweep raw HTML for season tokens (`halloween`) case-insensitive; replace asset with new 1200x630 og and keep URLs ABSOLUTE.

## Gotcha log
- og:image relative (`/assets/...`) silently breaks every link preview — Meta requires absolute; also fix JSON-LD `image`.
- Never touch unrelated repos that share digits (legit contact elsewhere).
- Event-page title/og fixes need BOTH the seoMeta source and the page's own Vite entry (e.g. `eventos.html`) — either alone leaves stale output in one surface.