# Telegram: lista viva en un mensaje fijado

Pattern for keeping ONE pinned Telegram message as a live view of a store (task board, ledger, alert list). Validated with the Bot API against Plon's chat.

## Core rules

1. **One message, edited in place — never a new message per change.** Store `message_id` in a state JSON (next to the store, e.g. `brain/tasks/.telegram-pin.json`) and call `editMessageText`. A `send` on every mutation floods the chat; the boss asked for a board, not a log.
2. **Hash the rendered text and skip the API call when the digest is unchanged** (`editMessageText` errors on identical content). Every script run should be idempotent by construction.
3. **`parse_mode="HTML"`, never Markdown.** Task/user text is untrusted: any stray `_` or `*` produces `Bad Request: can't parse entities` and the whole update fails silently. Escape `& < >` in all interpolated text, and keep markup to `<b>`, `<i>`, `<code>`.
4. **Capture HTTPError bodies in the send helper.** Without the body, a 400 surfaces as a bare stack trace and you re-debug blind. Return `{'ok': False, 'error': body[:400]}` and log it.
5. **Fire-and-forget on the writer side:** the mutating app spawns the pin script in a daemon thread (`subprocess.run(..., timeout=30)`), so Telegram latency/failure never blocks or fails the user's mutation.
6. **Backstop timer:** a 2-minute systemd timer runs the same idempotent script to cover mutations that bypass the app (CLI, other agents). Immediate path = app hook; delayed path = timer. Both call one script.
7. **`--force` flag** on the script to ignore the digest and re-render (used after manual state surgery or when verifying what the boss actually sees).

## Verification recipe

- `getChat?chat_id=<id>` returns `pinned_message` — read back `message_id` and first line to confirm what the user actually sees, not what the script printed.
- State file shape: `{"message_id": N, "digest": "...", "actualizado": ISO-ts}`.

## Token source

Bot token lives in the Hermes `.env` (see the state-snapshots dir for a readable copy); target chat is the CEO's id. Never paste the token into scripts — read it from the env file at runtime.
