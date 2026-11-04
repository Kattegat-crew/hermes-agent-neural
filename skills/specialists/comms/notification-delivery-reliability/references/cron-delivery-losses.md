# Caso verificado: paquete diario de campaña no entregado (08–10/09/2026)

## Pregunta del usuario
"¿A qué horas llega hoy la aprobación de las piezas?" — el job SÍ había corrido 4 minutos antes; el mensaje no llegó.

## Registro campo por campo

Job `calendario-paquete-diario` (`fee5dcf7691b`), `deliver: whatsapp:573166910728@s.whatsapp.net`:

| Campo | Valor |
|---|---|
| `last_run_at` | 2026-09-10T07:31:12-05:00 |
| `last_status` | `ok` |
| `last_delivery_error` | `delivery error: WhatsApp send failed: [Errno 104] Connection reset by peer (target whatsapp:573166910728@s.whatsapp.net)` |
| `executions.db` | `status: completed`, `pid: 77739` |

El `.md` de la corrida quedó `root:root` → ilegible como hermes; se lee con `docker exec hermes-agent cat …`.

## Recurrencia

```
2026-09-08 21:29  job 794be6c2336b  WhatsApp send failed: Server disconnected
2026-09-08 22:38  job 794be6c2336b  WhatsApp send failed: [Errno 104] Connection reset by peer
2026-09-09 01:57  job 794be6c2336b  Server disconnected
2026-09-09 05:17  job 794be6c2336b  [Errno 104] Connection reset by peer
2026-09-09 07:30  job fee5dcf7691b  [Errno 104] Connection reset by peer   <- paquete diario
2026-09-10 07:31  job fee5dcf7691b  [Errno 104] Connection reset by peer   <- paquete diario
```

≈15% de los envíos programados a WhatsApp; 2 días consecutivos sin recibir el digest.

## Qué NO era el problema

- El canal: `/health` → `{"status":"connected","queueLength":0}`, bridge con ~44 h de uptime.
- `bridge.log`: loops benignos `Connection closed (reason: 428/503). Reconnecting in 3s...` y **sin entrada** del envío fallido (reset a nivel TCP, antes del handler). El log incluso estuvo horas sin escribir con el bridge arriba → no sirve como única fuente.
- El scheduler: la corrida y el claim quedaron completos en `executions.db`.
- El proceso que ejecutó: PID 77739 = backend root del Desktop (`hermes serve --isolated`, root, `HERMES_HOME=/root/hermes-agent-legacy-docker/data`), no el gateway s6 (uid 10000). Ambos tickers comparten `jobs.json`.

## Comandos usados

```bash
grep -ahE "delivery error|send failed" /opt/data/logs/agent.log | tail -20
curl -s 127.0.0.1:3000/health
python3 -c "import json;d=json.load(open('/opt/data/cron/jobs.json'));..."   # last_delivery_error por job
ssh dev 'docker exec hermes-agent cat /opt/data/cron/output/<jobid>/<fecha>.md'   # output root-owned
ssh dev 'docker exec hermes-agent python3 -c "import sqlite3,json; ... executions.db"'
```

## Siguiente acción propuesta (pendiente de OK del usuario)

`deliver: "whatsapp:573166910728@s.whatsapp.net,telegram:8709909260"` en los jobs de campaña (paquete diario, publicación horaria, informe de campaña), con backup de `jobs.json`. Discord queda como tercera opción, no como sustituto (cambiar un canal frágil por otro).
