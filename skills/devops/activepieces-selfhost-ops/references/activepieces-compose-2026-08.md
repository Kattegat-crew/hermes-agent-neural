# ActivePieces — Stack en VPS dev (state verificado 21/08/2026)

> Captura de diagnóstico real. No confundir "instalado" con "corriendo": los
> contenedores estaban `Exited (137)` — OOM probable.

## Ubicación y servicios

- Ruta repo/compose: `/root/activepieces/` (host 10.0.7.1, SSH root).
- `docker-compose.yml` services:
  - `ap-app` — image `activepieces/activepieces:latest`, puerto `8088:80`, env `AP_CONTAINER_TYPE=APP`, `restart: unless-stopped`.
  - `ap-worker` — misma imagen, `AP_CONTAINER_TYPE=WORKER`, `restart: unless-stopped`.
  - `ap-db` — `pgvector/pgvector:0.8.0-pg14`, env `POSTGRES_DB/PASSWORD/USER` desde `.env` (`AP_POSTGRES_DATABASE`, `AP_POSTGRES_PASSWORD`, `AP_POSTGRES_USERNAME`).
  - `ap-redis` (dependencia; las líneas estaban en el compose original).
  - Red `ap-net`, volumen `./cache:/usr/src/app/cache`.
- `.env` presente en `/root/activepieces/.env` (fuente: postgres creds para ap-db).

## Estado del proceso (docker ps -a en el host)

```
ap-app     Exited (137) 4 days ago   activepieces/activepieces:latest
ap-worker  Exited (137) 4 days ago   activepieces/activepieces:latest
```

Síntoma: exit 137 en ambos; la UI en 8088 podría no contestar (no verificado en vivo).

## Chequeos siguientes (pendientes de ejecutar)

- `docker inspect -f '{{.State.OOMKilled}}' ap-app ap-worker` → true = OOM del kernel.
- `docker compose up -d --force-recreate` para revivir.
- `mem_limit` por servicio + `restart: on-failure:5` para que reviva tras OOM.
- Inventariar RAM total usada por el host (Hermes+web+Coolify+Orca+postgres) antes de subir AP.
- Una vez vivo: mapear conexiones por cliente y crear el cron de salud.

## Connections sample (planeado, no ejecutado)

El plan de integraciones de la casa va por aquí (visto en sesión 21/08):
- Meta Ads: system user token.
- Google: service account + domain-wide delegation (automatización).
- Canva: Connect API con refresh persistido.
- Alerta de salud con cron a WhatsApp (misma infra de alertas que pico y placa).