# 2026-08-31 — Golden webhook FAIL|000: false-green de Vigía + micro-caídas por deploy

## Contexto
Vigía (`vigia-health-2h`, sonda cada 2h sobre prod) reportó:
```
[FALLO] golden_webhook -> arreglado (re-check OK)
[FALLO] golden_chat -> arreglado (re-check OK)
```
El usuario dijo que el servicio "se cae de vez en cuando". La auditoría posterior demostró que el "arreglado" era **false-green**: el contenedor se había auto-recuperado al terminar un deploy; Vigía atribuyó la recuperación a su intervención.

## Causa raíz real (micro-caídas de deploy, no crashes)
- Compose de prod (`/opt/docker/webhook-gateway/docker-compose.yml`) arranca el Node con:
  `sh -c "npm install --no-audit --no-fund && node webhook-server.js"`
- Cada recreate del contenedor deja los puertos 10.0.1.1:3099/3100 **cerrados ~20–40s** mientras corre `npm install`. Toda sonda que pique en esa ventana ve `FAIL|000` (timeout de curl).
- Evidencia del 31/08 (horas Bogotá): `.env` editado 08:38 → contenedor Created 08:40; "Server running" 10:27; `knowledge.js`/`knowledge-paradise.js` editados 13:59–14:00 → restart 14:00. El run de Vigía de 14:02 cayó en la ventana del deploy de knowledge.js.
- `RestartCount=0`, `OOMKilled=false`, cero errores en `docker logs -t` del proceso Node → el proceso nunca crashea; lo recrean externamente (deploy manual de archivos: `.env`, knowledge base).

## Método que funcionó (forense, ~45 min)
1. `docker inspect webhook-gateway --format 'RestartCount={{.RestartCount}} OOMKilled={{.State.OOMKilled}} Created={{.Created}} Started={{.State.StartedAt}}'` — Created ≠ Started ⇒ lo recrearon; Started ≠ Created + RestartCount>0 ⇒ el proceso murió y Docker lo levantó.
2. `docker logs -t <c> --since 26h` — buscar timestamps de "Server running" (cada uno = un arranque); grep de errores reales del proceso.
3. `ls -la --time-style='+%m-%d %H:%M' /opt/docker/webhook-gateway/` — mtimes de `.env`, `*.js` correlacionan con cada recreate (quién y cuándo desplegó).
4. `last` + `grep Accepted /var/log/auth.log` — sesiones SSH entrantes (10.0.1.5 = red interna/agentes, 147.93.3.250 = VPS Hermes).
5. `crontab -l` en prod — descartar cron de reinicio.

## Auditar el reporte del watchdog (false-green)
- Re-ejecutar la sonda uno mismo: `python3 /opt/data/scripts/system-health-audit.py` (contenedor Hermes) → ejecuta `/root/audit_remote.sh` en prod vía SSH.
- Snapshot pre-corrección: `/opt/data/profiles/vigia/cron/output/3553a2017560/monitor_last_output.txt`.
- Runs del job: `/opt/data/profiles/vigia/cron/output/3553a2017560/YYYY-MM-DD_*.md` — `Status: no_change (agent run suppressed)` significa que el monitor no despertó al agente: un FAIL puede permanecer invisible hasta 2h y el historial de "arreglados" tiene huecos.
- Correlacionar la hora del run del monitor vs Created/Started del contenedor: si el FAIL coincide con la ventana de un deploy, el "arreglo" es coincidencia.

## Acceso y mapa de prod (169.58.189.222)
- `ssh -i /opt/data/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=no root@169.58.189.222` (key ya autorizada, solo publickey).
- Reloj de prod en **CEST (UTC+2)** → Bogotá = −7h. Convertir SIEMPRE antes de correlacionar logs.
- Servicios: webhook-gateway (Golden, 3099), webhook-paradise (Lucky, 3100), ActivePieces API en 100.73.30.29:8088, `ap-db` (postgres, flows + leads), nginx-proxy-manager delante, watchtower + coolify presentes (posibles recreadores).
- Fix propuesto (pendiente aprobación Admin, regla D-I-V-E): sacar `npm install` del command del compose (instalar una vez o hornear imagen propia) → reinicio de ~40s a ~2s y desaparecen los FAIL|000 fantasma.

## Quirks del entorno
- El contenedor Hermes no trae `ip`: usar `hostname -I`, `/proc/net/route` o `docker inspect`.
- El DNS interno NO resuelve los dominios de clientes (y el dominio puede estar mal apuntado en el mundo real — verificar con `https://dns.google/resolve?name=...&type=A` vía web_extract antes de concluir que un sitio "está caído").
- `docker events` sin `--until` queda colgado en stream: envolver siempre en `timeout`.
