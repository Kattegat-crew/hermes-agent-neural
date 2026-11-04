#!/usr/bin/env bash
# Esquema de messages (para atribución) + canales de notificación disponibles.
set -uo pipefail
R=/root/hermes-agent-legacy-docker
echo "=== esquema de messages ==="
python3 - "$R/data/state.db" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
for r in c.execute("select sql from sqlite_master where name in ('messages','sessions')"):
    print(r[0][:600]); print('---')
print("=== ejemplo de fila reciente ===")
cur = c.execute("select name from pragma_table_info('messages')")
cols = [r[0] for r in cur]
print("columnas:", cols)
q = "select %s from messages order by rowid desc limit 1" % ",".join(cols)
row = c.execute(q).fetchone()
for k, v in zip(cols, row):
    s = str(v)
    print("  %-18s %s" % (k, s[:160]))
PY
echo
echo "=== canales de notificacion declarados ==="
grep -rhoE "https://discord.com/api/webhooks/[0-9]+" "$R/data/config.yaml" "$R/.env" 2>/dev/null | sed 's|\(webhooks/[0-9]*\).*|\1/...|' | sort -u | head
echo
grep -rn "notify_webhook\|ops_webhook\|alerts_webhook\|DISCORD_WEBHOOK\|discord.webhook" "$R/data/config.yaml" "$R/.env" 2>/dev/null | head -8
echo
echo "=== envio de alertas existente en scripts ==="
grep -rln "webhook" "$R/scripts" 2>/dev/null | head -8
