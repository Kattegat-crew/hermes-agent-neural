---
name: prod-webhooks-audit
description: "Use when auditing Golden/Paradise webhooks in PROD"
tags: [webhooks, prod, golden-game, paradise, diagnostico, reason-codes, vigilancia, devops]
version: 1.0.0
author: NeuralCrew Labs
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [devops, vigilancia, webhooks, prod, golden-game, paradise]
    category: devops
    related_skills: [activepieces-selfhost-ops, nginx-proxy-manager-api]
---

# Prod Webhooks Audit Skill

Runbook de diagnóstico y reparación para los webhooks públicos de PROD (Golden Game y The Grand Paradise Club). No ejecutes arreglos en caliente: diagnosticá con la tabla de reason codes y proponé el fix gateado.

## When to Use

- Vigía reporta FAIL en `golden_webhook`, `paradise_webhook`, `golden_chat`, `paradise_chat`, `*_contract`, `*_public`, `activepieces`, `db_*` o `webhook_404_6h`.
- Usuarios/ads reportan que el chat, el bono VIP o el contacto "no funcionan".
- Cualquier deploy del gateway o de los landings.

## Arquitectura (para no romperla)

```
Cloudflare → NPM (edge) → landing nginx 9001/9002 (SPA + location /webhook/ con rate-limit)
                                 └─proxy_pass→ host 10.0.1.1:3099 (Golden) / :3100 (Paradise)
Gateway → infra-postgres 100.73.30.29 (golden_game / paradise_casino) + ActivePieces :8088 + Twenty :3020 + Meta CAPI
```
- El ruteo `/webhook/*` vive en el conf del landing (`location /webhook/`), **NO en NPM**. No agregues locations en NPM: saltaría el rate-limit del landing.
- `webhookLimiter` = 20/min/IP y `chatLimiter` = 10/min/IP. Los probes internos comparten bucket: una ráfaga de auditorías puede dar `429`.
- Twenty usa **una API key por marca** (misma URL): una key no ve las personas de la otra marca.

## Reason codes → causa → fix propuesto

| Código | Significado | Causa probable | Fix propuesto (con aprobación) |
|---|---|---|---|
| `health_404` / `chat_404` | La ruta no existe en el gateway vivo | Deploy reescribió el archivo y borró handlers | Restaurar handlers desde `*.bak-pre-redeem`/git y `deploy.sh` |
| `health_000` / `chat_000` | El backend no responde | Contenedor caído o puerto no bindeado | `cd /opt/docker/webhook-gateway && docker compose up -d` |
| `ai_fallback` | HTTP 200 pero reply = "dificultad técnica" | DeepSeek/proxy caído o lento | Revisar `DEEPSEEK_API_URL/KEY` en `.env` y logs del gateway |
| `golden_contract\|FAIL\|missing:<ruta>` | El bundle del landing pide una ruta que el gateway no tiene | Deploy del gateway dejó rutas faltantes | NO deployar; restaurar la ruta y `deploy.sh` |
| `routing_spa_fallback` | El POST público devuelve HTML 200 (SPA) | Se perdió el `location /webhook/` del landing o el proxy | Revisar el conf del landing (NPM/Cloudflare NO se tocan sin aprobación) |
| `routing_<code>` | La cadena pública falla | NPM/Cloudflare/DNS | Escalar al Admin con el código exacto |
| `ap_unhealthy` | ActivePieces no Healthy | Contenedor ap-db/ap-app | `docker ps` + `docker logs ap-app` |
| `db_error` | No conecta a `golden_game`/`paradise_casino` | infra-postgres caído o credenciales | Revisar `docker ps` (infra-postgres) y el item del vault |
| `count_N` (webhook_404_6h) | N usuarios reales rebotando 404 en 6 h | Igual que `health_404` | Escalado inmediato + fix de rutas |
| `simulado` | Corrida de prueba (`--simulate=`) | — | Ignorar (validación del sistema de alertas) |

## Procedure

1. Correr la auditoría: `bash /root/audit_remote.sh` (en PROD) o `python3 /opt/data/scripts/system-health-audit.py` (en DEV/Hermes).
2. Identificar los FAIL y su reason code en la tabla.
3. Publicar en Discord (webhook del canal de vigilancia): reason codes + causa probable + fix propuesto con comando exacto + `since`/`streak` del bloque `incident`.
4. El fix real se aplica así (nunca a mano):
   ```bash
   cd /opt/docker/webhook-gateway
   ./deploy.sh "mensaje"   # valida sintaxis+rutas+contrato, build, commit, recreate, smoke; rollback si falla
   ```
   Rollback manual de emergencia: `git checkout HEAD~1 -- webhook-server.js webhook-server-paradise.js && docker compose up -d --force-recreate`.
5. Re-auditar: 12/12 OK y `webhook_404_6h|OK|0`.

## Inspección read-only verificada (23-oct, diseño Pixel/CAPI)

Datos reales confirmados por SSH a PROD (útiles para cualquier diseño/diagnóstico del gateway):
- El contenedor de edge se llama `nginx-proxy-manager` (NO `npm`; ese nombre no existe).
- `webhook-gateway` expone `10.0.1.1:3099` y `webhook-paradise` `10.0.1.1:3100`; AMBOS montan el mismo bind `/opt/docker/webhook-gateway → /app` (código compartido: un deploy afecta a las dos marcas).
- Redes reales: `hermes_default` (10.0.5.x, gw 10.0.5.1) y `webhook-gateway_default` (10.0.6.x, gw 10.0.6.1). Los rangos 172.19/10.0.1 como pares Express NO están probados.
- Landings en contenedores efímeros de Coolify en `0.0.0.0:9001/9002` (publicado en 0.0.0.0 ≠ accesible desde internet: no asumir).
- Inspección sin exponer secretos: `docker inspect --format '{{.Name}} {{json .Mounts}} {{json .NetworkSettings.Networks}}' <cont>` — NUNCA inspect completo ni `docker exec env` (el .env del contenedor viaja en la salida). Conf de headers del edge: leer archivos `/data/nginx/...` con filtro por directivas (`proxy_set_header`, `real_ip`), redactando auth.

## Pitfalls

- No editar NPM, Cloudflare, Coolify ni los landings para "arreglar" `/webhook/*`.
- No reiniciar contenedores como primer reflejo: si el problema son rutas faltantes, el restart no cambia nada.
- `docker compose restart` re-ejecuta `node` (el código montado se relee), pero un deploy ordenado es `deploy.sh`.
- El `/health` **público** devuelve 200 HTML por el fallback del SPA: no es una señal válida; el `/health` del backend devuelve JSON.
- Los probes de chat escriben una conversación con `session_id=vigia-health` (limpiable periódicamente).

## Verification

- `bash /root/audit_remote.sh` → 12 líneas `|OK|` y sin bloque `incident`.
- La salida debe ser byte-estable entre corridas OK (es lo que mantiene silencioso al watchdog).
- Prueba de fuego: `bash /root/audit_remote.sh --simulate=<check>` → FAIL `simulado` + `incident|OPEN`; y la corrida siguiente → `incident|RECOVERED` y estado limpio en `/root/.vigia/`.
