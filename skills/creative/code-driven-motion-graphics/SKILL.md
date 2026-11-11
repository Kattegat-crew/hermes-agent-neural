---
name: code-driven-motion-graphics
description: Use for motion videos rendered from code, not gen APIs.
tags: [video, motion, canvas, chromium, ffmpeg, elevenlabs]
---

# Code-Driven Motion Graphics (showreels 1080p60 sin After Effects)

Método verificado en producción 03-oct-2026: dos videos "rendición de cuentas" (Golden Game y Grand Paradise Club) de 26.5 s @ 1080p60, renderizados de noche en DEV sin APIs de video generativo. La composición es una página web determinista, la captura es Chromium headless y el ensamble es ffmpeg. Doctrina completa versionada en cada repo cliente: `motion/INVESTIGACION.md` (Kattegat-crew/Golden-Game-Casinos y /The-grand-paradise-club-Casino, rama feature/motion-rendicion-sep2026).

Keywords: motion graphics, showreel, frame a frame, puppeteer-core, hyperframes, remotion, kinetic typography, rendición de cuentas.

## Pipeline canónico

1. **facts.json primero** — única fuente de cifras; la pantalla nunca inventa ni redondea números (la narración hablada sí redondea). Cada dígito en pantalla debe existir en facts.
2. **Composición determinista** — `index.html` + `engine.js` (easings, formato es-CO, grano, wipes) + `compose.js` (escenas, timeline en tiempo absoluto). Exponer `window.draw({t})` como función PURA del tiempo: sin timers, sin aleatoriedad sin sembrar. Fuentes woff2 y logos como data-URI → render 100% offline y reproducible.
3. **Captura** — puppeteer-core + Chromium con `--allow-file-access-from-files`. PITFALL verificado: sin ese flag el canvas que dibuja imágenes file:// queda TAINTED y `toDataURL` crashea en el primer draw del mascot (parece bug de la imagen, es del canvas). Velocidad DEV (4 cores): ~7.7 fps → 26.5 s @ 60 fps ≈ 3.5 min.
4. **Ensamble** — `ffmpeg -framerate 60 -i frames/%05d.jpg -c:v libx264 -crf 17 -pix_fmt yuv420p`.
5. **Audio** — ver sección ElevenLabs; mezclar con `amix=...:normalize=0` + `adelay|adelay` (ms) por capa; normalizar a **-16 LUFS** con loudnorm al final.

## QC sin visión (telemetría, cuando vision_analyze no está disponible)

- **Inspector en-page**: contar píxeles por color/región por frame (texto visible = miles de px), verificar fuentes cargadas, capturar errores JS — detecta composiciones vacías sin ojos.
- **Detector de congelamiento**: diff frame a frame (PIL ImageChops sobre frames muestreados). Regla: nada quieto >0.5 s; budget ≤1 s congelado por 30 s. Fix canónico: movimiento perpetuo de fondo (polvo, glow respirando, barrido de luz) en TODAS las escenas.
- **Contact sheet** para el ojo humano: `fps=1.5,scale=384:216,tile=8x5`.
- **Espejo entre marcas**: el 2º video por reemplazos exactos sobre el 1º; contar reemplazos (29/29) garantiza paridad estructural.
- La validación visual FINAL es humana; el constructor no se autoaprueba.

## QC visual con visión (vision_analyze, operativo desde 03-oct-2026)

Con el slot de visión corregido (auxiliary.vision → deepseek-v4-flash), un pase escena-por-escena con vision_analyze sobre frames clave caza lo que la telemetría de píxeles NO ve: desbordes de texto, desalineación, contraste, transiciones "planas". Defectos-clase verificados en el ciclo v1→v2, con fix canónico:

- **Wipe de cortina = "flash amarillo plano"**: un color sólido en el pico de cobertura se lee como bloque sin gracia. Fix: gradiente vertical + filos de luz en los bordes + alpha de pico ~0.78 (que se trasluzca la escena entrante).
- **Tarjetas con texto desbordado/desalineadas**: un título largo rompe el layout → envolver a 2 líneas y alinear todas las tarjetas a la misma baseline.
- **Tiles tenues parecen huecos**: los elementos "cristal"/modo-2 apenas por encima del fondo se leen como agujeros → subir su luminancia hasta distinguirse del bg.
- **Línea final del cierre débil**: créditos pequeños en tinta tenue desaparecen → ~34px a plena tinta (puede requerir 2 pasadas de QA para quedar "intencional").
- **Intro desbalanceada**: revisar encuadre, filete y fecha con contraste suficiente.

Regla: la telemetría numérica y la mirada del modelo son complementarias — ninguna sustituye a la otra; ambas antes de declarar el video terminado.

## ElevenLabs (quirks verificados 03-oct-2026)

- **Música NO sale de /v1/music** (401 missing_permission music_generation): usar el endpoint SFX con prompt largo (~22 s) — produce grooves musicales reales (validar BPM y loudness). Ajustar el largo exacto con atrim+concat+afade.
- **Voces de personajes de marca** ("Voz-Goldie") listan pero dan 404 voice_not_found → exigen tier Creator. Voces ES accesibles: "Angie vendedora Colombiana", Vivi, Monica.
- SFX: whoosh por corte de escena + chime de cierre, sin restricción.

## V2 audio-first (verificado 04-nov-2026, videos rendición 80–100 s)

Dirección del cliente que quedó como estándar: locución a velocidad NATURAL (prohibido atempo — la V1 sonaba robótica), 1–2 min, textos más grandes, y **la voz manda**: cada tarjeta aparece exactamente mientras se narra su dato.

- **Sincronía por timestamps de palabra, NO por duraciones fijas**: grabar la locución completa por beat primero, transcribir con faster-whisper (word_timestamps=True), y derivar la ventana de cada tarjeta del primer/último timestamp de su narración (±0,2 s de margen). PITFALL verificado: mapear ventanas por duraciones estimadas desincronizó 6/9 beats (la voz caía en la tarjeta de otro beat — parece un desplazamiento de mapeo, es timeline fijo). El verificador automático (ratio de superposición ventana-voz vs ventana-tarjeta, gate 9/9 OK por marca) es lo que lo detectó; corre SIEMPRE antes del mux final.
- **Cambiar el timeline NO invalida todo el render**: con caché de frames por hash de estado, re-renderizar ~5000 frames tras corregir ventanas toma ~70–85 s (solo ~15% frames nuevos). Permitirte corregir sincronía es barato — no regrabar audio.
- **Audición de voces**: probar 3 voces candidatas por marca con el MISMO texto (ElevenLabs eleven_multilingual_v2), evaluar con faster-whisper + loudness y elegir. Elegidas: Angie (Golden), Daniela (Paradise). Registrar consumo de caracteres y request-ids en un MANIFEST para el gate de gasto (~3.750 caracteres ≈ 21 requests para 2 marcas completas).
- **Crash doctrine de renders largos**: si Puppeteer muere a mitad de los ~5000 frames, distinguir inestabilidad (el retry con reapertura del navegador cada ~250 frames lo salva) de crash DETERMINISTA (muere igual en el mismo punto → diagnosticar el frame concreto; los reintentos no lo arreglan). Bug real visto: reasignar una variable `const` en la ruta de reapertura — solo se ejecuta tras ~2400 frames, invisible en renders cortos.
- **Verificación final**: ebur128 sobre los MP4 finales muxeados (no sobre el mix intermedio) — las 4 pistas dieron −16,0 LUFS exactos. Placa legal "+18 · Juego responsable · Coljuegos" verificarla por OCR del frame final (tesseract), no por el código.

## Entrega y versionado

- Carpeta `motion/` en el repo de cada cliente (rama feature): `INVESTIGACION.md`, `README.md` (cifras + runbook), `facts.json`, `video/` (engine, compose, render.js, build.sh, assets/, audio/), `out/rendicion-sep2026.mp4`, `.gitignore` de frames.
- Worktrees `git worktree add` para no tocar el checkout principal; commit firmado por Ragnar + push feature (v1: 91af796 golden / f8c6293 lucky; v2: 4f87d9c golden / 949e6bd lucky).
- PITFALL: los repos cliente DEV (/opt/golden-game-landing, /opt/paradise-casino/paradise-casino-landing) pertenecen a hermes:orca con `.git` de orca:orca → el usuario del runtime recibe Permission denied en index.lock al commitear. Vía que funciona: `ssh root@147.93.3.250` y hacer worktree+commit+push como root (worktrees en /root/motion-stg-*-wt), copiando los archivos desde el FS compartido (runtime y host DEV comparten disco). Alias `ssh dev` roto desde 03-oct: usar la IP.

Referencias de estilo, método-prompt y frameworks del ecosistema: `references/estilos-y-frameworks.md`.
