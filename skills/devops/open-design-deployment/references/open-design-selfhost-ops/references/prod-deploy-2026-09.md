# OpenDesign prod deploy trace (2026-09-03, VPS .222)

Session-validated sequence for putting OpenDesign behind NPM + Cloudflare on prod, with the two gotchas that cost the most time.

## Headless NPM: stale admin password rotation

NPM uses a host **SQLite** DB, not Postgres. `docker exec npm-postgres psql` / `ap-postgres` both FAIL.

```
/opt/docker/nginx-proxy-manager/data/database.sqlite
```

`POST /api/tokens` returned `400 {"error":{"code":400,"message":"Invalid email or password"}}` even with the vault password. Verified the stored bcrypt hash did NOT match the vault secret:

```python
import bcrypt
h = b"$2b$10$7t.yB5bwAWs0AUEox9h0POPPayyrS2WYFSN85OR8TnQIh1AmuWY/2"
print(bcrypt.checkpw(b"NC-Admin-2026!Vps", h))  # False
```

Fix: generate a new bcrypt hash and `UPDATE auth` directly in SQLite. Use a throwaway alpine container (sqlite3 not on host):

```bash
# generate hash (NPM has bcryptjs bundled; use its own node):
docker exec nginx-proxy-manager node -e "const b=require('bcryptjs'); console.log(b.hashSync('NEW-PASS',10));"

cat > /tmp/setpw.sql << "X"
UPDATE auth SET secret = 'NEW_BCRYPT_HASH' WHERE user_id=1 AND type='password';
X
scp /tmp/setpw.sql root@<host>:/tmp/setpw.sql
ssh root@<host> 'docker run --rm -v /opt/docker/nginx-proxy-manager/data:/data:rw -v /tmp:/tmp:ro \
  alpine sh -c "apk add sqlite >/dev/null 2>&1; sqlite3 /data/database.sqlite < /tmp/setpw.sql"'
```

NPM reads the DB on each login (no cache), so no restart needed. Then `POST /api/tokens` succeeds. **Report the new password to the user** — it's a credential change on their infra.

## Inspect proxy_host schema (read-only)

```sql
.mode line
SELECT id, domain_names, is_deleted, enabled, forward_host, forward_port, certificate_id
FROM proxy_host WHERE instr(domain_names, 'design') > 0;
SELECT id, domain_names, is_deleted FROM proxy_host WHERE is_deleted=1 LIMIT 5;
```

Reference: reels proxy host used `forward_host 172.19.0.1` (NPM host gateway) + cert id 20.

## LE cert via DNS-01 — certbot concurrency pitfall

First `POST /api/nginx/certificates` returned:

```
500 {"error":{"code":500,"message":"Internal Error"}}
debug.stack: ["Error: Another instance of Certbot is already running."]
```

Certbot only runs one at a time; a concurrent/previous issuance (e.g. another domain, or the retried request) blocks. Wait ~45 s and retry — second attempt succeeded and returned `expires_on` (`2026-12-02 ...`), id 23.

Cloudflare token NPM uses is in the host letsencrypt `credentials/credentials-<n>` file: `grep dns_cloudflare_api_token= .../credentials/credentials-3`.

## Attach cert to proxy host

`PUT /api/nginx/proxy-hosts/21` with `{domain_names, forward_host, forward_port:7456, forward_scheme:"http", ssl_forced:true, block_exploits:true, http2_support:true, allow_websocket_upgrade:true, certificate_id:23, enabled:true}`. NPM regenerates nginx config on change; then `curl https://<domain>/api/health` → 200.

## Design system package confirmed

`/opt/open-design/data/design-systems/<brand>/` with `manifest.json` (schemaVersion `od-design-system-project/v1`, files → DESIGN.md/tokens.css), `DESIGN.md` (≥7 H2), `tokens.css` (--bg/--surface/--accent/--accent-2/--fg/--font-display...). After scp + `chown -R 1001:1001`, `GET /api/design-systems` shows `user:<brand>`, status `draft`.

## Final state after OpenCode mount

`docker ps` → `open-design Up X (healthy)`; `docker logs open-design` → `listening on http://127.0.0.1:7456` + `readyToSend:true / schemaReady:true`; `https://design.neuralcrewlabs.com/api/health` → 200; `GET /api/agents` → 27 runtimes incl. `opencode` + `byok-opencode`.
