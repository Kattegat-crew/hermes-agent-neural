---
name: activepieces-selfhost-ops
description: "Use when fixing a down self-hosted ActivePieces stack."
tags: [activepieces, docker, oom, compose, self-hosted, devops]
author: Ragnar
version: "1.0"
created: 2026-08-21
category: devops
metadata:
  hermes:
    tags: [activepieces, integraciones, oauth, mcp, conexiones, self-hosted]
    related_skills: [hermes-ecosystem-tools, vps-host-access]
---

# ActivePieces Self-Hosted — Conexiones, MCP y Operación

## When to Use

- Diagnóstico de ActivePieces caído / `Exited` en el VPS.
- Diseño de la capa de integraciones y autenticación de agentes (Google, Meta/Canva, correo, webhooks).
- Exponer piezas de AP como MCP a Hermes/agentes.
- Conexiones por cliente (multi-tenant) sin credenciales a mano.

## Dónde vive (VPS dev, verificado 21/08/2026)

- Ruta: `/root/activepieces/` en el host (SSH root@10.0.7.1).
- Docker compose: `ap-app` (UI/API, puerto `8088:80`, env `AP_CONTAINER_TYPE=APP`), `ap-worker` (worker, `AP_CONTAINER_TYPE=WORKER`), `ap-db` (pgvector/pgvector:0.8.0-pg14), `ap-redis`. Red `ap-net`, volumes `./cache`.
- Estado observado: contenedores `Exited (137)` hace días → típicamente **OOM / kill externo**, NO reintento normal (por eso "se cae cada rato").
- No aparece en `docker ps` del contenedor hermes-agent (namespace propio); inspeccionar desde el host.

## Levantar / reparar

```bash
ssh root@10.0.7.1 "cd /root/activepieces && docker compose up -d --force-recreate"
ssh root@10.0.7.1 "cd /root/activepieces && docker compose logs --tail=50 ap-app ap-worker"
```

Para OOM recurrente:
- `docker inspect -f '{{.State.OOMKilled}}' ap-app` — true = OOM confirmado.
- Agregar `mem_limit` a ap-app (~750MB) y ap-worker (~750MB) + `restart: on-failure:5` o `unless-stopped`.
- Comprobar RAM total del host antes: si el stack completo (Hermes, Coolify, Orca, web, postgres) ya consume casi toda la RAM, ninguna config de AP la arregla sola — hay que liberar o priorizar.

## Modelo: capa de integraciones y autenticación

```
Hermes/Ragnar (MCP client) → ActivePieces (:8088) → apps (Google, Meta, Canva, Notion…)
      → CONNECTIONS: OAuth por cliente guardado en Postgres (refresh automático, backoff)
      → WORKFLOWS: triggers webhook/schedule, acciones con auth resuelta
      → MCP: cada pieza se expone como tool MCP al agente
```

- **Conexiones persistentes (anti-caídas):** OAuth se completa UNA vez por conexión; AP guarda refresh token cifrado en su Postgres y el access token se refresca solo. Cada **cliente = una conexión separada** (Golden ↔ Lucky independientes). Un token expirado de un cliente no tumba al otro.
- **Meta Ads:** preferir system user token (Business Manager) + rotación, no token de usuario de 60 días.
- **Google:** service account con domain-wide delegation para automatización; OAuth per-user solo para clientes puntuales.
- **Canva:** Canva Connect API + refresh persistente por cliente.
- **Exponer a Hermes:** configurar el MCP server de ActivePieces apuntando a la URL de la app (ver `hermes-mcp` / `hermes-ecosystems-tools`).

## Health-check / vigilancia

- Cron diario: `docker compose ps` (o puerto 8088) + alerta WhatsApp si un service no está `running` o si alguna conexión lleva < 4 días del refresh. Indispensable antes de desplegar a clientes.
- Log del estado y decisiones en `vps-brain/HISTORIAL_Y_CONTEXTO_VPS.md`.

## Pitfalls

- No confundir "Activo en la UI" con "contenedores vivos": la UI puede servir desde cache mientras los workers están muertos.
- `Exited (137)` ≠ error de app; es OOM — revisar `docker inspect` OOMKilled.
- `restart: unless-stopped` no siempre revive tras OOM del host — por eso monitor de salud real, no solo `docker compose up -d`.

## Referencias

- `references/activepieces-compose-2026-08.md` — copia del docker-compose.yaml y layout encontrado en el host.
- Stack conexo: Coolify, orca-serve, hermes-serve, etc. (ver `vps-host-access`).