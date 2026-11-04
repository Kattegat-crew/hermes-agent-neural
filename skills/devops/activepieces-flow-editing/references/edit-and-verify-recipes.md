# Recipes — AP flow editing, run verification, Google-Maps profile links

Session date: 2026-08-25. Prod VPS `169.58.189.222` (SSH key `/opt/data/.ssh/id_ed25519`).

## Prod layout (self-hosted ActivePieces)

- Containers: `ap-app` (UI/API, port 8088), `ap-worker` (executor), `ap-db` (postgres, db `activepieces`), `ap-redis`.
- Webhook servers (lead capture): `webhook-gateway` (Golden, :3099) and `webhook-paradise` (Paradise, :3100) in `/opt/docker/webhook-gateway/`.
- The webhook `notifyActivePieces` post to the AP webhook URL `http://<AP_IP>:8088/api/v1/webhooks/<flowId>`.
- Flows (written in `flow_version.trigger`):
  - **Golden** published version `3oGBil1naEsVErmbBz6KY` — steps: "Tarjeta VIP al Cliente" (email to lead), "Notificacion Interna" (admin), "Guardar lead en Google Sheets".
  - **Paradise** published version `jIrDwFPupZwZJ9Z1y97YT` — steps: "Enviar bono al lead" (email), "Aviso nuevo cliente a admin", "Guardar lead en Google Sheets".

## Email template location

`flow_version.trigger` is a JSON tree: `trigger` → `nextAction` → `nextAction` … Each step has `displayName` and `settings.input`. The email body is at `settings.input.body`:
- sometimes a dict `{ "html": "...", "text": "..." }`
- sometimes a plain string (the HTML directly).

Walk the tree to find the step by `displayName`, read/write `body.html`. Placeholders are `{{trigger.body.<field>}}`.

## Reading / writing flow_version.trigger via SQL

```bash
# read
docker exec ap-db psql -U postgres -d activepieces -tAc \
  "SELECT trigger::text FROM flow_version WHERE id='3oGBil1naEsVErmbBz6KY'" > /tmp/golden.json
```

Write back (JSON with single quotes must have `'` → `''`):
```python
import json, subprocess
def psql(sql):
    return subprocess.run(["docker","exec","ap-db","psql","-U","postgres","-d","activepieces","-tAc",sql],
                          capture_output=True, text=True).stdout
t = json.loads(psql("SELECT trigger::text FROM flow_version WHERE id='<vid>'"))
# ... edit nested body.html ...
esc = json.dumps(t, ensure_ascii=False).replace("'", "''")
psql(f"UPDATE flow_version SET trigger='{esc}'::jsonb, updated=now() WHERE id='<vid>'")
```

Do NOT wrap a `$json$...$json$` dollar-quoted string in single quotes (`'$json$..$json$'::jsonb` is invalid). Pass SQL as a psql **argument**; piping big JSON via `psql -i` stdin was unreliable.

## trigger_source alignment (fixes stale template / unstable runs)

```bash
# see what the webhook currently resolves to
docker exec ap-db psql -U postgres -d activepieces -tAc \
  "SELECT \"flowVersionId\" FROM trigger_source WHERE \"flowId\"='<id>'"
# point every row to the published (existing) version
docker exec ap-db psql -U postgres -d activepieces -c \
  "UPDATE trigger_source SET \"flowVersionId\"='<published_vid>' WHERE \"flowId\"='<id>'"
# ensure publishedVersionId matches
docker exec ap-db psql -U postgres -d activepieces -tAc \
  "SELECT \"publishedVersionId\" FROM flow WHERE id='<id>'"
# restart BOTH engines
docker restart ap-app ap-worker
```

## Verifying a run actually used your edit + its output

```bash
# which version ran
docker exec ap-db psql -U postgres -d activepieces -tAc \
  "SELECT \"flowVersionId\", status FROM flow_run WHERE \"flowId\"='<id>' ORDER BY \"startTime\" DESC LIMIT 1"

# extract the run's real output (compressed in `file`)
RID=$(... SELECT id FROM flow_run WHERE "flowId"='<id>' ORDER BY "startTime" DESC LIMIT 1)
FID=$(... SELECT "logsFileId" FROM flow_run WHERE id='$RID')
docker exec ap-db psql -U postgres -d activepieces -tAc \
  "SELECT encode(data,'base64') FROM file WHERE id='$FID'" > run.b64
base64 -d run.b64 | zstd -d > run.json
python3 - <<'PY'
import json
d=json.load(open("run.json"))
for n,st in d["executionState"]["steps"].items():
    out=st.get("output") or {}
    if isinstance(out,dict) and "accepted" in out:
        print(n, st.get("status"), "->", out["accepted"])
PY
```

## Timing / timezone

- AP returns `200 {}` immediately; the run is created ~20–30 s later (sandbox install/build). Wait ≥30 s.
- `startTime` is UTC. Use `WHERE "startTime" > now() - interval '10 minutes'` (literal timestamps are a timezone trap).

## notifyActivePieces "fetch failed"

```bash
# reproduce from inside the webhook container (must reach AP):
docker exec webhook-paradise node -e '
  fetch(process.env.ACTIVEPIECES_WEBHOOK_URL,{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({name:"t",email:"t@t.co"})}).then(r=>console.log(r.status)).catch(e=>console.log("ERR",e.message));'
```

Harden `notifyActivePieces` in `webhook-server.js` / `webhook-server-paradise.js`: timeout 8s→15s, N retries w/ backoff (e.g. `AP_NOTIFY_MAX_RETRIES=4`, sleep `1000*attempt`). Validate `node --check`, then `docker restart webhook-gateway webhook-paradise`.

## Python -c over SSH breaks (use a file)

Inline `python3 -c "..."` inside an `ssh '...'` heredoc keeps breaking on quotes/backslashes. Write the script to a file locally, `scp` it, run `python3 /tmp/script.py` on the host.

## Google Maps "profile of the local" link

To link a button to the local's **Google Business profile** (not a generic search), extract the place URL:
`web_extract("https://www.google.com/maps/search/?api=1&query=<casino>+<sede>")` returns entries like:
`https://www.google.com/maps/place/<Name>/data=!4m7!3m6!1s0x<hex>:0x<hex>…` — the `0x<hex>:0x<hex>` is the place id; the address and hours are in the extracted text.

Caveat: not every business has a live ficha. e.g. "Casino Golden Game Tunja" returned OTHER casinos, while "The Grand Paradise Club Casino Chiquinquira 1" (Cra. 9 #17-51) and "…2" (Cra. 8 #17-40) both had fichas. Verify each before wiring the link.
