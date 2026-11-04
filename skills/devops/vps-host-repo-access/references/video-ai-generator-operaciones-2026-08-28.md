# video-ai-generator — estado operativo y cambios (28/08/2026)

Repo host: `/root/marketing-campaign-generator`, rama canónica `main`, worker HTTP :8090.
Detalle de acceso y patrones docker en el SKILL.md padre.

## Estado verificado en vivo (28/08)
- `reel-worker.service` activo (systemd, :8090). `GET /health` → `{"status":"ok"}` sin token.
- Flows AP `reel-orchestrator` + `reel-callback` ENABLED. **AP vive en el VPS prod `.222`**
  (169.58.189.222, contenedores ap-app/ap-db/ap-worker/ap-redis, UI :8088), NO en .250.
  Worker en .250, AP en .222 → el flow POSTea a `http://10.0.1.1:8090/jobs` (IP interna).
- Suite de tests: 501 passed / 1 skipped (27 archivos tests).
- Reel final Lucky ensamblado: `assets/lucky/reel/lucky-reel-final.mp4` (19MB) — falta audio ElevenLabs.
- Keys en `.env`: NAN_API_KEY, TOKENROUTER_API_KEY, MONID_API_KEY, FAL_KEY, ELEVENLABS_API_KEY.
  ElevenLabs además en `~/.config/akari-video/credentials.env` (chmod 600, fuente del doctor AKARI).

## JWT del worker (ACTIVADO 28/08)
- `POST /jobs` y `POST /jobs/<id>/feedback` requieren `Authorization: Bearer <token>` (HS256).
  GETs y /health sin auth. Sin token → 401; token válido → 202.
- Secret: `REEL_WORKER_JWT_SECRET` en `/repo/.env` (generado con python secrets, no openssl).
  La unit systemd NO carga .env por defecto → se agregó `EnvironmentFile=/root/marketing-campaign-generator/.env`
  a `/etc/systemd/system/reel-worker.service` (daemon-reload + restart via nsenter).
- Mintear tokens: `python3 scripts/make_worker_token.py --days 365 --sub <nombre>`
  (helper agregado a scripts/; lee el secret del .env, no lo imprime).
- El brief del POST es estricto (contracts/brief.schema.json): requiere job_id/project/
  approved_to_spend/max_cost_usd/scenes/budget/delivery; escenas `scene-0N`; `false` como
  booleano JSON. `scenes` es ARRAY de objetos, no un número. (El ejemplo del skill
  video-ai-generator con `"scenes": 4` está ROTO — validar antes de copiarlo.)

## Lip-sync NATIVO (Ruta 1, elegida por el Admin) — IMPLEMENTADO 28/08 (commit 50417e0)
ElevenLabs sintetiza la voz por escena → se pasa como `audio_urls` a Seedance 2.0
`reference-to-video` con `generate_audio:true` → boca animada sobre esa pista exacta.
NO post-proceso. Restricciones: audio total ≤15s/clip; requiere ≥1 imagen/video de
referencia; la pista sale re-interpretada (~95% fiel, test A/B de oído en 1 escena).
**Ya hecho**: `scripts/fal-client.py --mode reference2video --model r2v` (o `r2v-fast`)
con `--image` repetible (≤9) y `--audio` (≤3, MP3/WAV ≤15s combined, ≤15MB c/u),
preflight de URLs image/* Y audio/* antes de POSTear, validaciones (audio sin imagen →
error, modelo no-r2v → error). Endpoint: `bytedance/seedance-2.0/reference-to-video`
(fast: `.../fast/reference-to-video`). Prompt con refs `@Image1`/`@Audio1`.
Tarifa estimada $0.014/s (r2v) → clip 5s ≈ $0.07, NO $0.5. Verificado en dry-run E2E;
regresión image2video intacta (24 tests fal passed). **monid-client.py sigue solo
image2video** — si se quiere lip-sync vía Monid hay que extenderlo igual.
⚠️ El gate humano `.fal-gate.json` (creado SOLO por el Admin, TTL 6h) sigue siendo
prerrequisito para cualquier run real de fal.
Schema completo del endpoint (límites por campo, ejemplo talking-head oficial, nota de
que NO hay 1080p en r2v y que el WAV de ElevenLabs exige publicarse a URL /va/ antes
del run): `references/seedance-r2v-fal-schema.md` en esta misma skill.

## Voces ElevenLabs del Admin (verificadas 28/08 — renombradas por el Admin después)
- **CONFIGURADAS EN EL PIPELINE (commit 2bad8da → main)**: `BRAND_VOICES` en
  `scripts/reel_engine.py` mapea proyecto→voice_id: `golden → "qWWAqFomnJ99VwQLREfT"`
  (Voz-Goldie), `lucky → "U9tZtg3uJtVgXPkvosWR"` (Voz_Lucky, ex Kate).
  `_resolve_voice(brief)`: brief["voice"] > BRAND_VOICES[project] > DEFAULT_VOICE.
  `_synth_narration`: dispatch — si la voz contiene "Neural" usa edge_tts_client, si no
  elevenlabs_client (import perezoso, ya no exige la librería edge-tts al importar el engine).
- Bug histórico: el engine ignoraba brief["voice"] (siempre DEFAULT_VOICE edge-tts). Ya no.
- **Bugs fixeados en `scripts/elevenlabs_client.py`** (rotos desde 8b4678b, el cliente
  nunca se había ejecutado): (1) `_headers` mandaba xi-api-key Y Authorization a la vez →
  ElevenLabs 401 "Only one of xi-api-key and authorization headers" — dejar solo xi-api-key.
  (2) Faltaba `import tempfile` → NameError en `_to_wav`.
- QA de pronunciación con STT round-trip (sin gastar en video): sintetizar líneas →
  concatenar preview (`ffmpeg -f concat`) → `POST /v1/speech-to-text` (multipart:
  file=@mp3, model_id=scribe_v1, header xi-api-key) → comparar transcrito vs original.
  Las 4 líneas de goldie-voice-lines.json transcritas 100% fieles = voz aprobable.
  Hacer el STT con un script python (urllib multipart con boundary manual) pasado por
  stdin — curl en alpine con la key interpolada rompe el quoting fácil.
- Consultar voces: `GET https://api.elevenlabs.io/v2/voices?page_size=100` con header
  `xi-api-key` (v2 incluye `generation_time` → detecta voces recién creadas/renombradas).
  Voz Goldie = qWWAqFomnJ99VwQLREfT. NO recomendar voces por nombre "Kate" — el Admin las
  renombra; siempre listar antes de proponer.

## AP: inyección de JWT en flows + workflow `video-generator` (HECHO 28/08)
AP corre en Docker (.222): `ap-app` (:8088), `ap-db` (postgres), `ap-worker`, `ap-redis`.
Los flows NO se publican (no hay versión PUBLISHED) — AP ejecuta la versión DRAFT. Para
modificar un flow: editar la fila DRAFT de `flow_version`.

### Receta (base64 + psql -f /dev/stdin, evita el infierno del quoting)
1. Los IDs de AP son `varchar(21)` base62 (p.ej. `TiRdZ7xkbD86d2eM7B9KJ`) — NO usar
   `gen_random_uuid()` (36 chars → viola NOT NULL/length). Generar con secrets.
2. Columnas NOT NULL de `flow_version`: `connectionIds` (ARRAY), `agentIds` (ARRAY),
   `valid` (bool), `state`, `notes` (jsonb → `'{}'::jsonb`), `trigger` (jsonb).
3. El header del piece-http vive en el JSON del trigger:
   `trigger->nextAction->settings->input->headers` (ej. `{"Authorization":"Bearer <token>"}`).
4. Pasos: escribir SQL a un archivo → base64 → SSH a .222 con las keys del host →
   `echo <b64> | base64 -d > /tmp/x.sql` → `docker exec -i ap-db sh -c 'psql -U "$AP_POSTGRES_USERNAME" -d "$AP_POSTGRES_DATABASE" -f /dev/stdin' < /tmp/x.sql`.
   (No pasar SQL inline por `ssh "bash -s"` con heredoc: el quoting anidado se rompe.)
5. Workflow creado: externalId `video-generator`, displayName "Video Generator - pipeline
   completo (imagen/voz/video/lip-sync)", trigger = webhook catch → POST :8090/jobs con
   header JWT, status ENABLED. Verificado E2E: POST /jobs con su token → 202 queued.
6. Los flows de AP POSTean al worker via IP interna `10.0.1.1:8090` (no el hostname público).

## D2 cleanup (fix aplicado 28/08)
`scripts/cleanup_previews.py` ahora barre `output/<project>/reel/` con TTL_FINAL_DAYS (30d)
y salta el pseudo-escenario "reel" en el loop de versiones. Tests en
`tests/test_cleanup_reel_D2.py` (4 nuevos + 6 existentes = 10 passed).
OJO: `assets/lucky/reel/*.mp4` es entregable commiteado — no cae bajo el barrido (solo output/).

## README (ACTUALIZADO 28/08, commit 249c243 → origin/main)
Reescrito con estado real: worker JWT, ElevenLabs, flows AP + workflow video-generator,
lip-sync nativo, quickstart con token y brief completo, tabla de scripts con
`make_worker_token.py`. No volver a marcar el README como "mentiroso" sin releerlo.

## Pendientes abiertos (al cierre de sesión 28/08 noche)
- HECHO en la misma sesión: lip-sync client `reference2video` (50417e0), voz Goldie
  configurada con QA STT 100% fiel (2bad8da), README (249c243).
- PENDIENTE: test lip-sync real escena 1 Goldie — requiere (a) oído del Admin sobre el
  preview `voz/goldie-lines/goldie_preview_ES.mp3`, (b) URLs públicas /va/ del frame +
  WAV de voz, (c) `.fal-gate.json` creado por el Admin (gate humano, TTL 6h).
  Costo real del test ≈ $0.07-0.14 (tarifa r2v $0.014/s), no $0.5.
- P3b Lucky: mismo test con Voz_Lucky cuando se retome.
- `monid-client.py` sin modo reference2video (solo tiene image2video) — extender si se
  quiere lip-sync por Monid en vez de fal.
- P5a-d: Monid LIVE 1080p, restyle Flux live, overlay Akari, scene-plan desde Hermes (gated por gasto).
- P6: publishing TikTok/IG/YT (flow AP, no existe aún).
- P7: doctor AKARI roto por imports relativos (no bloquea).
- Falsos positivos de test en alpine desechable: test_review_page (playwright),
  test_security_credentials (credenciales en el host, no en el contenedor),
  test_image_refiner ffmpeg-fallback y test_output_layout (default assets, preexistente).
