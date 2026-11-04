# Primera corrida real de content-intel (04/09/2026)

Análisis de campaña desde 15/08 (Golden, primer reel Goldie) y 21/08 (Lucky, primer reel Lucky).

## Media descubiertos

**Golden** — IG user id `40006158832316994` (13 media, 69 followers), FB page `820898971112738`.
**Lucky/Paradise** — IG user id `27571270162548342` (85 media, 273 followers), FB page `765896786617957`.

Método IG: `INSTAGRAM_GET_USER_INFO --account <word_id>` devuelve `data.id` correcly numérico.
`'me'` y el `ig_user_id` guardado en memoria fallan con 400 "object does not exist".

## Piezas registradas (12) y sus views reales

| brand | campaña | formato | IG media_id | IG views | FB media_id | FB views |
|---|---|---|---|---|---|---|
| golden | goldie-intro | reel | 17982546792065612 | 211 | 820898971112738_122143251015100778 | 230 |
| golden | bingo-sep2026 | reel | 18203464711373069 | 189 | 820898971112738_122144718933100778 | 191 |
| golden | bingo-sep2026 | post | 18135376444535152 | 58 | 820898971112738_122145053805100778 | 6 |
| lucky | lucky-intro | reel | 18028308344847219 | 287 | 765896786617957_122144912661096603 | 50 |
| lucky | bingo-sep2026 | reel | 18101309792360069 | 169 | 765896786617957_122145825231096603 | 82 |
| lucky | bingo-sep2026 | post | 18128009821750155 | 97 | 765896786617957_122146167489096603 | 69 |

## Features de los reels finales (faster-whisper `base`, HF_HOME cacheado)

- **Goldie** (goldie-reel-final.mp4, 20.19s, 720x1280, 24fps): LUFS -25.4, bandas {bass 38, mid 56, treble 6}, **46 palabras, 2.49 wps**, 3 silencios (3.7s), **SIN CTA**.
- **Lucky** (lucky-reel-final.mp4, 30.36s, 720x1280, 24fps): LUFS -16.6, bandas {bass 21, mid 77, treble 1}, **66 palabras, 2.21 wps**, 3 silencios (3.04s), **CTA@18.5s** ("Ven").

## Análisis (n=4 reels por marca — orientativo, no fiable)

**Golden** — reels media 205 views, engagement 2.32%, 2.49 wps, sin CTA; post media 32 views, engagement 4.31%.
**Lucky** — reel intro top 287 views; CTA presente pero tarde (18.5s).

### Veredictos clave (dato real, no intuición)
1. **CTA**: Goldie reel sin CTA; Lucky lo tiene pero a 18.5s (hooked too late). → guiones futuros: CTA <3s.
2. **Formato**: reels (~205 views) superan posts (~32 views) en Golden → priorizar reels sobre posts fijos.
3. **Engagement relativo**: posts tienen más interacción/views (4.3%) que reels (2.3%) → combinar reel (alcance) + copy con engagement.
4. **Perspectiva**: ambas cuentas son chicas (69 y 273 followers). Los números absolutos (189-287) son consistentes con eso. IG insights igualmente funcionó bajo el umbral de 1.000 followers.

## Limitación guardada

n=4 por formato es orientativo. El sistema se vuelve fiable/predictivo cuando cruce n≥10 por formato. Benchmarks se normalizan por follower (no comparar marcas entre sí).
