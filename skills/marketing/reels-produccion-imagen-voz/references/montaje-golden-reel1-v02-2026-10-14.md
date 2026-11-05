# Montaje Golden Reel 1 V02 — receta verificada (14-oct-2026)

Contexto: V01 del reel se montó con voz ralentizada (fit_voice clamp 0.5×) y sin música. El Admin pidió: voz a ritmo natural, música colombiana pegajosa, más ritmo y rótulos menos genéricos. Resultado: V02 verificada y publicada en el portal.

## Entregable
- `f22c5600-GG_REEL_TERROR_01_V02.mp4` → https://reels.neuralcrewlabs.com/assets/2026-10-halloween/golden/reel-01/ (16,5 s, 720×1280, 24 fps)
- Portal: https://reels.neuralcrewlabs.com/#golden-2026-10-halloween-r1
- Código versionado: `scripts/golden_reel1_montaje/` del repo m-c-g (movido fuera de assets/golden-* que está git-ignored). Commit eb831af.

## Cadena de montaje (montar_reel1_v2.py)
1. **Voz**: `refit_natural.py` re-calibra las 4 frases con atempo>=1.0 (solo acelerar; el fit_voice original bajaba hasta 0.5× para calzar el labial nativo → lentitud audible). Salidas por escena en `montaje/voz/`.
2. **Música**: `generar_musica.py` → ElevenLabs POST `/v1/music` con key del .env del repo. REQUIERE permiso `music_generation` en la API key (el Admin lo habilitó el 14-oct tras un 401 missing_permissions; sin él no cobra). Prompt: cumbia colombiana ~106 BPM, 22 s. Salida: `montaje/musica/musica.mp3`.
3. **Rótulos**: textos por escena en `scripts/golden_reel1_montaje/rotulos/s*.txt` (líneas separadas = entrada escalonada), fuentes de marca `assets/fonts/` (DM Serif Display regular + DM Sans Bold). Pasada 2: drawtext con fade y enable por tiempo.
4. **Overlays (pasada 2b separada)**: murciélago, destellos y placa CTA generados con PIL (`generar_assets.py` → RGBA). COORDENADAS FIJAS calculadas en Python — las expresiones `(W-w)/2` / `h*0.565` en la cadena combinada NO dibujaban nada y ffmpeg no avisaba. Sin fade alpha en RGBA (los dejaba invisibles): aparecer con enable.
5. **Mezcla**: voz + música con ducking; concat de escenas con disolvencias.
6. **QA**: vision_analyze sobre frames extraídos del MP4 final (verificar rótulos + placa CTA visibles), ffprobe de pistas y duración.
7. **Portal**: subir MP4 con prefijo sha8 y actualizar fragmentos r1-*.html + índice (ver skill portal-reels-ops para deploy).

## Lecciones de la sesión
- La lentitud no era del clip sino del fit: calzar voz al labial nativo comprime/estira la toma; para reels, voz natural + clips conformados a la voz.
- Los 2 bugs de ffmpeg fueron silenciosos: el pipeline reportaba OK sin overlays. Única detección confiable: QA visual por frames del MP4 FINAL, no confiar en exit code.
- El gate MCP de la key ElevenLabs aplica también a música: sin el permiso, el flujo debe continuar sin música (fallback) y declararlo, nunca improvisar con otra fuente.
- Pendientes que quedaron: aprobación V02 por el Admin; decisión copas en S3 (personajes Pixar con bebidas = riesgo pauta Meta); push de eb831af.
