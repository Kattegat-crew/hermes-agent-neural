---
name: neuralcrew-campaign-content
description: "Use when writing NeuralCrew casino campaign copy."
tags: [campanas, copy, guiones, casino, coljuegos, compliance, bingo, marcas]
---

# NeuralCrew Casino Campaign Content (Colombia)

Class of work: campaign copywriting for Colombian casino brands served by NeuralCrew (Golden Game, Lucky Brothers / The Grand Paradise Club) — reels scripts, posters, stories, WhatsApp copy — under Coljuegos promotional-games compliance.

## Fuentes de verdad (check in THIS order, never from memory)
1. **`campaign.yaml`** per brand (the contract: mecánica, sedes, paleta, montos) — `profiles/roshi/workspace/campaigns/`.
2. **T&C entregables** (`.docx` in `entregables/`, highest version number wins) — these override any plan/markdown when they disagree (e.g. horarios).
3. **Plans** in `plans/` (PLAN-ENTREGABLES, investigación) — context, but stale on details.
4. Never state a fact (hora, monto, mecánica) that is not in 1–2; if absent → `[PENDIENTE DE CONFIRMAR]`.

## Verifying claims inside .docx contracts (no converter needed)
Before "correcting" a deliverable based on someone's summary in chat, grep the actual contract text:

```python
from zipfile import ZipFile; import re
t = ZipFile("entregables/TC_..._v3.docx").read("word/document.xml").decode("utf8")
t = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", t))   # plain text
for kw in ("hora", "p.m.", "escalon", "jornada"):    # print ±120-char windows around each hit
    ...
```
Gotcha seen live: `"revisión 24/08/2026 — hora 5:00 p.m."` (doc-review timestamp) vs `"en el horario de 5:00 p.m."` (event start). Distinguish metadata timestamps from event times by reading the surrounding clause, and quote the exact phrase back to the room when reporting.

## Guión v2 structure (Admin-validated) — reels 30s 9:16
① dato curioso del pueblo (hook 0-3s) → ② conexión casino → ③ bingo con **premio TEMPRANO** (12-20s) → ④ CTA + legal.
- Prize number must appear as **on-screen overlay from second 0** (~40% of viewing is sound-off; the frame must read without audio).
- Recurring tension device for bingo promos: **"¿CAERÁ CON 53 O MENOS? 👀"** + animated acumulado counter — the ≤53-balotas rule is a narrative cliffhanger ("Will It Hit?" = highest completion-rate format), not fine print. Shared visual resource with posters/stories.
- Episodicity: same opening/formula per pueblo, only the town changes — campaign is a SERIES, not 8 one-off scripts.
- "Escalonado" mechanic (batches of 15-20 balotas/hora, doors open "desde las X") must read as **"llegue cuando pueda"** — never a fixed-arrival-time CTA.
- Sell the evening as a plan (comida/bebida/música/ambiente), not only "venir a ganar".
- Later weeks: real winner clips (UGC, 15s, with consent) outrank acted scripts — design the cycle to produce one per viernes.

## Compliance (hard rules, Colombia)
- Every piece footer: **"+18 Juego responsable | Regulado por Coljuegos"** — never dropped, never shortened.
- Mechanics copy must match T&C exactly (montos, fechas, empate, cartón gratis condicionado a "cliente jugando en el momento", acumulado independiente por local).
- Prefer the contract's own wording ("desde las 5PM / a partir de") over invented schedules.

## Tone & sensitivities (Colombia pueblos)
- Hooks need **verifiable, sourced** town facts (Wikipedia / Archivo General de la Nación / prensa regional); retórica sin dato = rejected in review. If a fact's attribution is folklore, say "dicen que…".
- **Agua de Dios**: the lazareto/leprosy history is a real community wound — reference water (Los Chorros), music (Luis A. Calvo), "Ciudad de la Alegría y la Memoria"; NEVER the leprosy as joke or hook.
- Voice: how people actually talk — short sentences, town-converso rhythm, no brochure adjectives; close each script with a memorable pueblo/suerte double-meaning line.
- Avoid AI-sounding words; run copy past humanizer/anti-slop before delivering.

## Group-chat delivery etiquette (NeuralCrew rooms)
- When context changes mid-campaign (e.g. horario 7PM→5PM): patch the deliverable FILE, then report what changed and hand shared visual cues to the design teammate explicitly.
- Cite the file path of the doc you updated so others can review it.

See `references/bingo-millonario-sep2026.md` for the current campaign's verified constants and artifact map.
