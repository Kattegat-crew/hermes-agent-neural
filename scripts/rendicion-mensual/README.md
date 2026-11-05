# rendición-mensual — automatización Golden Game + The Grand Paradise Club

Automatización de la rendición de cuentas mensual (día 1 de cada mes, 06:00
America/Bogota) reusando el pipeline V2 de octubre 2026. El cron corre SIEMPRE
`run_rendicion.sh --dry-run`. La subida a Drive y el envío al cliente son MANUALES
(gate humano: `APPROVED=1 run_rendicion.sh --full --upload-drive`).

## Componentes

| Script | Qué hace |
|---|---|
| `run_rendicion.sh` | Orquestador (`--dry-run` / `--full`). Copia entregables a staging local + notifica a Discord. Nunca publica. |
| `consolidar_facts.sh` (+ `.py`) | Compila `facts_<marca>.json` del mes anterior desde fuentes reales. Lo que no se obtiene queda `{"sin_dato": true}` — NUNCA se inventa. |
| `social.py` | Facebook + Instagram vía Graph API v21 (page tokens de larga vida + IG vía conexiones Composio). Es la fuente primaria de las cifras FB/IG; el export manual de `inputs/` queda como fallback. |
| `validar_facts.py` | Compara estructura contra el schema canónico de octubre (`videos-rendicion-oct2026/facts_*.json`). |
| `generar_docs.py` | DOCX+PDF del mes: plantilla del mes anterior editada in-place con python-docx + LibreOffice, tablas desde facts. |
| `generar_videos.sh` | Pipeline V2: guion desde facts → locución ElevenLabs (gated) → timeline audio-first → render 16:9 + 9:16 → mix −16 LUFS → verify_v2. `--dry-run` valida sin gastar TTS. |
| `gen_guion.py` | Locuciones (9 beats, números en letras) + tarjetas, 100% facts-driven. |
| `tts_elevenlabs.py` | Voces fijas: Golden=Angie `YPh7OporwNAJ28F5IQrm`, Paradise=Daniela `tTdCI0IDTgFa2iLQiWu4`, modelo `eleven_multilingual_v2`. Tope $2/mes + MANIFEST por request. Requiere `TTS_APPROVED=1`. |
| `notify_discord.py` | Resumen al canal de ops (⚔️・digital-vikings, forum → crea thread). |
| `upload_drive.py` (+ `.sh`) | Sube staging a `<Cliente>/05-informes/rendicion-de-cuentas/<YYYY-MM>/`. Solo con el gate. |

## Fuentes de datos (consolidar_facts.py)

1. **Bre-B** — hojas `Bre-B <Marca> — Pagos` (Drive): tab `Informe <Mes>`, tabla
   `POR DÍA` → total + pagos + ticket; tab del mes anterior → comparativo. VERIFICADO:
   octubre golden reproduce exactamente $50.429.800 / 426 pagos / ticket $118.380.
2. **Ventas por sede** — busca hoja `<MM-YY> ventas <marca>` (patrón oct:
   `10-26 ventas golden`) en la carpeta datos-ventas. Si la hoja no está visible con
   las credenciales disponibles → `sin_dato`. Parser genérico (Sede|Venta|Meta).
3. **Facebook + Instagram (social.py, Graph API v21)** — fuente PRIMARIA desde
   nov-2026, sin export manual. Credenciales en `/opt/data/secrets/rendicion_social_pages.json`
   (page tokens FB de larga vida de la conexión Composio `facebook_uncite-skyish`;
   IG vía conexiones Composio `instagram_demal-molala`/`instagram_scot-linked` con la
   consumer key de `/opt/data/secrets/composio_consumer.key`). Marca `fuente=graph_api`
   en el fact. Genera:
   - `facebook`: visualizaciones (vistas lifetime del contenido publicado en el mes,
     posts+reels con dedup) + variación vs mes anterior con la misma métrica.
     NO expuesto por la API → sin_dato con motivo: espectadores deduplicados del mes,
     % no seguidores (breakdown `is_from_followers`) y stories del mes (expiran; el
     edge `/stories` viene vacío). Por eso el valor API es levemente inferior al
     export manual: Golden 2026-10 API 11.522 vs export 11.900 (brecha −3,2% = stories);
     Lucky 9.101 vs 10.500. La suma calendario oficial (`page_media_view`) va en la
     nota del fact como referencia.
   - `instagram` (nuevo, ambas marcas): seguidores ganados (headline), más
     `instagram_publicaciones`, `instagram_alcance`, `instagram_interaccion` — todo
     real de graph.instagram.com vía Composio MCP (o `ig_token` directo si se agrega
     a la config). Debug: `python3 social.py --marca golden --mes 2026-10`.
4. **Meta Ads, Search Console, agentes CRM** — siguen MANUALES, exports en `inputs/`:
   - `meta_ads_<golden|paradise>.json`: `{"spend": 430484, "leads": 13, "nota": "..."}`
   - `gsc_<golden|paradise>.json`: `{"impresiones": 96, "clics": 3, "ctr": "3,12%"}`
   - `agentes_<golden|paradise>.json`: `{"tareas": 297, "horas": 250, "nota": "..."}`
   - `business_suite_<golden|paradise>.csv` — SOLO FALLBACK (si la Graph API falla):
     columnas `facebook_views[, instagram_followers]`. Si existe mientras la API
     responde, se usa solo para anotar el cross-check (brecha %) en la nota del fact.
   Sin el archivo ni API → `sin_dato` (nunca inventa). El CSV debe regenerarse cada
   mes (no lleva mes en el nombre): NO dejar el del mes anterior en `inputs/`.

## Salidas

```
/opt/hermes-agent-data/home/proyectos/rendicion-mensual/<YYYY-MM>/
├── facts/facts_golden.json · facts_lucky.json   (schema octubre; sin_dato marcado)
├── docs/  DOCX + PDF + revision_pendiente.md    (párrafos a revisar por Plon)
├── videos/ (solo --full) 4 MP4 16:9 + 9:16
├── staging/  copia de entregables + resumen para revisión
└── logs/
```

## Cron (registrado en Hermes)

- `rendicion-mensual-dryrun`: `0 6 1 * *` America/Bogota →
  `/opt/data/scripts/rendicion-mensual/run_rendicion.sh --dry-run --no-discord`…
  (ver job real con `hermes cron list`). Solo dry-run. El `--full` lo ejecuta
  Plon a mano tras aprobar un dry-run.

## Gates (heredados del KANBAN oct)

1. Datos: nada entra al guion que no esté en facts con su fuente.
2. `sin_dato` en ventas/meta/cumplimiento/breb/ads → videos NO se renderizan.
3. Gasto TTS: `TTS_APPROVED=1` explícito + tope $2/mes verificado contra MANIFEST.
4. Publicación: `APPROVED=1` explícito + `--upload-drive`.
