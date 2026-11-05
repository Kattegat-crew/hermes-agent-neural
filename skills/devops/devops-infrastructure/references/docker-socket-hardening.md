# Docker Socket Hardening & Kuma Coverage Recovery

Depth for the container-privilege workflow: auditing `docker.sock` holders, removing the socket safely, and rebuilding uptime-kuma coverage without it.

## Audit: who holds docker.sock
A container with `docker.sock` mounted is root-of-host by proxy: anyone controlling it can ask dockerd to run a privileged container with `/` mounted. Audit before assuming a container is "just low-priv".
- Inventory in one pass: for each running container, `docker inspect -f '{{range .Mounts}}{{.Source}} {{end}}'` and flag `docker.sock` matches. Confirm per suspect with `docker exec <c> test -S /var/run/docker.sock` — a stale inspect cache or an inherited image entrypoint can mislead.
- Classify before touching: keep sockets that are structural (orchestration sentinels, the fleet's own agent) and document them as accepted residual risk; remove the ones mounted only for convenience (e.g. a monitor peeking at container state).
- Removal protocol: back up the compose file first (`docker-compose.yml.bak-<ts>`), edit mounts down to data/certs only, `docker compose up -d --force-recreate`, then verify from INSIDE the container (`test -S /var/run/docker.sock` → NO-EXISTE) and that the service still answers on its mapped IP.
- Scope the severity honestly: a socket holder bound only to the Tailscale IP is not internet-exposed, but the app's own login becomes the single barrier between a compromised account and root of the host. Report it as residual risk with the mitigation option (read-only `docker-socket-proxy`), not as "fixed".

## Expect monitor collateral, plan before recreating
Any Kuma monitor of type `docker` loses its target the moment the socket is gone and fails with `ENOENT`. Back up `kuma.db`, disable those monitors (`UPDATE monitor SET active=0`), and remember monitors are held in memory — the change needs a Kuma container restart to take effect.

## Recover coverage without the socket
HTTP/port monitors detect "service not responding" but NOT a crash-looping container still serving stale content. Cross-check coverage with read-only SQLite over SSH (`sqlite3 'file:/opt/uptime-kuma/data/kuma.db?mode=ro'` — enumerate active http/port monitors and diff against the disabled docker monitors).
- Count INDIRECT coverage before declaring a gap: a service served through an NPM domain is covered by that domain's HTTPS monitor, and a webhook consumer is covered by its webhook-endpoint probes — an apparent list of "N uncovered containers" usually shrinks on real verification.
- Non-HTTP services (admin panels, agent APIs) take a PORT monitor against the Tailscale IP: cheap liveness without inventing HTTP endpoints.

## Push monitor recipe (validated on PROD)
Replaces docker-type monitors with zero socket exposure: a host-side script + `/etc/cron.d` entry every 2 min pushes a verdict to the Kuma push endpoint.

Detection set (run on the host, which already has Docker privileges — nothing needs the socket mounted):

```bash
# 1. unhealthy
 docker ps --filter health=unhealthy --format '{{.Names}}' | paste -sd, -
# 2. restart-looping
 docker ps --filter status=restarting --format '{{.Names}}' | paste -sd, -
# 3. restart-policy != no but not running (ONE inspect pass over docker ps -aq;
#    the policy comes from .HostConfig.RestartPolicy.Name, NOT from labels)
 docker inspect --format '{{.Name}}|{{.State.Status}}|{{.HostConfig.RestartPolicy.Name}}' $(docker ps -aq)
#    -> while IFS='|' read -r nm state policy; flag state != running when policy not in (no, "")
```

Push the verdict: `GET <kuma>/api/push/<monitor-token>` with query params `status` (`up`/`down`), `msg` (problem list, or "N contenedores arriba, 0 problemas") and `ping`. Build the query with `curl -G --data-urlencode` — the msg carries container names and semicolons that break a hand-built query string.

Key details:
- Bind the push monitor to the Discord notification in `monitor_notification` or it collects heartbeats silently.
- Create the push monitor in Kuma first and take its token from the monitor's edit panel; each push monitor has its own token.

## Self-test the DOWN path before trusting a push monitor
A push monitor that has only ever reported UP proves nothing — the detection branch is the whole value.
1. `docker run -d --name kuma-push-selftest --restart always alpine sleep 600`
2. `docker stop kuma-push-selftest` → run the script: expect exit 1 and a DOWN heartbeat (verify the cron cycle catches it too, not just the manual run).
3. `docker rm -f kuma-push-selftest` → run again: expect exit 0 / UP.
4. Check `notification_sent_history` for that monitor id: confirm the test fired no more than the intended down/up pair so the alert channel was not spammed.

## Kuma DB writes: stop → backup → write → chown
- SQLite WRITES to `/opt/uptime-kuma/data/kuma.db` require the container stopped (`docker compose stop uptime-kuma`), a fresh backup (`kuma.db.bak-<ts>`), and `chown 10000:10000` at the end — the container runs as uid 10000 and a root-owned DB breaks the next start.
- READ-ONLY queries need none of this: open with `file:...?mode=ro` anytime, even while Kuma runs.
- Monitor config changes via SQL (including `active=0`) only take effect after a Kuma restart — monitors live in memory.

## Deactivate monitors whose target is hardened BY DESIGN
Before "fixing" a permanently DOWN monitor, verify the service bind (`docker inspect` port bindings / listen address). A service deliberately bound to `127.0.0.1` fails a TCP monitor aimed at the Tailscale IP forever — the correct action is `UPDATE monitor SET active=0`, never re-opening the port to make a monitor green. A false-positive monitor trains the team to ignore alerts.
