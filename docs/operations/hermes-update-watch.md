# Hermes Update Watch: Operator Guide

This CLI observes verified official stable releases and manages local report/outbox state. It is a monitoring and notification component only: it does not install or update Hermes, access production, run SSH, create backups, restart services, or authorize a deployment.

## Before use

- Run from the immutable watcher release selected during the separately handled installation/cutover. This implementation adds the driver but does not install or schedule it.
- Use the explicitly approved private state root `/var/lib/hermes-update-watch` only after the parent confirms its owner and permissions; this task does not create it. `StateStore` fails closed on unsafe ownership, permissions, symlinks, and checkout paths; it does not repair them.
- The user authorized the weekly sender for Discord DM `1493432785245962250` with profile `roshi`. This authorization is specific to the weekly driver and does not establish a general destination default for manual `deliver` commands.
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

## Weekly driver and pending recovery

The weekly driver is locked to the user-authorized DM and `roshi` profile. It runs a complete `watch` first, then drains at most five never-attempted pending report IDs under the state lock. A failed/incomplete watch prevents sends; a delivery failure stops the batch. Reports left pending after a crash between watch and send can be delivered by a later run after a new complete scan. `sending` recovered as ambiguous, `ambiguous`, `failed_no_send`, and `confirmed` records are never retried or reset.

The intended invocation for the immutable release is:

```sh
/usr/bin/python3 /opt/hermes-update-watch/releases/<immutable-commit>/scripts/hermes-update-watch-weekly.py \
  --state-root /var/lib/hermes-update-watch \
  --target 1493432785245962250 \
  --profile roshi
```

Preserve the existing **Monday at 09:00 America/Bogota** cadence when the parent replaces the legacy cron entry after verification. Do not run both the legacy sender and this driver concurrently. On first activation, cold-start behavior can notify the latest currently verified stable release; review that expected first notification before cutover. This writer did not edit cron, install the immutable release, provision state, or send a message.

## Not enabled by this implementation

No real Discord send, state-root creation/ownership change, scheduler/cron/service change, code installation, PROD inspection/SSH, deployment checkout access, update, backup, restart, rollback, or recovery is performed by this writer. The user-authorized weekly target/profile and cadence are recorded above; installation, private state-root verification, immutable release selection, and cron replacement remain parent-controlled.
