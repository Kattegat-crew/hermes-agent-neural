#!/usr/bin/env bash
# Reconocimiento para el job de higiene: consumidores de la alerta + state.db.
set -uo pipefail
R=/root/hermes-agent-legacy-docker
echo "=== consumidores de skills_sync_alert.json ==="
grep -rl "skills_sync_alert" "$R/scripts" "$R/data/scripts" /root/.agents 2>/dev/null | head -5
echo
echo "=== crons que tocan skills ==="
crontab -l 2>/dev/null | grep -iE "skill|higiene|vigil" || echo "  (ninguno en crontab root)"
ls -la /etc/cron.d/hermes-sync 2>/dev/null && cat /etc/cron.d/hermes-sync
echo
echo "=== state.db: ubicacion y tamaño ==="
for f in "$R/data/state.db" /opt/data/state.db "$R/data/profiles/roshi/state.db"; do
  [ -f "$f" ] && echo "  $f  $(stat -c '%s B' "$f")"
done
echo
echo "=== tablas de state.db ==="
DB="$R/data/state.db"
[ -f "$DB" ] || DB="$(ls "$R"/data/profiles/roshi/state.db 2>/dev/null | head -1)"
python3 - "$DB" <<'PY'
import sqlite3, sys
db = sys.argv[1]
c = sqlite3.connect(db)
print("  db:", db)
for (n,) in c.execute("select name from sqlite_master where type='table' order by name"):
    try:
        cnt = c.execute("select count(*) from %s" % n).fetchone()[0]
    except Exception:
        cnt = '?'
    print("   -", n, cnt)
PY
