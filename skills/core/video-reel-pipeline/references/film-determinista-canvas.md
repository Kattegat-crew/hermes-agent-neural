# Film determinista canvas + puppeteer (launch-proof)

Motor de film 9:16 (1080×1920) verificado en producción (sesión 11-nov-2026, launch-proof:
`/opt/hermes-agent-data/cache/scratch/launch-proof/`, MP4s focus_v3..v6 entregados) y
re-inventariado 12-nov. Reproducible por cualquier agente sin IA de video paga.

## Cadena

1. **Escena:** `film/index.html` + `film/scene.js` — canvas 2D a 1080×1920 con utilidades
   (gradientes, partículas nieve/bokeh, glow radial, grano, Ken Burns sobre plates).
2. **Fuentes embebidas:** `film/fonts.css` con @font-face base64 — DM Serif Display
   (titulares) + DM Sans (pie/legal). 8 bloques, ~271 KB. Reutilizable tal cual.
3. **Render:** `render.js` con puppeteer-core + CHROMIUM_BIN, ~18-20 fps de frames; frame
   count exacto = `duración_s × fps_target` (p.ej. 24 s × 30 fps = 720).
4. **Voz:** ver [voz-es-coste-cero-nan.md](voz-es-coste-cero-nan.md). **El cue sheet se
   cuelga de la voz** (whisper word-level o ElevenLabs /with-timestamps), nunca al revés:
   se sintetiza primero, se miden duraciones reales y de ahí salen los tiempos de escena.
5. **Música:** cama ElevenLabs `/v1/music` (gated) o procedural numpy/ffmpeg (campanas+
   pad) a coste cero. NUNCA reutilizar camas de campañas anteriores (Halloween etc.).
6. **Mezcla:** ffmpeg con ducking por sidechain (voz protegida) + `loudnorm` a −16 LUFS.
7. **QA:** escalera `qa-video-con-modelos` (qa_gate.py determinista → glm5.3-flash →
   qwen3.8-max árbitro). Entregar solo tras QA verde.

## Paralelismo y coste
- Motor compartido (index/scene/render/mix) + un `scene.js` por marca: N films corren como
  procesos background simultáneos (~40-45 s de render cada uno), no como subagentes.
- Coste típico del corte completo: $0 en generación (voz kokoro + música procedural +
  render local); solo el QA con modelos gasta centavos.
- Artes de personaje con fondo integrado (no transparente): usarlos como «plate» dentro de
  marco con viñeta/parallax; NO intentar recorte perfecto de pompón/flecos/glow.

## Lección operativa
Declarar duración de producción con desglose medido (render + mezcla + encode + QA), no
con estimación redondeada; y cada regeneración paga gate aparte si consume saldo.
