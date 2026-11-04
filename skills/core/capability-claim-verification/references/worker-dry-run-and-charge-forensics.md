# Sonda E2E gratuita contra un worker HTTP + forense de gasto

Caso: `marketing-campaign-generator` en DEV (worker `reel-worker.service` en `:8090`, engine
`scripts/reel_engine.py`), 11-sep-2026. Objetivo: probar la ruta real de producción (AP → worker →
engine) sin gastar un centavo, y demostrar después que un escape a live no costó nada.

## 1. Payload que NO gasta

`dry_run` es **campo de primer nivel** del body del worker, no parte del contrato del brief:

```bash
TOKEN=$(cd <repo> && python3 scripts/make_worker_token.py --days 1 --sub <sub>)
curl -s -X POST http://127.0.0.1:8090/jobs \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" \
  --data-binary @- <<'JSON'
{
  "job_id": "audit-dryrun-01",
  "project": "audit-readiness",
  "scenes": [
    {"name": "scene-01", "voice_line": "...", "duration_seconds": 5,
     "input_image": "/ruta/abs/a/un/png.png", "edits": [{"type": "brightness", "value": 1.05}]},
    {"name": "scene-02", "voice_line": "...", "duration_seconds": 5,
     "input_image": "/ruta/abs/a/un/png.png", "edits": [{"type": "contrast", "value": 1.05}]}
  ],
  "approved_to_spend": true,
  "max_cost_usd": 3.0,
  "budget": {"currency": "USD", "max_total_usd": 3.0},
  "delivery": {"target_format": "1080x1920", "target_duration_s": 10},
  "dry_run": true
}
JSON
```

Detalles que importan:

- `approved_to_spend: true` es **gate de valor** (el engine lo exige incluso en dry-run). No es
  autorización de gasto: en la ruta live de los clientes sin `spend_gate` (Monid/NaN) no frena nada.
- **Omitir `dry_run` = corrida LIVE.** Sin default seguro. Verifícalo SIEMPRE en
  `assets/<project>/logs.jsonl` → `job_started {"mode": "dry_run"|"live"}`.
- Cada escena necesita `input_image` (ruta local) o `prompt_image` (generación paga). El engine
  aborta sin una de las dos.
- Escribe artefactos en el repo (`assets/<project>/`, `jobs.jsonl` gitignored) → decláralo y
  bórralos al terminar (`rm -rf assets/audit-readiness .audit-tmp`; `git status` limpio).

## 2. Qué prueba el éxito

Con `dry_run: true` y `edits` en TODAS las escenas, el job recorre
`refine → tts → monid_skipped → mix → audit → concat` y termina en:

- `assets/<project>/version-manifest.json` con una entrada por escena (`status: dry_run`,
  `cost_usd: 0.0`, `simulation: true`), `total_cost: 0.0`
- `assets/<project>/reel/reel.mp4`
- `logs.jsonl`: `job_started` … `concat_ok` … `job_completed`

El último evento registrado es el **punto de ruptura**. Un job que muere antes de `job_completed` no
crea manifest (`GET /jobs/<id>` → 404): eso se lee como «el job desapareció», no como «el engine murió».

## 3. A/B del input sospechoso

Para localizar la causa sin arqueología de logs (el worker trunca el stderr del subproceso a ~300
chars): corre dos veces el mismo job cambiando UNA variable. Caso real: escena con `edits=[]` →
ffmpeg construye `-filter_complex ""` → `Invalid argument` → **exit 234**; con `edits` presente, el
mismo job completa. El defecto es «campo opcional por ítem ausente», no el proveedor.

## 4. Forense de gasto cuando la corrida se escapa a live

Si `logs.jsonl` dice `mode: live`, la pregunta «¿me costó dinero?» se responde con el historial del
proveedor, no con tu log:

```bash
set -a; . <repo>/.env; set +a
curl -s -H "Authorization: Bearer $MONID_API_KEY" "https://api.monid.ai/v1/runs?limit=25" \
 | python3 -c 'import json,sys
for r in json.load(sys.stdin)["items"]:
    print(r["runId"], r["createdAt"], r["status"], r["endpoint"], r["cost"])'
```

Evidencia de cero cargo: **ninguna corrida con la fecha del intento** (en el caso real, la última
corrida era de 3 días antes) + carpeta `video/` vacía + ausencia de sidecar `.runid`
(`monid-client.py` lo escribe solo al completar, así que su ausencia NO basta por sí sola — el
historial sí). Endpoints `/v1/credits|/balance|/usage|/account` → 404.

## 5. Qué reportar

- Veredicto: la ruta real funciona hasta X y muere en Y, con el evento exacto de `logs.jsonl`.
- El escape a live, en la misma respuesta: causa (campo omitido), evidencia de cargo $0, y qué se
añade para que no vuelva a pasar (gate físico en el choke point del POST de cada cliente).
- Los artefactos escritos y su limpieza (`git status` limpio al cerrar).
