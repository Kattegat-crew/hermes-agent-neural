---
name: campanas-qa-integridad
description: "Use when building campaign docs and QA gate."
tags: [campanas, qa, integridad, docx, gate, marketing, roshi]
---

# Campañas: paquete documental + gate QA-INTEGRIDAD

## Qué hace

Capa documental de Roshi dentro del pipeline de marketing multi-agente: a partir de un `campaign.yaml` (contrato único, fuente de verdad) genera los 5 docs de campaña (.docx) y un **gate binario de integridad** (`QA-INTEGRIDAD.md` + `.json`) que los bots downstream (Content Bot, Review Bot, perfil de QA) consumen para decidir sin intervención humana.

## When to Use

- Armar una campaña nueva: brief → docs → validación.
- Entregar un "pack" de campaña al equipo de bots (Review Bot presenta, cliente aprueba).
- Necesitar un veredicto automático (OK / REVISAR) sobre legal, fechas, marca y coherencia antes de producir piezas.

## Prerequisites

- `python-docx` y `pyyaml` instalados.
- Esqueleto listo y probado: `/root/hermes-agent-legacy-docker/data/profiles/roshi/workspace/campaigns/template/` (`campaign.yaml`, `build_campaign.py`, `generate_docs.py`). `demo/` = caso de prueba con empresa ficticia.
- Los 5 .docx los genera el módulo `generate_docs.py` (del skill global `marketing-campaign`); NO reimplementar ese generador.

## How to Run

```bash
cd /root/hermes-agent-legacy-docker/data/profiles/roshi/workspace/campaigns
python3 template/build_campaign.py <campaña>/campaign.yaml --output <campaña>/docs/
```

Salida: 5 .docx + `QA-INTEGRIDAD.md` + `QA-INTEGRIDAD.json`. Exit code 0 = OK, 1 = REVISAR.

## Gate QA-INTEGRIDAD (el formato)

- **Estado binario**: `OK` = listo para QA de ejecución / `REVISAR` = hay issues bloqueantes.
- **Issues (bloqueantes)**: legal sin regulador, edad < 18, retención 0, falta política de datos, nombre comercial vacío, `start_date` inválida (YYYY-MM-DD). Items como `- [ ]`.
- **Warnings (no bloqueantes)**: promoción vacía, sedes en `featured_sedes` que no están en `company.sedes`.
- Siempre emitir **`.md` (legible) + `.json` (parseable con la misma data)** — los bots parsean el JSON, no el texto.
- Ver ejemplo completo en `references/qa-integridad-formato.md`.

## Deploy de superficie web de campaña (reels/portal/landing)

Cuando el equipo publica o reemplaza una superficie web de campaña en prod (ej. Portal de Campañas sobre reels-web :9020 → reels.neuralcrewlabs.com), Roshi no construye: hace QA. **Antes** del deploy captura la línea base con curl (HTTP, bytes, title de cada URL viva) y **después** ejecuta el smoke (portada nueva, contenido nuevo presente, URLs heredadas intactas, routing NPM sin cambios). Regla fija de arquitectura (orden del usuario, 02/sep/2026): servidor .250 = SOLO desarrollo (nada público sale de ahí, staging se sube a prod por Tailscale); servidor .222 = prod con NPM (:80/:443) como ÚNICO dueño del tráfico público vía Cloudflare y DNS de subdominios siempre al .222. Contrato de URL: un redeploy de página viva NO cambia rutas existentes (ej. `/lucky/bingo/` ya compartida). Receta completa: `references/web-deploy-baseline-smoke.md`.

## Motor de reels: guiones + escenas (quién tiene qué)

La producción de guiones, escenas (keyframes generados con GPT), animación 9:16 y portales de revisión NO es de Roshi: vive en el repo del generador, `/root/marketing-campaign-generator/` (= `/host/root/marketing-campaign-generator/`, git `Kattegat-crew/marketing-campaign-generator`) con el servicio `reel-worker.service` (:8090). Inventario completo —dónde viven los guiones, los keyframes, el contrato `scene-plan`, la salida en PROD y los crons— en `references/generador-reels-guiones-escenas.md`. Roshi aporta el gate documental/QA y, si toca automatizar, trabaja sobre ese repo in-place (no clonar copias nuevas).

**Cuando pregunten "¿el generador funciona así?" o haya que auditar una infografía/README/plan contra la realidad:** el
veredicto se levanta con **sondas en vivo** (gate de gasto, worker, crons, `flow_run` de ActivePieces, `calendario.jsonl`),
no leyendo documentación — receta, comandos exactos y tabla de estado por eslabón en
`references/verificar-generador-campanas.md`. Un "✅" del README **no** es evidencia.

## Mapa vivo: Drive ↔ superficie web (relevado con evidencia)

Cuando piden "las ubicaciones y recursos que se están utilizando" (Drive, dominios, servicios) la respuesta se levanta **con evidencia** — Drive vía API, dominios vía la sqlite de Nginx Proxy Manager en prod, servicios vía `ps`/`systemctl` del host — nunca de memoria. Mapa completo (rutas de campaña con IDs, subcarpetas de escenas/guion por reel, tabla dominio→upstream, SSO `oauth2-proxy-universal`, cadena de publicación dev→prod y link de revisión con token) en `references/mapa-drive-web-campanas.md`; para re-relevar: `scripts/drive_map_campanas.py` con `/opt/data/.venv/bin/python`.

## Reglas de oro (pitfalls)

- **NUNCA inventar datos**: lo que no esté en el YAML sale como `[PENDIENTE DE CONFIRMAR]`. Checks del script lo garantizan.
- **División multi-agente**: Content/Visual/Review Bots CONSUMEN el paquete (yaml + docs + QA) — nunca reimplementan la generación de estructura, o hay dos verdades que se pelean.
- **Versionar los packs por campaña**: carpeta `Campañas/<slug>/` con docs + QA de cada versión aprobada (v1, v2...) para trazabilidad ante el cliente.
- **Legal gate antes de publicar**: nada sale a Social/Ads sin el QA-INTEGRIDAD en OK + aprobación del Review Bot.
- **Generador de reels y reel-worker:** `reel-worker.service` vive en el host con `WorkingDirectory=/root/marketing-campaign-generator`, puerto :8090 (`/health` OK). El repo físico del host está verificado y activo.
- **Correr scripts del repo:** los que necesitan dependencias del `.venv` (edge-tts, etc.) se ejecutan **en el host** con `ssh dev` y `/root/marketing-campaign-generator/.venv/bin/python`; el `python3` del contenedor basta para los stdlib-only.
- **Temporales en el host:** lo que crees por `ssh` queda root-owned y no se puede borrar desde el contenedor (`Permission denied`); se limpia con el mismo `ssh`.
- **Estado vs. diseño:** separar "existe el código" ≠ "corrió de verdad" ≠ "está roto (ENABLED pero falla)" antes de afirmar que un eslabón opera.
- **Convención multi-tenant de conexiones** (para los bots del equipo): `{tenant}-{servicio}` (ej. `helmer-gmail`, `golden-meta-ads`, `jonathan-canva`); mapa lógico en Engram (`topic_key: connections-map`), credenciales NUNCA en el mapa. Si falta la conexión, reportar — no adivinar.

## Verification

- `build_campaign.py` imprime: 5/5 docs generados y verificados, Legal ✓, y QA con Issues/Warnings.
- Confirmar que `QA-INTEGRIDAD.json` tiene `status` y que el exit code coincide (0 ↔ OK).