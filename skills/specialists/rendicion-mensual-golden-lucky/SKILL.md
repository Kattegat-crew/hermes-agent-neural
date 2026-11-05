---
name: rendicion-mensual-golden-lucky
description: Use when running the Golden/Lucky rendición automation.
tags: [rendicion, golden, lucky, breb, elevenlabs, cron]
---

# Rendición mensual Golden Game + Lucky Brothers

Automatización en `/opt/data/scripts/rendicion-mensual/` (código fuente de verdad, README.md ahí). Cron Hermes `rendicion-mensual-dryrun` (job de4296822acf): día 1 de cada mes 06:00 America/Bogota, `run_rendicion.sh` sin args = dry-run.

## Reglas duras

- **Nunca inventar cifras.** Todo campo no obtenido va como `{"sin_dato": true, "motivo": ...}` en facts. El render de videos se bloquea si faltan ventas/meta/cumplimiento/breb/ads.
- **TTS es gated**: `TTS_APPROVED=1` explícito + tope $2/mes impuesto en `tts_elevenlabs.py` con MANIFEST por request (`ELEVENLABS_MANIFEST.jsonl`). Voces fijas: Golden=Angie `YPh7OporwNAJ28F5IQrm`, Paradise=Daniela `tTdCI0IDTgFa2iLQiWu4`, modelo `eleven_multilingual_v2`.
- **Publicación gated**: `APPROVED=1 run_rendicion.sh --full --upload-drive`. Sin eso, staging local + Discord solamente.
- Cron scripts: rutas relativas a `/opt/data/scripts/` (hermes cron exige relativo a ese root); dentro del script resolver con `readlink -f`.

## Estructura Drive canónica (REGLA DURA)

Ver skill `estructura-drive-neuralcrew`. Los entregables de rendición van SIEMPRE en `<Cliente>/05-informes/rendicion-de-cuentas/YYYY-MM/` (upload_drive.py ya lo hace así). Prohibido crear carpetas fuera de la estructura canónica.

## Fuentes verificadas (nov 2026)

- Bre-B: hojas Drive `Bre-B Golden/Lucky — Pagos`, tab `Informe <Mes>`, tabla `POR DÍA` (A1:C100) → pagos + total exactos; cross-check contra celda `TOTAL RECAUDADO` (si no cuadra >0.1%, sin_dato). IDs en `lib_gdrive.py::BREB_SHEETS`.
- Ventas por sede: hoja `<MM-YY> ventas <marca>` — visible desde el 04-nov-2026 (Plon compartió las carpetas con las creds de cliente `golden/lucky-drive.json`); el parser genérico Sede|Venta|Meta la levanta sola (verificado: Golden 2026-10, 7 sedes). Ya NO queda sin_dato por permisos.
- Facebook + Instagram: automatizados con `social.py` (Graph API v21) desde nov-2026 — fuente primaria, marca `fuente=graph_api` en el fact. FB: page tokens de larga vida en `/opt/data/secrets/rendicion_social_pages.json` (de la conexión Composio `facebook_uncite-skyish`; NUNCA expiran, el system-user token de meta_ads_system_user.env expiró el 19-oct-26). IG: conexiones Composio `instagram_demal-molala` (Golden) / `instagram_scot-linked` (Paradise) vía MCP-over-HTTP con la key de `/opt/data/secrets/composio_consumer.key`.
- Meta Ads / Search Console / agentes CRM: siguen manuales, exports en `inputs/` (schemas en README). `business_suite_<marca>.csv` quedó como SOLO fallback de la API; regenerarlo cada mes (no lleva mes en el nombre).
- Docs: plantilla del mes anterior editada in-place (python-docx venv `/opt/hermes-agent-data/cache/scratch/venv-docs/bin/python`, tiene docx 1.2.0; system python NO tiene docx) + soffice. Tables mapeadas por encabezado; filas por agente de lucky no se tocan; párrafos narrativos con cifras quedan listados en `revision_pendiente.md` para revisión humana.

## Lecciones

- La hoja de ventas consolidada tiene columnas META MENSUAL | ACUMULADO(venta) en ese orden: NUNCA asumir venta-primero; el parser mapea columnas por encabezado (colmap) desde el fix 04-nov-2026. Si una hoja nueva cambia nombres, el colmap debe reconocerlos.
- Business Suite NO es reproducible 1:1 por Graph API: el export manual mezcla stories del mes (expiran, sin insights) y dedup mensual de espectadores no expuesto. Métrica API adoptada: vistas lifetime del contenido publicado en el mes (Golden oct: 11.522 vs export 11.900, −3,2%). FB parcial: page tokens en /opt/data/secrets/rendicion_social_pages.json; IG via conexiones Composio instagram_demal-molala (Golden) / instagram_scot-linked (Paradise) con consumer key en /opt/data/secrets/composio_consumer.key. Faltan instagram_basic/manage_insights en el app de la conexión facebook (el page token no expone la cuenta IG).
- `parse_num` es-CO: punto=miles si todos los grupos posteriores tienen 3 dígitos, si no decimal (las fechas serial de Sheets tipo `46266,42708` se confunden con montos si no).
- Notificar a Discord desde scripts: token vía env → `/opt/hermes-agent-data/.env` → hydrate_profile_secret_sources; destino = **hilo FIJO `📊 Rendición mensual` (1567660948058275872) en el foro digital-vikings** (1554961885160415283, mapa Discord 2026-11-04 — crons-bragi está ARCHIVADO). `notify_discord.py` reutiliza el hilo (active+archived), lo reabre si está archivado y solo lo crea si no existe; una corrida = un mensaje. Fallback: alertas-prod 1557152614045581373. Override con `RENDICION_DISCORD_CHANNEL`/`RENDICION_DISCORD_THREAD`.
- Antes de tocar el cron de Hermes: backup de config.yaml + state.db de ambos homes en `~/.hermes/backups/`.
- Business Suite UI no es reproducible 1:1 por API: el export manual de FB (Golden oct-26: 11,9 mil / +46,4% / 4.988 espectadores / 97,4% no seguidores) incluye stories (expiran, sin insights por API) y dedup mensual de espectadores (la API solo da uniques diarios; breakdown is_from_followers no soportado). La métrica API adoptada = vistas lifetime del contenido publicado en el mes (posts+reels, dedup por fecha+views); el fact anota la brecha contra el export cuando existe. Golden oct-26: API 11.522 vs export 11.900.
- Reels de FB no exponen `/insights` (error "nonexisting field"): sus vistas se leen del campo `views` del objeto; un video publicado como post y como reel comparte el número de vistas → dedup por (fecha, vistas) para no contar doble.
- IG por Graph API: alcance/interacción con `metric_type=total_value` y since/until en epochs de Bogotá (los strings de fecha dan totales levemente distintos); seguidores ganados = suma de la serie diaria `follower_count` (deltas, no absolutos); publicaciones del mes = paginar `/me/media` hasta pasar el límite del mes.