# Runbook — Golden Reel 1 piloto (13-oct-2026)

Caso real ejecutado y verificado. Rutas relativas al repo m-c-g en DEV.

## Insumos
- Lote: `assets/campanas/2026-10-halloween/02-guiones/reel1-piloto-v01/`
  - `lote-preparado.json` (prompt, 6 referencias, tope USD 1, 150 chars, sin reintentos)
  - `prompt-imagen-s01.txt`, `dialogo-aprobado.txt` (150 chars exactos)
- Referencias: 5 de `assets/sheets/golden/` + 1 pendón prepress de la campaña.

## Ejecución
1. Gate validado con `gate_status(["fal","elevenlabs"])` → ok, firmado por Jonathan en terminal, expira 2026-10-14T00:05-05:00. El agente nunca escribió el gate.
2. Imagen: `fal_image_client._run("gpt-image-2", build_payload(..., images=refs), out, editing=True)` → endpoint `openai/gpt-image-2/edit`, request_id `01a13898-43e2-7fe0-b266-3f7ebaa00e01`, PNG 720×1280 (1.313.836 B).
3. Voz: `elevenlabs_client._tts_raw(key, "qWWAqFomnJ99VwQLREfT", texto_150, speed=1.0)` → HTTP 200, MP3 173.497 B, WAV 10.774059 s. Voz professional funcionó en tier Starter.
4. Output: `assets/golden-terror-reel1/s01/v1/{frames,audio,audit}/` via `output_layout.scene_output_dir("golden-terror-reel1","s01",1)`.

## QA y hallazgos
- PIL re-open confirmó 720×1280; ffprobe/ffmpeg decodificaron MP3 (44.1k mono) y WAV (pcm_s16le estéreo) sin errores; `git diff --check` limpio.
- vision_analyze: capa morada/roja, dos colmillos visibles, identidad robot y paleta correctos; DEFECTO: plano de cuerpo completo en vez de medio corto, mano parcialmente oculta. No se regeneró (lote sin reintentos) — pendiente de decisión humana.
- Cobro real de fal ausente en la respuesta del cliente; estimación base del repo ($0.0434) NO citada como cargo real.

## Entregables
- `REVISION-IMAGEN-Y-DIALOGO.html` (PNG+MP3 base64 verificados por hash contra los archivos)
- `RESULTADO.md`, `audit/{image-generation,voice-generation,resultado-lote}.json` (git-ignored)
- Handover en `PROJECT_MEMORY.md` con backup `.bak` previo; sin commits.
