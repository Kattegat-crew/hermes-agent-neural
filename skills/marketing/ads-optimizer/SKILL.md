---
name: ads-optimizer
description: "Automatización y optimización de campañas Meta Ads (Golden Game y Lucky Brothers / The Grand Paradise Club) desde piezas de Campaign Generator, con atribución de leads calificados y autorización de gasto por chat."
license: Apache-2.0
metadata:
  author: "NeuralCrew Labs"
  version: "1.0.0"
---

# Ads Optimizer — Automatización y Optimización de Meta Ads

Usa esta skill cada vez que el usuario pida armar, validar, montar en `PAUSED`, medir leads calificados u optimizar campañas publicitarias de Meta Ads para **Golden Game** (`golden-game`) o **Lucky Brothers / The Grand Paradise Club** (`lucky-brothers`).

## Ubicación en el repositorio

- **Módulo principal**: `/opt/marketing-campaign-generator/modules/ads_optimizer/`
- **CLI unificado**: `python3 -m modules.ads_optimizer.cli`
- **Documentación y contratos**:
  - `/opt/marketing-campaign-generator/modules/ads_optimizer/README.md`
  - `/opt/marketing-campaign-generator/contracts/ads-*.schema.json`
  - `/opt/marketing-campaign-generator/modules/ads_optimizer/examples/`

---

## Cuentas y Activos Verificados

| Marca | `brand_id` | Ad Account ID | Composio Account | FB Page ID | IG Actor ID |
| --- | --- | --- | --- | --- | --- |
| **Golden Game** | `golden-game` | `act_1581421999562187` | `metaads_tactic-vison` | `820898971112738` | `40006158832316994` |
| **Lucky Brothers / The Grand Paradise Club** | `lucky-brothers` | `act_1525564931963110` | `metaads_moly-ponent` | `765896786617957` | `27571270162548342` |

---

## Estadísticas orgánicas en Business Suite (verificado 3-nov-2026)
- Para stats FB/IG orgánicas de las páginas usar el navegador del perfil (sesión de Plon) en `business.facebook.com/latest/insights/overview?asset_id=<PAGE_ID>&business_id=<BIZ_ID>`.
- **business_id de Paradise (The Grand Paradise Club Casino): `559931120085088`** (page `765896786617957`). Si no se conoce el business_id de una página, descubrirlo en `business.facebook.com/latest/settings/pages?business_id=<biz>` (lista páginas + IDs) o desde los href de `latest/home` (`asset_id=` en los enlaces del sidebar).
- **Pitfall:** el parámetro `&date=YYYY-MM-DD_YYYY-MM-DD` se IGNORA — el rango queda fijo en «últimos 30 días» y hay que cambiarlo desde el date picker de la UI para obtener mes calendario exacto (ej. 1–31 oct).
- Para el selector de entidad, clicar el texto no basta: usar los anchors con `href*="asset_id"` del sidebar y navegar por URL directa.

## Reglas Duras (Invariantes)

1. **Objetivos ODAX obligatorios**: Usar únicamente `OUTCOME_LEADS`, `OUTCOME_TRAFFIC`, `OUTCOME_ENGAGEMENT`, `OUTCOME_SALES` o `OUTCOME_AWARENESS`. Nunca usar objetivos legacy (`LEAD_GENERATION`, `LINK_CLICKS`, `CONVERSIONS`).
2. **Presupuesto en centavos (`COP * 100`)**: En Meta Ads para cuentas en COP, `amount_minor_centavos` debe ser exactamente `amount_major * 100` (ej. `$50.000 COP/día` = `5000000`).
3. **Geolocalización y edad**:
   - `age_min >= 18` obligatorio (+18 Coljuegos). Si `advantage_audience == 0`, `age_max` debe ser `65`.
   - Para ciudades locales, `radius_miles >= 10` (~16 km; Meta rechaza radios menores con subcode `1487110`) y `geo_key` numérico.
   - Sede **Funza** está cerrada y vetada en pauta.
4. **Compliance Casino / Entretenimiento Nocturno**:
   - Prohibido vocabulario de azar/dinero fácil en copy publicitario (`gana`, `juega`, `reclama bono`, `ruleta`, `tragamonedas`, `$50.000`, `$100.000`, `$1.600.000`, `53 balotas`, `boleta física`).
   - Cuando el destino es `WEBSITE`, la URL debe ser una ruta limpia `/eventos/` con `venue_safe_verified: true`.
5. **Creación siempre en `PAUSED`**: Toda creación remota en Meta Ads nace en estado `PAUSED` y se verifica por lectura posterior (`METAADS_GET_OBJECT`).

---

## Flujo Operativo Paso a Paso (Sin que el humano toque la terminal)

### Paso 1: Validar manifiesto y generar variantes + plan Dry-Run (Gratis, 0 mutaciones)

```bash
cd /opt/marketing-campaign-generator
PYTHONPATH=. .venv/bin/python -m modules.ads_optimizer.cli plan \
  --manifest modules/ads_optimizer/examples/golden_halloween_manifest.json \
  --output /tmp/ads_plan.json
```

Presenta al usuario en el chat el resumen del plan:
- Marca, cuenta (`act_...`), objetivo ODAX y presupuesto diario en COP.
- Variantes creativas e hipótesis generadas.
- Pregunta: **«¿Autorizas crear esta estructura en PAUSED en Meta Ads?»**

### Paso 2: Autorización conversacional en chat y creación en `PAUSED`

- **PROHIBIDO** inventar la autorización o usar tu propio nombre (`Ragnar`, `agent`, `bot`) en `--by` o `--approved-by`.
- Cuando el usuario responda explícitamente en el chat (ej. **«Autorizado, procede»** o **«Dale»**), ejecuta directamente con el nombre del humano:

```bash
cd /opt/marketing-campaign-generator
PYTHONPATH=. .venv/bin/python -m modules.ads_optimizer.cli execute-paused \
  --manifest modules/ads_optimizer/examples/golden_halloween_manifest.json \
  --approved-by "Yisus (autorizado en chat)" \
  --purpose "Creacion en PAUSED campana Meta Ads" \
  --hours 2 \
  --output /tmp/ads_exec_result.json
```

*(También puedes abrir el gate por separado con `PYTHONPATH=. .venv/bin/python -m modules.ads_optimizer.cli authorize-gate --by "Yisus (autorizado en chat)" --purpose "..." --providers meta_ads --hours 2`).*

### Paso 3: Medición comercial (CPQL, Oportunidades, CAC, ROAS) y Recomendaciones

Para cruzar métricas de Meta Insights con eventos de leads/CRM y obtener recomendaciones diagnósticas (entrega, medición, costo, fatiga creativa, calidad comercial) respetando ventanas mínimas de muestra (`>= 72h`, `>= 1000` impresiones, `>= 30` clics):

```bash
cd /opt/marketing-campaign-generator
PYTHONPATH=. .venv/bin/python -m modules.ads_optimizer.cli recommend \
  --manifest modules/ads_optimizer/examples/golden_halloween_manifest.json \
  --insights modules/ads_optimizer/examples/synthetic_insights.json \
  --crm-events modules/ads_optimizer/examples/synthetic_crm_events.json \
  --output /tmp/ads_recommendations.json
```

### Paso 4: Freno de emergencia (Kill Switch)

Si se detecta anomalía de gasto, error de credenciales o solicitud del usuario de detener automatización:

```bash
cd /opt/marketing-campaign-generator
PYTHONPATH=. .venv/bin/python -m modules.ads_optimizer.cli kill-switch \
  --reason "Detencion solicitada por el operador"
```

---

## Parámetros de URL (UTM) y contrato de atribución (verificado en código 19-oct-2026)

El bloque `utms` del manifiesto es la ÚNICA fuente de verdad para los URL parameters del anuncio. NO inventar valores ni copiarlos de campañas viejas.

- `utm_source` va EXACTAMENTE `fb` (o `ig`): `content-intel/leads_report.py` clasifica un lead como **Anuncio** solo si `utm_source IN (fb, ig) AND utm_campaign IS NOT NULL`; cualquier otro valor (p. ej. `facebook`, `meta`) lo degrada a **Probable** (si hay `fbc`) u **Organico**.
- `utm_content` DEBE seguir la plantilla del manifiesto `{experiment_id}_{variant_id}_{piece_id}` (ej. `exp_gg_halloween_hook_01_var_gg_hook_control_GG-REEL-TERROR-01-V05`): `modules/ads_optimizer/crm_attribution.py` resuelve `campaign_id`/`adset_id`/`ad_id`/`creative_id`/`experiment_id` buscando primero por `utm_content` y luego por `utm_campaign` en el `campaign_lookup`. Un `utm_content` libre (p. ej. `{{ad.name}}`) rompe la atribución de variante/pieza.
- Pegar la cadena completa en el campo «Parámetros de URL» del anuncio en Ads Manager: `utm_source=fb&utm_medium=paid_social&utm_campaign=<slug>&utm_term=<segmento>&utm_content=<experiment_id>_<variant_id>_<piece_id>`.
- Todo en minúsculas, sin tildes ni espacios. Meta añade `fbclid` solo; NO agregar `utm_id` ni duplicar parámetros.
- Nivel de pegado: si todos los adsets comparten destino, pegar la cadena a nivel de CAMPAÑA (Meta concatena campaña+adset+anuncio; un solo nivel evita duplicados). Distinción por sede = nombre del adset + reporte nativo + `fbclid`, no la URL.

## Kit de marca «Imagen de marca» (modal de Ads Manager)

Para llenar logo/fuente/colores/tono/estilo/palabras restringidas NO improvisar: seguir la receta de `references/brand-kit.md` (fuentes canónicas por campo, paleta real extraída del CSS de producción, lista de palabras restringidas del kit más amplia que la de copy, y el pitfall del sitio Golden: `?sede=` solo personaliza home y `/bono`, `/eventos` lo ignora). Verificar también qué logo está cargado en el modal antes de dar OK y en qué plataforma es el modal (Google Ads exige certificación de gambling).

## Ejecución real vía Composio (verificado en producción 16-oct-2026)

**El CLI `execute-paused` NO crea objetos en Meta** — termina en bloqueo deliberado (`live_transport_requires_explicit_network_opt_in`). La creación real se hace con el executor JSON-RPC `scripts/ads_execute_composio.py` de esta skill (dryrun.json del plan + nombre de cuenta Composio; exportar `COMPOSIO_MCP_KEY` antes de invocarlo).

Patrones verificados:

- Las tools de acción `METAADS_*` NO se pueden llamar directo por JSON-RPC `tools/call` al MCP (`Tool not found`): solo vía `COMPOSIO_MULTI_EXECUTE_TOOL` con `{tools:[{tool_slug, arguments}]}`. Header obligatorio `Accept: application/json, text/event-stream` (respuesta SSE; parsear las líneas `data: `).
- **Enrutamiento multi-cuenta (BLOQUEO ABIERTO, ticket 1560875784246399059 a Chucho):** con 2 conexiones metaads activas toda llamada devuelve `Multiple metaads accounts connected. Specify which to use via the 'account' field` y ese campo NO se acepta ni dentro de `arguments` de cada tool entry ni como top-level del MULTI_EXECUTE (los schemas de las tools no declaran ningún campo `account`). NO reintentar esas shapes — verificar en la cuenta antes de reintentar CREATE.
- `COMPOSIO_MANAGE_CONNECTIONS` con `action='list'` + `toolkits` NO lista: **inicia una conexión nueva pendiente** y devuelve `redirect_url`. No usar para listar; descartar cualquier link pendiente (`lk_hHiSBBSHQLG1` quedó huérfano, no completarlo).
- **Anti-duplicado:** el executor interpreta errores en-banda del MULTI_EXECUTE como `id` nulo. Antes de reintentar CREATE con id nulo, LEER el estado real de la cuenta — un reintento ciego duplica (en 16-oct la primera pasada nunca llegó a Meta y no hubo duplicados, pero el patrón de riesgo es real).
- **Pixel IDs reales:** grepear `fbq('init')` en el HTML servido de la landing destino, no confiar en IDs de documentos externos. Golden `989823497477559`, Lucky `797435129291027` (16-oct).
- **Presupuesto lifetime:** NO mandar `daily_budget` en los adsets cuando el período es con fecha de fin; el lifetime por adset = suma exacta y el período lo definen `start_time`/`end_time` del schedule. Un campo extra tipo `period_days` viola el schema (`additionalProperties: false`).
- **Gap de diseño:** creativos VIDEO (reels 9:16) sin vía de subida — el toolkit no tiene UPLOAD_AD_VIDEO y el plan arma creativos con `image_hash: None`. Los ads por API requieren resolver esto (la UI de Ads Manager sí admite el MP4 → vía manual mientras).
- **Convención de nombres con tag de idempotencia (comiteada en `main`, `composio_adapter.py:87`):** toda entidad creada por el adapter se nombra `<base>-<sha256({ref, payload, op})>` y un guard lo hace obligatorio (`ExecutionBlocked: Idempotency tag is missing from entity name`, línea 268). NO renombrar ads/adsets quitando el sufijo ni crear entidades con nombres sin tag: el tag es el anti-duplicado en reintentos. El script operador `/opt/data/scripts/ads/finish_halloween_ads.py` replica la misma convención vía `tagged_name()` con placeholders (`${creative:...}`) en el payload, para que el nombre sea determinista entre corridas.
