---
name: hermes-relocation-ops
description: "Use when asked to move an agent: guild, token or host."
tags: [discord, guild, relocation, migracion, token, gateway, perfiles, allow-bots]
version: 1.0.0
author: Roshi
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [discord, telegram, migration, profiles, gateway, secrets]
    related_skills: [multi-profile-cron-reliability]
---

# Hermes Relocation & Ops-Inquiry

Answers "can I move you to X?" and "can we do Y across agents?" questions about this
agent fleet: moving to another Discord server (guild), a new bot app/token, or another
machine; and configuring bots to see/talk to each other (`DISCORD_ALLOW_BOTS`). Also
carries the inventory recipe for the per-profile layout on this host and the
gateway-source-reading technique for answering capability questions with evidence.

## ⚠️ Step 0 — Disambiguate "servidor" BEFORE going deep
When Yisus/Jonathan asks "¿puedo cambiarte de servidor?" while chatting **on Discord**,
he almost always means a **Discord server (guild)**, not the physical box/VPS. Real
session (01/09): a one-line ambiguous question triggered ~10 tool calls of /opt/data
host-migration auditing before the user redirected with "...de servidor EN Discord".
Rule: for a yes/no capability question, answer fast with short branches ("¿guild o
máquina? A) ... B) ...") — depth comes AFTER scope is known. Never launch a full
investigation on an ambiguous noun in the first message.

## Fleet inventory (this host)
- Profiles root: `/opt/data/profiles/<name>/` — one per agent (roshi, bragi, brokkr,
  comms, freyja, heimdall, hermodr, sindri, ullr, vigia, vili, default).
- Per profile: `config.yaml` (platforms/providers/model pins), `.env`
  (`DISCORD_BOT_TOKEN`, `TELEGRAM_BOT_TOKEN`, `DISCORD_ALLOWED_USERS`, …),
  `cron/jobs.json`, `gateway.{pid,sock,state.json}` + `gateway-starts.log`,
  `sessions/`, `memories/`, `skills/`, `workspace/`, `SOUL.md`/`AGENTS.md`.
- Disk shape (01/09): full `/opt/data` ≈ 15G; a profile ≈ 650M (workspace+skills
  dominate); biggest trees: `home/` 5.5G, `workspace/`, `.cache/`, `.npm/` — caches
  are rebuildable, never copy them in a host move.
- Which profiles hold a given platform's bot: loop `grep -q DISCORD_BOT_TOKEN
  profiles/*/.env`. On this fleet each specialist profile carries its own token.
- Skills vault is shared: `/opt/data/skills/` + graphify `graph.json`.

## Safe secret inspection (never echo token values)
- List key names only: `grep -oE '^[A-Z_]+=' .env`.
- Redact values inline: `sed -E 's/(token:.{0,8}).*/\1...[oculto]/I'`.
- Compare a token across profiles WITHOUT exposing it: extract, `sha256sum |
  cut -c1-12`, compare fingerprints — equal hash = same bot.
- System python3 has no `yaml` module → parse configs with grep/sed or use a venv
  with pyyaml.

## Move the agent to another Discord server (guild)
**Option A — same bot, new guild (simplest, recommended):** the token and gateway are
NOT bound to a guild; the bot listens account-wide. Invite via Developer Portal →
OAuth2 → URL Generator (scope `bot`; perms: Send Messages, Embed Links, Attach Files).
Re-check intents (Message Content; Server Members if used) are still enabled.
**Option B — new bot application:** replace `DISCORD_BOT_TOKEN` in the profile `.env`,
adjust `DISCORD_ALLOWED_USERS`, restart the gateway. Discord user IDs are **global**, so
the allowlist (Yisus 996914419 / Plon 8709909260) survives unchanged.
Either option, gotchas:
1. **Home channel ID is guild-specific** (e.g. discord "Home" `1493354289773674760`)
   — crons and scheduled reports that deliver to it must be re-pointed after the move.
2. **Never run two instances on the same token at once** (gateway fight). Stop the old
   before starting the new; same applies if the host is also changing.
3. Standing team rule: **one bot per team** (Marketing Crew / Ops-System), not one per
   agent — moving a shared bot moves the whole team riding on it; warn before doing it.

## Move to a different machine (host migration) — outline only, not executed in prod
Carry all of `/opt/data` (rsync -a excluding `.cache/ .npm/ cache/ *_cache*`), reinstall
Hermes, restore profile dirs, then re-verify: skills symlinks (see
`multi-profile-cron-reliability` Pitfall B — links break across hosts), venv paths,
`cron/jobs.json` contents (crons are file-based here, not system crontab), gateway
pid/sock state after boot. Pin all fleet crons post-move (drift-skip bites after any
config change).

## Can our bots see/talk to each other on Discord? (`DISCORD_ALLOW_BOTS`)
Default is `none` → a bot-authored message is dropped TWICE: it never wakes the other
bot (admission gate) AND it is filtered out of the `[Recent channel messages]` context
window, so bots are mutually invisible even mid-conversation. Modes (per-profile env,
read live per message — a gateway restart is still needed for `.env` to be re-read):
- `none` — bots can't see each other at all (current fleet default).
- `mentions` — a bot-authored message wakes this bot only when it @-mentions it
  (`_self_is_explicitly_mentioned`); all bot messages still show as context labeled
  `[Name [bot]]`. Recommended for shared human+bot threads.
- `all` — any bot message wakes; risky (ping-pong).
Related guards:
- `discord.bots_require_inline_mention` (config or env): demands a literal `<@thisbot>`
  token — a reply-chip does NOT count, because Discord silently adds the replied-to bot
  to `message.mentions`. Turn on if a `mentions` setup ever ping-pongs.
- When a HUMAN mentions two bots in one message, only the explicitly @-ed bots respond
  (the other-bots-mentioned branch short-circuits non-mentioned bots).
- Bots admitted via `DISCORD_ALLOW_BOTS` bypass the `DISCORD_ALLOWED_USERS` human
  allowlist (authz_mixin comment #4666-path), so no user-ID changes needed.
Recipe for a "we 4 want to work together" request: set `DISCORD_ALLOW_BOTS=mentions` in
EACH participating bot profile's `.env` (loop: `grep -n 'ALLOW_BOTS' /opt/data/profiles/*/.env`
to see who has it), restart both gateways, then humans `@BotA @BotB` in one thread and
each bot sees the other's replies as context. Flag before doing it: config of agents is
Chucho's domain per team rules, and the gateway restart drops the bot for a few seconds.

## Reading gateway source to answer capability questions (evidence, not guessing)
When asked "can Hermes do X / does it see Y", grep the live source instead of answering
from general Discord.py knowledge — the fleet runs a patched tree with custom gates:
- `grep -rn --include=*.py -iE 'author\\.bot|is_bot|ALLOW_BOTS|bot_id' /opt/hermes/gateway /opt/hermes/plugins/platforms/discord`
- Key files: `plugins/platforms/discord/adapter.py` (`_discord_message_admission` = wake
  gate, `include_other_bots` in the history scan = context gate, `_get_allow_bots`),
  `gateway/authz_mixin.py` (`_platform_gate_env`, allow-bots bypass of user allowlist),
  `gateway/session.py` (`is_bot` field). Then check the profile `.env` for actual state.
Cite file:line in the answer — Plon/Yisus trust verified answers with concrete knobs
over hedged guesses.

## Docs pointer
Authoritative answers about Hermes itself: https://hermes-agent.nousresearch.com/docs —
machine-readable index at `/docs/llms.txt` (web_extract handles it cleanly; ~17KB).

## Verification
After any move: send a test DM in the new guild/chat, confirm `gateway_state.json`
shows the platform connected, and dry-run one Discord-delivering cron so the home
channel resolves.
