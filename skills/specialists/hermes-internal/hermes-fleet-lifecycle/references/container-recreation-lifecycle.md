# Container Recreation Lifecycle — Hermes Dev VPS

## Snapshot: dev VPS (147.93.3.250)

- Compose: `/root/hermes-agent-legacy-docker/docker-compose.yml`
- Image: `hermes-agent-hermes` (rebuilt by sync-upstream.sh)
- Cron rebuild: `/etc/cron.d/hermes-sync` → `0 2 * * * root /root/hermes-agent-legacy-docker/scripts/sync-upstream.sh`
- Container restart policy: `unless-stopped`
- sync-upstream log: `/root/hermes-agent-legacy-docker/scripts/sync-upstream.log`
- Key config: `gateway.multiplex_profiles: true` in `/opt/data/config.yaml` (line 494)

## Timeline of events (Sep 2-3 2026)

| Time (Bogotá) | Event | Effect |
|---|---|---|
| Sep 2 14:49-14:51 | Manual compose up ("Obtener versión de Hermes" session) | Container recreated; all named-profile gateways DOWN |
| Sep 2 14:53 | Reconciler: `action=registered` for roshi/vigia/comms (multiplex on) | No auto-start |
| Sep 2 15:17 | Roshi gateway NOT started; roshi gateway down file created at 14:52 | |
| Sep 2 23:36 | Manual `s6-svc -u gateway-roshi` (by whom?) | Roshi up, Discord+Telegram connected |
| Sep 3 00:27 | .env patches applied (API_SERVER_ENABLED=false etc. on all profiles) | Removed port-binding skip cause |
| Sep 3 00:56 | `s6-svc -r gateway-roshi` (restart for env) | Roshi restarts cleanly |
| Sep 3 01:07 | `s6-svc -d` (watchdog test) + `s6-svc -u` (revive) | Confirmed watchdog works |
| Sep 3 02:00 | sync-upstream.sh cron fires | git pull 370 commits + docker compose up --build |
| Sep 3 02:13:26 | Docker image tag event | New image rebuilt |
| Sep 3 02:13:33 | Docker kill signal=15 (SIGTERM to all) | Container destroyed |
| Sep 3 02:13:53 | New container created/started | PID 1 up |
| Sep 3 02:14:12 | Reconciler: `action=registered` for ALL named profiles | down file for all |
| Sep 3 02:15:27 | Default gateway: "Skipping secondary profile 'roshi' due to port-binding api_server" | Roshi not served by multiplex |
| Sep 3 ~02:50 | Watchdog `s6-svc -u` → roshi starts → hits multiplex guard → exit 78 | First exit 78 |
| Sep 3 ~03:50 | Watchdog retry → same exit 78 | Loop continues |
| Sep 3 03:58 | `s6-svstat`: down (exitcode 78) 168 seconds | Permanent failure state |

## Key code paths

### Reconciler auto-start gate (container_boot.py:207)
```python
multiplex_profiles = ???  # from default config gateway.multiplex_profiles
...
prior_state = _read_desired_state(entry)
should_start = (
    not multiplex_profiles and prior_state in _AUTOSTART_STATES
)
```
- With `multiplex_profiles: true` → `not True` = `False` → named profiles NEVER auto-start.
- `default` slot: uses a different path (`default_should_start = default_prior_state in _AUTOSTART_STATES`) — NO multiplex gate.
- `_AUTOSTART_STATES = frozenset({"running"})`

### Multiplex guard (gateway.py:6398-6415)
```
The default gateway is running as a profile multiplexer and already serves
profile '<name>'.
Starting a separate gateway for this profile would double-bind its platforms
(two pollers on one bot token, port conflicts).
Manage the multiplexer instead (from the default profile):
    hermes gateway restart
Pass --force to start a separate profile gateway anyway (not
recommended while the multiplexer is running).
sys.exit(GATEWAY_FATAL_CONFIG_EXIT_CODE)  # = 78
```

### Finish script (service_manager.py:720)
- Exit 78 → `exit 125` → s6 permanent failure (no restart)
- Exit 0 → `exit 125` → intentional stop (no restart)
- Any other exit → `exit 0` → s6 restarts normally

### Secondary port-binding skip (gateway/run.py:17301-17311)
```python
port_binding_platforms = sorted(
    platform.value
    for platform, platform_config in profile_cfg.platforms.items()
    if platform_config.enabled
    and _platform_binds_port(platform.value, platform_config.extra)
)
if port_binding_platforms:
    raise SecondaryPortBindingConfigError(...)
```
- The check reads `profile_cfg.platforms` — derived from root `.env` flags for the multiplex context, NOT profile-level `.env`.
- api_server, webhook are port-binding; discord, telegram are not.
- When a profile raises `SecondaryPortBindingConfigError` → entire profile skipped → multiplex does NOT serve it → standalone is allowed.
- When the error is removed (API_SERVER_ENABLED=false) → multiplex DOES serve the profile → guard blocks standalone.

## Watchdog script contract

Host cron: `*/10 * * * * root docker exec hermes-agent /bin/bash /opt/data/scripts/gateway-fleet-health.sh`

Internals:
1. For ALWAYS_UP list (default, roshi): `s6-svstat` → if down → `s6-svc -u` → report.
2. For other slots: only report if `down (unexpected` (normal reconciler DOWN is expected).
3. Silent stdout = no delivery (cron `--no-agent` pattern).

## Pitfalls

- **Restarting roshi standalone under multiplex ON + v0.21+**: after removing port-binding from roshi .env, the multiplex guard now fires → exit 78. The .env patch was counterproductive. Either revert to having api_server enabled (so multiplex skips roshi), or migrate roshi entirely to multiplex (no standalone).
- **Profile .env precedence**: the multiplex reads flags from root `.env`, not profile `.env`. Changing `API_SERVER_ENABLED=false` in `profiles/roshi/.env` has NO effect on the multiplex's skip decision.
- **`down` file is recreated every boot**: the reconciler writes `down` unconditionally for non-default profiles under multiplex. Removing it manually has no lasting effect across container recreations.
- **Watchdog in container dies with container**: cron jobs inside the gateway only run while the gateway runs. Host-side cron is needed for survival across container recreates.