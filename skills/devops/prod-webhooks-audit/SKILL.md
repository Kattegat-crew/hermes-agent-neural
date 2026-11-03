---
name: prod-webhooks-audit
description: "Use when auditing Golden/Paradise webhooks in PROD"
tags: [webhooks, prod, golden-game, paradise, diagnostico, reason-codes, vigilancia, devops]
version: 1.1.0
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

## Auditoría de conversión de leads (no solo salud)

Cuando el síntoma es "no llegan leads" y los checks de salud pasan (12/12 OK), la salud del webhook NO es el diagnóstico. Cadena verificada en la auditoría Lucky-vs-Golden (27-oct-2026, causa raíz: CTA oculta en móvil, no el webhook):

1. **Serie de leads real (PRIMERO, delimita el problema):**
   `docker exec infra-postgres psql -U postgres -d paradise_casino -Atc "SELECT count(*), max(created_at) FROM leads;"` (y `golden_game`). Si el último lead es viejo, todo lo demás se ordena por esa fecha.
2. **Prueba end-to-end controlada:** POST al webhook público con payload válido marcado como prueba (`email=test+audit@...`), verificar `leadId` y fila en PG, y BORRAR el registro inmediatamente (restaurar el count exacto). Esto separa "captura rota" de "tráfico sin conversión".
3. **Contar POSTs reales por endpoint vía logs del edge:**
   `docker exec nginx-proxy-manager sh -c "grep -E 'POST https' /data/logs/proxy-host-2_access.log | grep -oE '/[a-z0-9/_-]+\"' | sort | uniq -c | sort -rn | head -10"`
   proxy-host-1 = golden, proxy-host-2 = paradise/lucky. Filtrar con referer in-app de Meta (FBAN/FBAV + fbclid/utm) para aislar tráfico pagado humano. Compara POSTs de form vs POSTs de chat: 200+ chats y 0 submits = usuarios llegan pero no encuentran el camino al formulario.
4. **Verificar dónde aterriza la pauta y en qué viewport:** la pauta Meta cae en móvil in-app 100%. Simular `Emulation.setDeviceMetricsOverride` 390x844 y listar CTAs VISIBLES (`getBoundingClientRect().width>0`) — no basta con que el botón exista en el DOM.
5. **Paridad de builds:** descargar los bundles/chunks servidos de ambos landings y comparar endpoints de submit, formulario (inputs, sede selector) y reglas CSS. La regla culpable se encuentra con: `grep -o '@media[^{]*{[^}]*header-cta[^}]*}' main-*.css`.

Leads de datos de esa auditoría: Golden 55 leads (último mismo día) vs Lucky 29 (último 13-oct); tráfico casi idéntico (3.6k vs 3.7k requests/día); el flujo de Lucky funcionaba end-to-end — el fallo era UX: en `/eventos` móvil el botón "¡GANA TU BONO!" desaparecía por `@media(max-width:860px){.header-cta .btn{display:none}}` y el menú hamburguesa no tenía entrada al bono. Golden convierte; Lucky no.

## Drift de deploy y tracking incompleto (verificado 27-oct-2026)

Hallazgos confirmados en vivo que cambian el diagnóstico antes de tocar código:

1. **El gateway desplegado es un fork divergente:** PROD corre `/opt/docker/webhook-gateway/webhook-server-paradise.js` (repo git aparte, con ficheros sin commitear), mientras que los repos de los landings llevan su propia copia evolucionada (`server/webhook-server.js` + `server/tracking/*`). Antes de "activar" una feature nueva, verifica DÓNDE vive el código que corre: el feature puede estar escrito en el repo del landing pero nunca portado al gateway.
2. **Tracking fail-closed ≠ solo config:** si `GET /api/tracking/status` responde `200 text/html` con el peso del index del SPA, la ruta no existe ni en el gateway ni en el proxy del landing — el cliente fail-closed no carga `fbevents.js` y Meta recibe cero señal de navegador. Poner `META_TRACKING_MODE=LIVE` en el `.env` es un **no-op** si el router no está montado y proxado.
3. **Drift de deploy (3 capas a comparar):** `git ls-remote origin main` (GitHub) vs hash local (`git log --oneline -1`) vs `docker inspect <contenedor-landing> --format '{{.Config.Env}}' | grep SOURCE_COMMIT` (lo que realmente corre Coolify). Commits locales sin push NUNCA llegan a producción aunque Coolify redespliegue.
4. **Drift de env:** editar el `.env` del host NO afecta al contenedor corriendo y `docker compose restart` NO recarga environment (el env se inyecta al crear el contenedor). Sintoma típico: el `.env` ya tiene el modelo/CORS corregidos pero `docker exec <cont> env` muestra los viejos. Fix: `docker compose up -d --force-recreate` (con backup del `.env` previo). Probar el modelo real desde dentro: `docker exec <cont> node -e "...fetch..."` para ver el 401/200 real, no el del host.
5. **Sonda CORS de un tiro (separa CORS de validación):** repetir el mismo POST cambiando solo el header `Origin` (http vs https). `403 Acceso denegado.` con http + 400/201 con https = CORS funciona y el problema es que los clics aterrizan en `http`. Si `http://` sirve 200 sin redirect, además del 403 hay PII (nombre/cédula/teléfono) viajando en claro y contenido duplicado SEO; el fix es Cloudflare → SSL/TLS → *Always Use HTTPS* (toggle, sin código, rollback de 1 clic).
6. **Peso de entrada medible sin Lighthouse:** sumar `size_download` de todos los `/assets/*.js` referenciados por el HTML servido — con tráfico in-app de Meta (3G/4G), >300 KB de JS antes del CTA es fricción medible (lazy-load del chat y de librerías de animación).

## Pipeline de notificación de leads: cron (PG) vs webhook firmado (AP) — verificado 28-oct-2026

Causa raíz del GAP de cobertura (cron veía 100% de leads, webhook 0 eventos): **el webhook firmado a Hermes se agregó al flow equivocado de ActivePieces**.

**Arquitectura real de captura (no la que uno asume):**

```
landing → webhook-gateway :3099 (PROD) → PG insert + Twenty + Meta CAPI
                                        └─POST fire-and-forget (8s timeout)→ AP "Flow bono Golden" (webhook trigger, env ACTIVEPIECES_WEBHOOK_URL)
Flow bono Golden (AP): email VIP → notificación interna → insert Sheets "Registro bonos"
```

- El gateway **NUNCA** llama a los flows "Leads → Sheets (insert only)": su código solo tiene una URL de AP (verificar con `grep -n 'ACTIVEPIECES_WEBHOOK_URL' /opt/docker/webhook-gateway/webhook-server.js`). El payload que envía es el lead JSON completo (incluye `created_at`, `name`, `cedula`, `phone`, `email`, `sede`, `bonus_amount`, `utm_source/medium/campaign`, `fbc/fbp`).
- El webhook firmado a Hermes (HMAC `X-Hub-Signature-256` → `http://100.86.8.81:8644/webhooks/lead-nuevo`, ruta Discord `#ullr-leads`) vive en los flows "Leads → Sheets", que reciben **cero runs reales** (solo tests QA). Resultado: 0 eventos de webhook desde su publicación mientras el cron `leads-alertas` (lee la PG de PROD directo) ve todo.

**Técnica forense para identificar la vía real de inserción (cuando el log original ya rotó/podó):**

1. Cron outputs de días pasados suelen estar podados y `agent.log` rota rápido — no contar con ellos; reconstruir por otras vías.
2. Correlacionar el historial de runs de AP contra `leads.created_at` de la PG: si los runs de un flow coinciden **al segundo** con cada lead real, ese es el flow por el que pasa el tráfico real (los flows Sheets solo mostraban tests `QA-`).
3. Listar TODOS los flows por proyecto (`ap_list_flows` project=jonathan / lucky): el flow real puede llamarse "Flow bono ...", no contener la palabra "lead".
4. Verificar en el código del gateway si alguna vez llamó al flow sospechoso: cero referencias = cero llamadas, sin importar la config.
5. La conectividad PROD AP → DEV Tailscale (`100.86.8.81:8644`) queda probada si los tests e2e del flow webhook entregaron; la causa del GAP será de RUTA (flow equivocado), no de red.

**Fix pattern (gateado, alta impacto):** agregar a los flows de bono (Golden + Paradise) los pasos ya validados de los flows Sheets: paso CODE "Firmar lead (HMAC)" (crypto-js) + paso HTTP POST firmado con `failureMode: continue_all` y timeout 5s (si DEV está caído no rompe el email del bono). Publicar, probar con lead sintético `QA-`, re-correr el coverage check (cron vs webhook events) y recién ahí degradar la frecuencia del cron.

## Pitfalls

- No asumir que un webhook firmado publicado "funciona" porque los tests e2e pasaron: identificar en QUÉ flow vive y si los leads reales pasan por ese flow (correlación de timestamps runs ↔ PG).
- Evidencia efímera: outputs del cron se podan y `agent.log` rota en días — capturar la evidencia original en caliente o documentar el método de reconstrucción.

- No editar NPM, Cloudflare, Coolify ni los landings para "arreglar" `/webhook/*`.
- No reiniciar contenedores como primer reflejo: si el problema son rutas faltantes, el restart no cambia nada.
- `docker compose restart` re-ejecuta `node` (el código montado se relee), pero un deploy ordenado es `deploy.sh`.
- El `/health` **público** devuelve 200 HTML por el fallback del SPA: no es una señal válida; el `/health` del backend devuelve JSON.
- Los probes de chat escriben una conversación con `session_id=vigia-health` (limpiable periódicamente).
- `/api/tracking/consent` NO está proxado en NINGÚN dominio: devuelve el index del SPA (HTML 200) y el POST muere con 405. Si se implementa consentimiento de pixel, primero agregar el location al landing nginx (no a NPM).
- Headless falso-positivos al probar el juego de bonos: (a) el tab en background (`document.hidden:true`) congela la animación rAF → el modal nunca "termina de girar"; usar `Emulation.setFocusEmulationEnabled` / foco real antes de concluir "bug". (b) `localStorage` puede contener estado de un spin anterior ("YA RECLAMASTE TU TIRO") → `localStorage.clear()` y recargar para simular usuario nuevo.
- Los landings se redespliegan (Coolify) y el build servido cambia: bajar los assets del DOM vivo (hash en `main-<hash>.js/.css`), no asumir el bundle del repo local.

## Verification

- `bash /root/audit_remote.sh` → 12 líneas `|OK|` y sin bloque `incident`.
- La salida debe ser byte-estable entre corridas OK (es lo que mantiene silencioso al watchdog).
- Prueba de fuego: `bash /root/audit_remote.sh --simulate=<check>` → FAIL `simulado` + `incident|OPEN`; y la corrida siguiente → `incident|RECOVERED` y estado limpio en `/root/.vigia/`.
