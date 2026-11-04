#!/bin/bash
# audit_cron.sh <job_id> <wrapper.sh> — verifica un cron de Hermes en el namespace REAL del gateway (uid 10000).
# Adaptar <repo> y los imports al cron auditado.
G=$(pgrep -f 'hermes gateway run' | head -1)
[ -z "$G" ] && { echo 'gateway no corre'; exit 1; }
NS="nsenter -t $G -m -S 10000 -u -- env HOME=/opt/data PATH=/opt/data/.local/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
JOB=$1; WRAP=$2

echo "== 1) repos visibles desde el contenedor =="
$NS ls /opt/data/repos/ 2>&1 | head -5

echo "== 2) deps del python del cron =="
$NS python3 -c "import openpyxl,requests; print('DEPS-OK')" 2>&1 | tail -1

echo "== 3) git del cron-user =="
$NS sh -c 'cd /opt/data/repos/<repo> && git status -sb | head -1' 2>&1

echo "== 4) output dir escribible =="
$NS sh -c "mkdir -p /opt/data/cron/output/$JOB && touch /opt/data/cron/output/$JOB/.wt && rm /opt/data/cron/output/$JOB/.wt && echo WRITE-OK" 2>&1

echo "== 5) wrapper completo =="
$NS bash "$WRAP"; echo "EXIT=$?"

echo "== 6) binarios externos que usa el script =="
$NS sh -c 'command -v composio || echo "composio NO en contenedor (usa puente ssh root@10.0.2.1)"'
