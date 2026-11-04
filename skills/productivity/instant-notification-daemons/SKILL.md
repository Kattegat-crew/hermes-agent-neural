---
name: instant-notification-daemons
category: devops
description: "Use when building or fixing push-notification daemons."
tags: [daemon, notificaciones, imap, whatsapp, watchdog, delivery, timeouts]
---

# Instant Notification Daemons (never miss an event)

Class: any system whose job is "user MUST be told when event X happens" — purchase alerts, message notifications, uptime pings. The failure mode is always the same and always invisible: the system keeps running, the user simply never finds out. Design for that failure from line one.

## The 5 Guarantees (design checklist)

1. **Delivery-confirmed pointer.** The classic bug: a cursor/pointer advances when the event is *read*, not when the notification is *sent*. If the send fails, the event is lost forever. Fix: the pointer ONLY advances after a confirmed delivery (WhatsApp/API send returned success). A read-but-unsent event stays pending and is retried on the next cycle/reconnect.
2. **Refuse to advance over undelivered events.** On reconnect, never assume "processed = delivered". Re-derive pending work from the confirmed pointer, not from what was merely seen.
3. **Honest parsing.** If the source's template changed (bank email layout, webhook schema), prefer raising and retrying over sending a corrupted/garbage alert. `amount == '?'` or empty body → exception, not notification.
4. **Realistic timeouts.** A socket timeout shorter than the platform's push drain (e.g. 30s against Gmail IDLE which needs ~180s) kills the daemon exactly when an event arrives. Set generous timeouts on the connection; short ones only for idle drain.
5. **Explicit imports.** In long-lived daemons, every module used in the hot path must be imported at top level — a missing `import select` crashed a daemon in a silent 20s crash-loop while it looked alive to the watchdog.

## Debugging "the notification never came" (in order)

1. Confirm the event actually arrived at the source (search the mailbox/feed for the sender + timestamp).
2. Read the daemon log around the event timestamp — crash-loop? timeout? parse failure?
3. Inspect the pointer/state file: did it advance past the event? If yes and no send log → classic guarantee-1 violation. Reconcile: rewind the pointer to before the event, restart, let it re-notify. Rewinding + real re-delivery is the honest test.
4. Check what's actually running: a watchdog relaunching a broken version produces crash-loops that superficially look like "running". Kill everything, start the fixed version once, verify PID and log line-by-line through the first event.
5. After ANY fix to a production daemon: restart the service and immediately verify the new process is the fixed code — a half-applied fix + watchdog = silent crash-loop.

## Test without damaging (no fake events to the user)

- Best test: rewind the pointer to before a REAL past event and let the fixed system re-notify. Proves detection, parsing, and delivery end-to-end with real data.
- Self-send a synthetic message to the monitored mailbox yourself, delete after; never fabricate user-facing events into their chat without saying so.
- Synthetic tests prove wiring, not delivery-guarantee logic — the rewind test is the one that matters.

## Watchdog & ops

- Watchdog (cron every few minutes) must check: process alive AND log recently advanced AND no crash-loop signature (same error repeating at restart cadence).
- Keep the daemon independent of the agent gateway (own process, own restart) so gateway restarts don't drop monitoring; the watchdog survives both.
- Document every real incident in README + memory: the next debugging session starts from the postmortem, not from zero.

## Reference

- `references/davibank-implementation.md` — concrete implementation of all 5 guarantees (IMAP IDLE + Gmail OAuth + WhatsApp send), v2.1→v2.2 incident postmortem, state file format, watchdog cron setup.
