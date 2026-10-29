# Hermes Update Watch: Operator Guide

This CLI observes verified official stable releases and manages local report/outbox state. It is a monitoring and notification component only: it does not install or update Hermes, access production, run SSH, create backups, restart services, or authorize a deployment.

## Before use

- Run from a checkout with the approved watcher code. This feature is not installed or enabled by this implementation task.
- Choose a private state root outside every checkout. The proposed `/opt/hermes-agent-data/state/update-watch/` path is not operationally approved or created here. `StateStore` fails closed on unsafe ownership, permissions, symlinks, and checkout paths; it does not repair them.
- Obtain separate human authorization for the exact numeric Discord destination and `ncl-discord` profile (`default`, `ragnar`, or `roshi`). No destination is configured as a default, and this guide does not establish one.
- The only post adapter is the existing `/usr/local/bin/ncl-discord` CLI. The watcher does not read credentials; credential resolution remains owned by that CLI.
- Use the explicit Python entrypoint; no package installation or scheduler setup is performed:

```sh
python3 scripts/hermes-update-watch.py --help
```

## Inspect and watch

`inspect` reads official stable-release metadata and reports a bounded summary. It does not write state or send a message:

```sh
python3 scripts/hermes-update-watch.py inspect
```

`watch` requires an explicit private state root and a previously authorized numeric target. It records complete discovery/report results only; it never sends. Replace placeholders only after verifying the local state-root policy and obtaining target authorization:

```sh
python3 scripts/hermes-update-watch.py watch \
  --state-root /path/to/approved/private/update-watch-state \
  --target <authorized-numeric-channel-id>
```

Incomplete upstream discovery, evidence collection, or state persistence is reported as a bounded failure; the cursor is not advanced on a partial scan. Do not treat an unknown DEV/PROD fact as a pass.

## Deliver one report

Delivery is a separate explicit action, not part of `watch`. Select an existing unexpired report ID, the separately authorized numeric destination and profile, and provide the exact operation confirmation shown below. The state transaction records the send intent before invoking `ncl-discord`; only a strictly validated receipt confirms it. A timeout, malformed result, process crash, or other uncertain post-invocation outcome remains ambiguous and is never automatically retried. Investigate ambiguous delivery through the separately authorized operator process; do not reset state to resend.

```sh
python3 scripts/hermes-update-watch.py deliver <existing-report-uuid> \
  --state-root /path/to/approved/private/update-watch-state \
  --target <authorized-numeric-channel-id> \
  --profile <default|ragnar|roshi> \
  --confirm-send 'SEND <existing-report-uuid> TO <authorized-numeric-channel-id> AS <profile>'
```

The confirmation is a per-invocation guard, not a substitute for separate operational authorization. Expired, missing, corrupt, or mismatched reports are blocked before transport. Unsupported verbs (including future update/recovery verbs) exit with `unsupported_operation`; there is no hidden mutation command.

## Not enabled by this implementation

No real Discord send, destination/profile selection, state-root creation/ownership change, scheduler/cron/service change, code installation, PROD inspection/SSH, deployment checkout access, update, backup, restart, rollback, or recovery is performed or authorized by this runbook. Enablement requires a separate operator decision and verification of the target, private state-root ownership/path, alert routing, and scheduling policy.
