#!/bin/bash
# vigia_post_thread.sh — publica stdin en un hilo/canal de Discord via bot Ragnar.
# Uso:  echo "texto" | vigia_post_thread.sh <channel_id>
# Silencioso si stdin vacio. NUNCA falla el job (siempre exit 0).
set -u
CH="${1:-}"
TXT=$(cat)
[ -z "$TXT" ] && exit 0
[ -z "$CH" ] && { echo "vigia_post_thread: falta channel_id" >&2; exit 0; }
# Token del bot: env -> secret materializado por el gateway -> .env legacy.
# Desde oct-2026 el token ya no vive en /opt/data/.env (lo sirve el vault), y el
# grep en .env devolvía vacío: los avisos se perdían en silencio con exit 0.
TOKEN="${DISCORD_BOT_TOKEN:-}"
if [ -z "$TOKEN" ] && [ -r /opt/data/secrets/discord-nca-bot.token ]; then
  TOKEN=$(tr -d '\r\n' < /opt/data/secrets/discord-nca-bot.token)
fi
if [ -z "$TOKEN" ]; then
  TOKEN=$(grep -m1 '^DISCORD_BOT_TOKEN=' /opt/data/.env 2>/dev/null | cut -d= -f2 | tr -d '"' | xargs)
fi
[ -z "$TOKEN" ] && { echo "vigia_post_thread: sin token" >&2; exit 0; }
MSG=$(printf '%s' "$TXT" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()[:1900]))')
CODE=$(curl -s -m 12 -X POST "https://discord.com/api/v10/channels/$CH/messages" \
  -H "Authorization: Bot $TOKEN" -H "Content-Type: application/json" \
  --data-raw "{\"content\": $MSG}" -o /dev/null -w "%{http_code}")
echo "post:$CODE"
exit 0
