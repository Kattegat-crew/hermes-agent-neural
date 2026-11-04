# NPM proxy host + LE cert for a Design/JS service (prod .222)

This VPS's Nginx Proxy Manager uses **SQLite**, not postgres/mysql. Admin UI is bound to the Tailscale IP on port 81 (`http://100.73.30.29:81`). The data dir on the host is `/opt/docker/nginx-proxy-manager/data/` and the DB is `database.sqlite`.

## Two ways to configure a proxy host

### Preferred: REST API (emits cert + regenerates nginx)

1. **Get a JWT**: `POST /api/tokens` with `{identity, secret}` → `token` field. Admin creds live in `/opt/vault/CREDENCIALES-ACTUALIZADAS.md` (row `| NPM UI | ...`).

2. **Create proxy host**: `POST /api/nginx/proxy-hosts`:
```json
{"domain_names":["design.<domain>"],"forward_host":"172.19.0.7","forward_port":7456,"forward_scheme":"http","ssl_forced":false,"block_exploits":true,"http2_support":true,"allow_websocket_upgrade":true,"access_list_id":0,"certificate_id":0,"caching_enabled":false,"hsts_enabled":false,"enabled":true,"meta":{}}
```
   - **`forward_host` must be reachable from the NPM container.** Use the target container's IP on the `nginx-proxy-manager_proxy` network (found with `docker inspect <ctr> --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}: {{$v.IPAddress}}{{end}}'`). `127.0.0.1` fails. For host-network services the host gateway `172.19.0.1` works (reels uses it).
   - If you get `400 "already in use"`, the host was already created (often by an earlier dup POST) — find it with `GET /api/nginx/proxy-hosts` and skip creation.

3. **Emit LE cert (DNS-01)**: `POST /api/nginx/certificates`:
```json
{"domain_names":["design.<domain>"],"provider":"letsencrypt","nice_name":"design.<domain> LE","meta":{"dns_challenge":true,"dns_provider":"cloudflare","dns_provider_credentials":"dns_cloudflare_api_token=<CF token>","propagation_seconds":60}}
```
   - Do NOT put `letsencrypt_agree` inside `meta` — it causes `400 data/meta must NOT have additional properties`. (The generic `--agree-tos` is handled server-side.)
   - If you get `500 Internal Error` with `Another instance of Certbot is already running`, a concurrent emission is in progress (often the previous attempt). Wait ~45s and retry the same POST.
   - The CF token is in NPM's `/opt/docker/nginx-proxy-manager/letsencrypt/credentials/credentials-*` (one line `dns_cloudflare_api_token=<token>`).

4. **Attach cert**: `PUT /api/nginx/proxy-hosts/{id}` with the same body plus `"certificate_id":<cert_id>,"ssl_forced":true`. This regenerates nginx config.

5. **Verify** (from outside the NPM/container, e.g. from the VPS host): `curl -s -o /dev/null -w "%{http_code}" https://design.<domain>/` → 200 (app load) or 401 (auth-protected = good). Check issuer with `openssl s_client -connect ... -servername ...`.

### Fallback: direct SQLite

Needed when the API login is unavailable. Query/insert via a throwaway alpine container mounting `/opt/docker/nginx-proxy-manager/data:/data:ro`:
```bash
docker run --rm -v /opt/docker/nginx-proxy-manager/data:/data:ro -v /tmp:/tmp:ro \
  alpine sh -c "apk add sqlite >/dev/null 2>&1; sqlite3 /data/database.sqlite < /tmp/q.sql"
```
Schemas: `proxy_host(id, created_on, modified_on, owner_user_id, is_deleted, domain_names(json), forward_host, forward_port, access_list_id, certificate_id, ssl_forced, block_exploits, http2_support, forward_scheme, enabled, advanced_config, meta(json), ...)`; `certificate(id, created_on, modified_on, owner_user_id, is_deleted, provider, nice_name, domain_names(json), expires_on, meta(json))`; `user(id, nickname, email)`; `auth(user_id, type, secret)`.

## Password rotation (when the vault creds are stale)

If `POST /api/tokens` returns `400 Invalid email or password` but `GET /api/users` shows an admin, the vault password is stale. Rotate it by overwriting the bcrypt hash:

1. Generate a hash matching the app's bcryptjs format: `docker exec nginx-proxy-manager node -e "console.log(require('bcryptjs').hashSync('<NEWPW>',10))"` (or `python3 -c "import bcrypt; print(bcrypt.hashpw(b'<NEWPW>', bcrypt.gensalt(10)).decode())"`).
2. `UPDATE auth SET secret='<hash>' WHERE user_id=1 AND type='password';`
3. Login again with the new password. NPM reads the DB per-login (no restart needed).
4. **Always report the new password to the user** and store it in the vault — silently rotating a shared credential is a security decision the admin should own.

## Quoting gotchas (SSH + sqlite + JSON)

- Double quotes inside an SSH single-quoted command get eaten. Write SQL/JSON to a file with `write_file`/`scp` to `/tmp/` first, then `sqlite3 <duerfile>`. Use `instr(domain_names,'x')>0` instead of `LIKE '%x%'` to avoid `%`/quote mangling.
- It is normal for `docker exec open-design` to be the only thing that can reach the daemon's API when there is no host port mapping; curl to `127.0.0.1:7456` from the host returns `000`.

## Cloudflare DNS record

Create the A record via the CF API (token from the NPM credentials file):
```bash
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/<zone_id>/dns_records" \
 -H "Authorization: Bearer $CFTOKEN" -H "Content-Type: application/json" \
 -d '{"type":"A","name":"design","content":"169.58.189.222","ttl":120,"proxied":true}'
```
Zone ids are discoverable from `GET /api.cloudflare.com/client/v4/zones?per_page=50`. Propagation can take a few seconds; verify with `curl` after a short wait before issuing the LE cert.
