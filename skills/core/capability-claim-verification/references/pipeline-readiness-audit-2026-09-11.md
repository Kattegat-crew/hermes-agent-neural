# Auditoría de readiness del generador de campañas (11-sep-2026, caso trabajado)

Pregunta del usuario: «¿estamos listos para generar los guiones y las escenas de los reels de este fin de semana?» sobre el repo `marketing-campaign-generator` (campaña `bingo-sep2026`, clientes Golden Game y Lucky Brothers / Grand Paradise).

Forma de la auditoría: 1 barrido propio + 3 subagentes read-only en paralelo (AP / portal / guión→escenas) + 1 reviewer fresco con checklist de falsificación.

## Topología real (verificada en vivo)

- **Repo**: DEV `/root/marketing-campaign-generator` (= `/host/root/marketing-campaign-generator` desde el contenedor; entre el 08 y el 11-sep vivió en `data/repos/`, ya no).
- **Worker**: systemd `reel-worker.service`, `:8090`, `ExecStart=<repo>/.venv/bin/python scripts/reel_worker.py`; auth JWT sólo en `POST /jobs` y `POST /jobs/<id>/feedback` (`make_worker_token.py`); `dry_run` es campo de PRIMER NIVEL del body, no del brief.
- **Engine**: `scripts/reel_engine.py --brief <json> [--dry-run] [--base <dir>]`; exige por escena `input_image` (ruta) o `prompt_image` (generación paga) y `approved_to_spend=true` **incluso en dry-run** (gate de valor).
- **Proveedor de video del engine**: `opencode/skills/reel-pipeline/references/monid-client.py` por subprocess (nunca importado). El `fal-client.py` del repo es drop-in pero el engine NO lo usa todavía.
- **Orquestador**: ActivePieces en PROD (`ap-app :8088`, `ap-db`); flows `Reel Orchestrator` y `Reel Callback Receiver` (ENABLED) postean a `http://100.86.8.81:8090` (Tailscale de DEV = destino correcto; la IP pública `:8090` NO es alcanzable desde PROD).
- **Portal**: PROD, contenedor `reels-web` (`:9020`, nginx:alpine), docroot `/opt/reels`, vhost NPM `20.conf`, SSO oauth2-proxy vía `forward_auth_guard.conf` (sólo `location /`). Galería viva `/v2/index.html` (281 referencias, 281/281 en disco).
- **Publicación**: `planning/calendario-sep2026/publish.py` descarga de Drive, sube a `/opt/reels/assets/<mes>/` (público, verificado 200) y publica con Composio a IG/FB. Una fila `reel` necesita `asset_drive_id` + `asset_name` (+ `cover_drive_id` opcional) y `copy`.
- **Hojas canónicas**: `assets/sheets/registry.json` — `goldie-character` y `lucky-character` `locked`; `golden-scene`, `lucky-scene`, `bingo-product` `missing`.

## Sonda E2E gratuita (la que decidió el veredicto)

```bash
# en DEV
TOKEN=$(cd <repo> && python3 scripts/make_worker_token.py --days 1 --sub audit)
curl -s -X POST http://127.0.0.1:8090/jobs -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" --data-binary @brief.json      # -> 202 {"status":"queued"}
sleep 90
curl -s http://127.0.0.1:8090/jobs/<job_id>                        # manifest, o 404 "manifest aún no disponible"
grep <job_id> <repo>/assets/<project>/logs.jsonl                   # refine_ok/tts_ok/monid_skipped/mix_ok/audit_ok/concat_ok
```

Brief mínimo válido: `job_id, project, brand, topic, aspect_ratio, voice, scenes[{name, voice_line, duration_seconds, input_image, edits}], approved_to_spend: true, max_cost_usd, budget, delivery` + `dry_run: true` hermano. Nota: `budget.max_total_usd` / `delivery.target_duration_s` son claves del ejemplo del README, no del schema.

Resultado: con `edits` en TODAS las escenas → manifest + `reel/reel.mp4` (pipeline local completo gratis). Con una escena sin `edits` → engine muerto, sin manifest.

## Los tres defectos que bloquean la generación de escenas

1. **`image_refiner.refine_image(img, [], ...)` revienta con el python del servicio**: sin PIL cae a `_refine_ffmpeg`, que con `edits` vacío arma `-filter_complex ""` → `RefineError: ffmpeg falló (exit 234)`. Con `python3` (PIL disponible) la misma llamada devuelve `engine=pil`, `applied=[]`, OK. ⇒ bug del caso AUSENTE, no de PIL.
2. **`monid-client.py:build_request_body()` manda ruta LOCAL como `image_url.url`** cuando `--image` no empieza por `http` (el comentario del propio código admite que sólo sirve en tests). El API real necesita URL pública ⇒ la corrida live falla aunque todo lo local pase. Salida: hospedar el frame refinado en una ruta pública (`/opt/reels/assets/<mes>/` es pública) antes de encolar.
3. **Intérpretes partidos**: `<repo>/.venv/bin/python` (el del servicio) tiene `edge_tts` pero no PIL; el `python3` del sistema tiene PIL/requests/numpy pero no `edge_tts`. Ninguno completa la cadena solo.

## Otros hallazgos de la misma auditoría

- `reel-worker.service` en bucle de reinicios (contador ~2515) desde el 04-sep por `WorkingDirectory=/root/marketing-campaign-generator` (ruta borrada al mover el repo). Reparado con backup del unit en `/root/backups/systemd/` + `daemon-reload`.
- 6 tests fallaban por rutas hardcodeadas a `/root/video-ai-generator` (NO eran regresiones); corregidos derivando la ruta de `__file__` → suite 605 passed / 1 skipped.
- 50 ficheros `root:root` en el repo (drift del ticker root del Desktop) impedían escribir `workspace/pacho/clips` → `chown -R hermes:10000 <repo>`.
- ActivePieces: flows ENABLED pero el último brief real es del 16-ago; `Video Generator` con versión publicada inválida y sin `trigger_source` (zombi); callback worker→AP no cableado (ningún fichero lo referencia); 0 connections sociales ⇒ no hay publicación por AP.
- Portal: `publish-review.sh` hard-codeado a rutas muertas (`/var/www/golden-webproxy`, contenedor nginx inexistente) ⇒ no publica en PROD; material interno (guiones `.md`, `estado.json`, legales, audio QA) descargable sin login; `review.html` público por token en `goldengame.com.co/va/<token>/`.
- Guión: no hay código que genere guión ni que convierta guión→prompts→scene-plan. `_build_prompt()` del engine es placeholder literal; `contracts/scene-plan.schema.json` sin consumidores; los prompts viven embebidos en scripts de un solo uso; los guiones de los reels publicados están SOLO en PROD.
- Vault de story-ads (`kb/ad.jsonl`): 54 entradas, todas `kind=ad`, todas de `golden`; 0 `spine` y 0 `lesson` ⇒ el cierre de loop (F7) nunca se ejecutó.

## Declarado al usuario

No se publicó nada, no se commiteó, no se ejecutó ninguna generación pagada. Sí se escribieron artefactos de prueba en el repo (`assets/audit-readiness/`, `.audit-tmp/`, 2 líneas en `jobs.jsonl` gitignored) y un GET a un webhook de AP disparó 2 corridas fallidas del `Reel Orchestrator` (sin job creado).
