#!/bin/bash
# audit_ticker_ownership.sh — READ-ONLY forensics for the two-ticker setup.
# Answers: who actually ticks the crons, is the output dir writable by uid 10000,
# and did any run already write as root into shared paths?
# No writes anywhere. Usage: bash audit_ticker_ownership.sh [repo_path]
set -u
REPO="${1:-/root/marketing-campaign-generator}"
CRON="${HERMES_HOME:-/root/hermes-agent-legacy-docker/data}/cron"

echo "== volume map (host -> container) =="
docker inspect hermes-agent --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' 2>/dev/null \
  | grep -E 'data|/host' || echo "(docker not reachable from here)"

echo
echo "== tickers alive =="
ps -eo pid,user,cmd | grep -E 'hermes (serve|gateway run)' | grep -v grep
for p in $(pgrep -f 'hermes serve --isolated' 2>/dev/null); do
  echo "-- pid $p env:"
  tr '\0' '\n' < "/proc/$p/environ" 2>/dev/null | grep -E 'HERMES_HOME|HERMES_DESKTOP|^HOME='
done
stat -c '%n owner=%U:%G mtime=%y' "$CRON/ticker_heartbeat" "$CRON/ticker_last_success" 2>/dev/null

echo
echo "== run artifacts owned by ROOT today (=> root ticker claimed those jobs) =="
find "$CRON/output" -user root -newermt 'today 00:00' -printf '%TH:%TM %u:%g %s %p\n' 2>/dev/null | sort

echo
echo "== output dir permissions =="
stat -c '%n owner=%U:%G mode=%A' "$CRON/output" 2>/dev/null
setpriv --reuid=10000 --regid=10000 --clear-groups bash -c "cd '$CRON/output' 2>/dev/null && { [ -w . ] && echo 'WRITABLE by uid 10000' || echo 'NOT writable by uid 10000'; }"

echo
echo "== root-owned residue in $REPO =="
find "$REPO" -user root -not -path '*/.git/*' -printf '%p\n' 2>/dev/null | head -30
echo "count: $(find "$REPO" -user root -not -path '*/.git/*' 2>/dev/null | wc -l)"
echo "(>0 => a root-claimed run already wrote there; repair: chown -R 10000:10000 '$REPO')"

echo
echo "== git state as uid 10000 (read-only) =="
setpriv --reuid=10000 --regid=10000 --clear-groups env HOME=/opt/data bash -c \
  "git -C '$REPO' status --porcelain | head; echo 'HEAD / origin/main:'; git -C '$REPO' rev-parse HEAD origin/main"
