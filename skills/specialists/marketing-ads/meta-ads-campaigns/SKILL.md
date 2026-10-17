---
name: meta-ads-campaigns
description: "Use when running Meta Ads campaigns, adsets or pixel."
tags: [meta, ads, campanas, composio, pixel, capi, facebook, instagram]
version: 1.0.0
---

# Operación de Meta Ads para clientes (via Composio / Marketing API)

Operar cuentas publicitarias de Meta (Facebook/Instagram Ads) para los clientes de NeuralCrew: leer campañas, crear anuncios, medir con el pixel y armar el funnel (ads → web → eventos). Cumple la regla de oro: **nunca activar anuncios en producción sin aprobación humana del cliente (gate de Review)**.

## Acceso: toolkit `metaads` en Composio

El conector se cablea via Composio (interfaz CLI). Ver `composio-integrations` (setup/execute general) para la base; aquí va el dominio de ads.

### Conectar (managed auth, sin crear app)
```bash
composio link metaads --no-browser --no-wait
# → redirect_url de connect.composio.dev — el usuario abre, inicia sesión con la cuenta dueña del Business/Ad Account y acepta TODO el consentimiento.
composio connections list   # status: ACTIVE / EXPIRED / INITIATED
```
- Una conexión queda **ACTIVE solo si el usuario completa todo el flujo**; un `INITIATED` que no se terminó vuelve EXPIRED.
- **EXPIRED = OAuth vencido**: re-vincular con `composio link metaads` (crea `word_id` nuevo). Las expired no se borran solas — identificar la ACTIVE por status.
- Cada conexión Composio puede mapear a un Ad Account distinto (ej. nuestro Golden y Paradise son 2 conexiones, una por cliente).

### Cuentas ADS
```bash
composio execute METAADS_GET_AD_ACCOUNTS --account <word_id> -d '{}'
# → [{id: act_..., name: "Golden Game"}]  — el act_... es el object_id raíz de todo
```
SIEMPRE pasar `--account <word_id>` (obligatorio si hay varias conexiones del mismo toolkit).

## Tools disponibles (verificadas en vivo)

**Lectura:**
- `METAADS_GET_AD_ACCOUNTS` — listar Ad Accounts.
- `METAADS_GET_INSIGHTS` — métricas por `level` = account/campaign/adset/ad (debe casar con el `object_id`).
- `METAADS_READ_ADSETS` — **requiere `ad_account_id`**.
- `METAADS_GET_OBJECT`, `METAADS_LIST_TARGETING_SEARCH`.

**Creación (existen on-demand — la carpeta tool_definitions NO las lista a primera vista, pero `--get-schema` sí las resuelve):**
- `METAADS_CREATE_CAMPAIGN`, `METAADS_CREATE_AD_SET`, `METAADS_CREATE_AD`, `METAADS_CREATE_AD_CREATIVE`, `METAADS_UPDATE_CAMPAIGN`, `METAADS_GET_PAGE_ACCOUNTS`.

## Quirks de schema (verificados en vivo 07/09/26)
- `GET_INSIGHTS.date_preset` SOLO enum: `today/yesterday/last_7d/last_30d/this_month/last_month/this_quarter`. **NO soporta `last_90d`** → usar `time_range {since,until}` (YYYY-MM-DD) para rangos mayores.
- Sin `date_preset` ni `time_range`, default = `last_30d`.
- `READ_ADSETS` sin `ad_account_id` → 'required property' (código de validación).
- `GET_OBJECT`: `fields` como **array** (nunca string comma-separado) y `object_id` en limpio (sin path/sufijo).
- `-d '{}'` siempre obligatorio.

## Pitfalls de creación (documentados por composio)
- `CREATE_AD_SET` rechaza edades automáticas → 1870189 / 100@2490487; simplificar targeting o quitar expansión.
- `100@1815857` — puede ser el budget/bid a nivel campaña (ajustar via UPDATE_CAMPAIGN).
- Conversion setups → `100@1815430` — simplificar y reducir campos.
- `100@2490487` 'Invalid parameter' — quitar campos de expansión/extra.
- **Flujo SEGURO**: campaña → ad set → ad, todos en **pausado**; activar con `METAADS_UPDATE_CAMPAIGN` SOLO tras gate de aprobación del cliente.

## RECETA QUE FUNCIONA — crear campaña + ad sets con geo (verificada 07/09/26, Golden)

Esta es la receta probada end-to-end que evita los 3 errores que bloquean la creación vía Composio. NO hay tool de `UPDATE_AD_SET` ni de borrar ad set por API — **créalos correctos a la primera** (solo existe `METAADS_UPDATE_CAMPAIGN`, que toca la campaña, no los ad sets).

### 1. Obtener el geo key (id numérico) de cada ciudad
Meta NO acepta nombres de ciudad para targeting por API — usa ID numérico. Extraer con `METAADS_LIST_TARGETING_SEARCH`:
```bash
composio execute METAADS_LIST_TARGETING_SEARCH --account <word_id> -d '{"type":"adgeolocation","q":"Tunja"}'
# → [{name: Tunja, type: city, key: 480932, ...}]  usar el tipo=city, el key es el id
```
Los keys de las sedes Golden (07/09/26): Tunja 480932 · Pacho 475293 · Cachipay 2712446 · Anolaima 457023 · Carmen de Apicalá 459356 · San Francisco de Sales 478567. "El Carmen" suelto devuelve cities ambiguas → buscar por "Apicala".

### 2. Crear campaña (PAUSED)
`objective` en este schema NO tiene `OUTCOME_LINK_CLICKS` — el correcto para tráfico es **`OUTCOME_TRAFFIC`**. Campos mínimos: `account_id`, `name`, `objective`, `status: PAUSED`, `bid_strategy: LOWEST_COST_WITHOUT_CAP`, `special_ad_categories: []`.

### 3. Crear ad set (PAUSED) — los 3 errores a evitar
El `targeting` object requiere estos campos o falla:
```json
{
  "name": "Golden Tunja Septiembre",
  "status": "PAUSED",
  "optimization_goal": "LINK_CLICKS",
  "billing_event": "IMPRESSIONS",   // NO usar LINK_CLICKS aquí → 'billing option not available' (100)
  "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
  "daily_budget": 155500,             // EN CENTAVOS: $1.555 COP/día = 155500
  "targeting": {
    "age_min": 18, "age_max": 65,
    "location_type": "cities",
    "location_radius": 10,            // MÍNIMO: 10 millas (≈16km). Menos → 1487110
    "locations": ["480932"],          // geo keys (ids numéricos)
    "targeting_automation": {"advantage_audience": 0}  // OBLIGATORIO con budget alto, si no exige Advantage+
  }
}
```
**Errores reales encontrados (códigos y su causa):**
- `location_radius` < 10 → **subcode 1487110** "El radio geográfico no se encuentra dentro de los límites". Meta NO permite radio menor a ~10 millas (16km) por API para ciudades. Si el cliente pide 5-8km, advertir que el mínimo es 16km (o hacerlo manual en la UI).
- `billing_event: LINK_CLICKS` → "Opción de facturación no disponible" aunque `optimization_goal` sea LINK_CLICKS. Usar **`billing_event: IMPRESSIONS`** + `optimization_goal: LINK_CLICKS`.
- budget/daily_budget alto sin Advantage → "Se requiere la marca de público Advantage". Fijar **`targeting_automation: {advantage_audience: 0}`** y `age_max: 65` (requisito cuando se desactiva la expansión). Con daily_budget pequeño (~500) no pide Advantage, pero con budget real sí.

### 4. `daily_budget` va EN CENTAVOS (bug crítico)
`daily_budget` se interpreta en la **unidad menor de la moneda** (como centavos) — enviar 4000 muestra 400000 (= $4.000 COP). Si quieres $X COP/día, envía **X * 100**. Error cometido: poner sedes a 4665 → quedaron en $4.665/día cuando debían ser ~$1.555. Como estaban PAUSED no gastó, pero al activar habría gastado 3x. Siempre recalcular: 400K/mes → 30% general = $4.000/día (400000), 70% repartido en 6 sedes = ~$1.555/día c/u (155500).

### 5. Verificar geo real tras crear (nunca creer el nombre)
Tras crear, confirmar con `METAADS_GET_OBJECT` que el `targeting.geo_locations.cities[].name` trae la ciudad correcta. Un ad set recién creado puede aceptarse pero con targeting mal aplicado — verificar siempre. Y confirmar que status=PAUSED (nada activo) antes de reportar éxito.

### 6. Sin tool de borrado/aditamento de ad set
NO hay `METAADS_UPDATE_AD_SET` (404) ni delete de ad set vía Composio. Un ad set con budget errado o test queda creado — o se deja pausado (no gasta) y se corrige a mano en la UI al activar, o solo `METAADS_UPDATE_CAMPAIGN` (campaña). Planificar bien antes de crear; los test fallidos del flujo anterior quedan como ad sets PAUSED huérfanos (limpiar marcando que son test).

## Diagnóstico de campañas (plantilla)
1. `GET_AD_ACCOUNTS` → `act_...` por cliente.
2. `GET_INSIGHTS` level=campaign + `time_range` → inversión/clicks/impresiones/alcance por campaña (patrón: campañas mensuales 'Mundial', LINK_CLICKS; ad sets por sede).
3. `READ_ADSETS` → ad sets, status (PAUSED/ACTIVE), sedes.
4. Resumir en tabla de inversión por campaña para presentar diagnóstico al cliente.

## Pixel / funnel — el punto crítico
El pixel registra eventos post-click. Sin él Meta solo mide clicks, NO el funnel real. Verificar SIEMPRE si la web destino lo tiene:
```bash
curl -sL <web> | grep -cE "fbq\("        # base
curl -sL <web> | grep -cE "fbevents"      # script connect.facebook.net/en_US/fbevents
curl -sL <web> | grep -iE "fbq|pixel|fbevents"
```
- 0 en ambos = **el funnel NO existe** (hoy solo miden clicks). Este es el hallazgo número 1 de un diagnóstico.
- **SPAs Vite/React** (`#root`, module JS): el ruteo cliente-side hace que rutas tipo `/bingo` sirvan la home. NO asumir que `/bingo` es una landing real → confirmar con `curl -IL` (redirects) y grep del contenido (ej. 'bingo millonario', premio, CTA).
- Instalación: `fbevents.js` en `<head>` + `fbq('init', PIXEL_ID)`; para SPAs usar `fbq('track', ...)` disparado en las acciones clave (ViewContent, Lead, Contact) — 1 pixel por cliente. Verificar con Meta Events Manager → Test Events.

### Pitfall: noscript en `<head>` rompe Vite (parse5)
**NUNCA** poner `<noscript>` dentro de `<head>` en un proyecto Vite — el parser HTML (parse5) rechaza `disallowed-content-in-noscript-in-head` y `npm run build` falla con exit code 1. Solución: el `<script>` del pixel va en `<head>` (OK), pero el `<noscript>` con el `<img>` fallback va **justo después de `<body>`**:
```html
<head>
  <!-- script del pixel OK aquí -->
  <script>fbq('init', '...'); fbq('track', 'PageView');</script>
</head>
<body>
  <noscript><img height="1" width="1" style="display:none"
  src="https://www.facebook.com/tr?id=...&ev=PageView&noscript=1"/></noscript>
  <div id="root"></div>
</body>
```

### Pitfall: nginx CSP bloquea el pixel de Meta
Si la web tiene `Content-Security-Policy` en nginx, el pixel NO cargará a menos que se whiteliste `connect.facebook.net`. Agregar:
- `script-src 'self' 'unsafe-inline' https://connect.facebook.net` (carga el JS)
- `connect-src 'self' https://connect.facebook.net https://graph.facebook.com` (CAPI + tracking)

Ejemplo de CSP completo que funciona con Meta Pixel:
```
script-src 'self' 'unsafe-inline' https://connect.facebook.net; connect-src 'self' https://api.nan.builders https://connect.facebook.net https://graph.facebook.com;
```
Verificar con `curl -sI https://tudominio.com/ | grep content-security` después del deploy.

## Flujo completo de campaña (faseado)
1. Diagnóstico (pantalla de campañas + estado del pixel).
2. Pixel: crear por cliente → integrar en el build (SPA) → verificar Test Events.
3. Campaña: CREAR en pausado, presupuesto/día, geo de sedes, destino = web con pixel.
4. Gate humano (Jonathan/cliente aprueba copys y creativos) — regla de oro.
5. Activar (UPDATE_CAMPAIGN) → monitorear insights diario.
6. Optimizar: matar ad sets sin rendimiento, subir presupuesto a ganadores, A/B creativos.

## Presupuestos (convención NeuralCrew)
Sept 2026 Bingo Millonario: **$400K COP/mes por empresa** (Golden + Paradise), ≈$13.300/día. Confirmar siempre el monto con el Admin antes de activar.

### `daily_budget` va en CENTAVOS
El campo `daily_budget` del ad set/campaña se interpreta en la **unidad mínima de la moneda** (centavos). `daily_budget: 4000` = $4.000 COP/día. Un error común: poner `4665` pensando en $4.665 → Meta lo lee como **$466.500/día** (3x). Verificar siempre con `READ_ADSETS` el `daily_budget` devuelto (si aparece multiplicado por 100, fue centavos).

## Creación de campaña + ad sets (receta verificada 07/09/26)

### Campaña
```
METAADS_CREATE_CAMPAIGN \
  -d '{"account_id":"act_...","name":"Campaña X","objective":"OUTCOME_TRAFFIC","status":"PAUSED","bid_strategy":"LOWEST_COST_WITHOUT_CAP","special_ad_categories":[]}'
```
- **`objective` NO acepta OUTCOME_LINK_CLICKS** en el schema — usar **OUTCOME_TRAFFIC** (equivalente moderno a link-clicks).
- Returna `{id: "120251536257860347"}`.

### Ad set (el paso que más falla)
```
METAADS_CREATE_AD_SET \
  -d '{"account_id":"act_...","campaign_id":"<campaña>","name":"X","status":"PAUSED","optimization_goal":"LINK_CLICKS","billing_event":"IMPRESSIONS","bid_strategy":"LOWEST_COST_WITHOUT_CAP","daily_budget":4000,"targeting":{"age_min":18,"age_max":65,"location_type":"cities","location_radius":10,"locations":["<geo_key>"],"targeting_automation":{"advantage_audience":0}}}'
```
**Receta que funciona (validada en vivo):**
- `billing_event: IMPRESSIONS` (NO LINK_CLICKS — daba error "Opción de facturación no disponible" en budget bajo).
- `targeting_automation: {advantage_audience: 0}` — desactiva Advantage+ (sin esto, con budget bajo pedía "marca de público Advantage").
- `advance_audience: 0` exige `age_max: 65` (requisito de la API).
- `location_type: cities` + `location_radius` (obligatorio) + `locations: [geo_keys]`.

### ⚠️ RADIO MÍNIMO = 10 millas (~16km) por API
Meta **NO permite radio menor a 10 millas** para targeting por ciudad vía API. Cualquier `location_radius < 10` falla con `code:100 subcode:1487110` ("radio geográfico no se encuentra dentro de los límites"). Validado: 1/3/5/8/10 km → todos rechazados; 10 mi OK. Consecuencia: **los planes de radio fino (5-8km) no son posibles por API** — el mínimo es ~16km. Para radios menores, editar manualmente en la UI de Meta.

### GEO KEYS (identificadores numéricos de ciudades — obtenidos con LIST_TARGETING_SEARCH type=adgeolocation)
Para construir el `targeting.locations`, se requieren los **geo keys** (IDs numéricos), NO los nombres. Obtenerlos con:
```
composio execute METAADS_LIST_TARGETING_SEARCH --account <wd> -d '{"type":"adgeolocation","q":"<ciudad>"}'
```
Verificados para Golden:
| Ciudad | geo key |
|---|---|
| Tunja | 480932 |
| Pacho | 475293 |
| Cachipay | 2712446 |
| Anolaima | 457023 |
| Carmen de Apicalá | 459356 |
| San Francisco de Sales (Cund.) | 478567 |

## Verificar geo REAL después de crear (obligatorio)
`READ_ADSETS` NO expone targeting. Para confirmar que el ad set quedó con la geo correcta:
```
composio execute METAADS_GET_OBJECT --account <wd> -d '{"object_id":"<adset_id>","fields":["name","targeting"]}'
```
Chequear `targeting.geo_locations.cities[].name` — debe listar los municipios esperados. SOLO así se confirma la geo (el nombre del ad set miente).

### Sin tool de UPDATE/DELETE ad set
El conector NATURAL no tiene `METAADS_UPDATE_AD_SET` ni `METAADS_DELETE_AD_SET` (solo UPDATE_CAMPAIGN). Correcciones de budget/targeting de un ad set se hacen: (1) recreando el ad set, o (2) manual en la UI de Meta. Los ad sets PAUSED no gastan → se pueden corregir sin riesgo antes de activar.

## Verificación de geo real de ad sets (CRÍTICO)

Los nombres de ad sets NO garantizan la geo — un ad set "Anolaima" puede segmentar solo por interés, sin ciudad. `READ_ADSETS` NO expone targeting. **Siempre verificar con:**
```bash
composio execute METAADS_GET_OBJECT --account <word_id> -d '{"object_id":"<adset_id>","fields":["name","targeting"]}'
```
El campo `targeting.geo_locations.cities[].name` confirma la geo real. Cities vacío = sin geo = segmenta por todo el país. Este patrón es OBLIGATORIO antes de proponer campañas "por sede" — es fácil que haya ad sets que dicen "por sede" pero no tienen geo.

## Conversions API (CAPI) — implementación server-side

El **pixel browser** (fbevents.js) y la **Conversions API** (POST al Graph API desde el servidor) son complementarios. Meta recomienda ambos juntos:
- **Browser pixel**: `PageView`, `ViewContent` (lo que la gente ve). Necesario para que Meta optimice el funnel alto.
- **CAPI (server)**: `Lead`, `Purchase` (lo que la gente hace). Confirmado desde el servidor, no depende de adblock. Es la fuente de verdad para conversiones.
- **Deduplicación**: usar el mismo `event_id` en browser y server para que Meta no cuente el mismo evento dos veces.

### Implementación CAPI en webhook server (Node.js/Express)

1. **Crear pixel** en Events Manager → copiar **Pixel ID** (16 dígitos).
2. **Generar Access Token** en Events Manager → Settings → Conversions API → Generate Access Token.
3. **Vars de entorno**: `META_PIXEL_ID` y `META_CAPI_ACCESS_TOKEN` (en el .env del contenedor).
4. **Función `sendCapiEvent()`** que hace POST a `https://graph.facebook.com/v21.0/{PIXEL_ID}/events` con:
   - `event_name`, `event_time` (unix), `event_id` (UUID para dedup), `action_source: 'website'`
   - `user_data`: SHA-256 hasheados de `em` (email), `ph` (phone sin espacios/guiones), `fn` (first name)
   - `custom_data`: `content_name`, `value`, `currency`
5. **Fire-and-forget** después del INSERT en el handler del formulario (no bloquear la respuesta al usuario).
6. **Verificar** con `test_event_code` de Events Manager (método oficial, no contamina métricas reales).

### Región del servidor (Meta Events Manager)
La "ubicación del servidor" en Events Manager es la región **física** del server que envía los eventos CAPI (NO la ubicación de la web). Verificar con `ssh <server> curl -s ipinfo.io`. Ejemplo: Contabo → ipinfo.io puede mostrar Francia (Grand Est) → seleccionar "Europe". Una vez seleccionada, NO se puede cambiar.

### Token scope (pitfall)
Un token de CAPI puede retornar `(#100) Missing Permission` en `GET /{pixel_id}` pero funcionar correctamente para `POST /{pixel_id}/events`. El error de GET no indica token inválido — es solo scope de lectura no incluido. Para confirmar que el token sirve, hacer un POST de test.

### Docker Compose env_file (pitfall de deploy)
`docker restart` NO re-read `env_file:` del compose. Las vars de entorno se inyectan al CREAR el contenedor, no al reiniciar. Para aplicar cambios en .env: `docker compose up -d --no-deps <service>` (fuerza recrear). Verificar con `docker exec <name> env | grep META_`.

### Verificación end-to-end (MUY recomendada antes de dar por hecho)

Después de desplegar el CAPI, NO basta el `events_received:1` de una llamada directa. Probar el flujo REAL (el que ejecutará un usuario):
1. Hacer `POST` a `http://localhost:{port}/webhook/golden-vip-signup` con datos de test claramente marcados (ej. `email: test-capi@...`, cédula `9999...`).
2. Verificar en los logs del server: `[BONO] Lead inserted: id=NN` **Y** `[CAPI] Lead enviado. events_received=1`.
3. Esto confirma: formulario → Postgres INSERT → CAPI a Meta. Es la prueba de punta a punta.

### Expectativa: dashboard "0 eventos / 28 días" (NO es error)
Después de instalar el pixel, el dashboard de Events Manager muestra "0 eventos / 28 días" y "No hay integraciones". **Es normal** y NO indica falla. Razones:
- El pixel se instaló recién → no ha habido **tráfico real** aún. Los eventos de reporting cuentan usuarios reales, no llamadas de test.
- "No hay integraciones" se refiere al gateway/CAPI (opción de pago, Stape) que NO usamos — nuestro CAPI va directo por API, por eso no aparece como "integración".
- Los `events_received:1` de mis pruebas de API son eventos de validación, NO datos de reporting.
Cuando la campaña mande tráfico real, los eventos se llenan y Meta los cuenta para optimizar.

### Deploy manual del frontend (Coolify / Docker file)
Si el sitio se despliega vía Coolify desde un repo, el contenedor usa una imagen Nginx pre-builtda (mounts None). Para cambios sin push git:
1. Localizar source buildable: `find / -maxdepth 4 -name Dockerfile` o el dir con `package.json` + `src/` + `nginx.conf`.
2. Sincronizar archivos editados al server → `docker build -t <name>:latest .` en el dir del source.
3. `docker stop <old> && docker rm <old> && docker run -d --name <name> -p 9001:80 --restart unless-stopped <name>:latest`.
4. Verificar con `curl -sL http://localhost:9001/ | grep fbq` y `curl -sI https://dominio | grep content-security`.
5. Si el repo es el fuente de verdad (GitHub), además hacer push al repo para que Coolify rebuilde en el futuro.

### Selección del mejor tramo de un video largo (técnica verificada 07/09/26)
Los clips de evento vienen de 50 a 260s (y a veces 368x496 de resolución). Para cortar a 15-20s sin adivinar:
1. `ffprobe` → width/height/duration.
2. **Contact sheet** por tramos, ajustando `fps` al largo (video 260s → `fps=1/15`; 60s → `fps=1/4`; 96s → `fps=1/6`):
   `ffmpeg -y -i IN -vf "fps=1/5,scale=220:-1,tile=4x4" -frames:v 1 /tmp/contact.png`
3. `vision_analyze` la contact sheet y pedir el **rango recomendado de 15-20s** (clímax = ganador con cartón/billetes, grito de bingo, entrega de premio, gente levantada — suele estar al 65-90% del video).
4. Cortar: `ffmpeg -ss <start> -t <dur> -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1" -c:v libx264 -preset medium -crf 24 -pix_fmt yuv420p -c:a aac -b:a 128k OUT.mp4`.
5. Verificar el **frame al 1s** del corte con vision_analyze — suele capturar el ganador con cartón + billetes. El frame del medio (50%) a veces es máquinas/vacío; no te fíes de él, revisa inicio y fin.
6. Subir a `/opt/reels/assets/` y publicar. El upscale de low-res tarda → dar a ffmpeg timeout 200-400s.

## ads_optimizer (repo m-c-g) — vía canónica de ejecución (16-oct)
El módulo `modules/ads_optimizer` del repo m-c-g implementa el loop de 9 etapas (brief → hipótesis → manifiesto → variantes → validación → ejecución → resultados → calidad de leads → siguiente experimento) con gobernanza: `dry_run` por defecto, creación solo en PAUSED, spend gate sellado por autorización de chat, outbox idempotente. Los manifests de ejemplo (examples/{golden,lucky}_halloween_manifest.json) traen datos reales: cuentas act_1581421999562187 (Golden) / act_1525564931963110 (Lucky), composio metaads_tactic-vison / metaads_moly-ponent, 7 sedes Golden con geo keys y veto Funza.

### Destinos de conversión verificados (NO asumir dominios)
- **Golden:** `https://goldengame.com.co/eventos` (HTTP 200; la ruta /eventos/halloween-2026 NO existe como canónica — el Admin definió /eventos).
- **Lucky:** `https://paradiseclubcasinos.com.co/eventos` — **`luckybrothers.com.co` NO RESUELVE (NXDOMAIN)**; aunque aparezca en docs/manifests, nunca usar ese dominio. La página /eventos de Paradise es venue-safe verificada (solo Halloween/sorteo/eventos; el contenido de tragamonedas/efectivo vive en el home, que NO debe ser destino del ad).
- **Pitfall:** los `pixel_id` de los manifests de ejemplo son placeholders (114422334455667 / 225533445566778) — conseguir los Pixel IDs reales de cada cuenta antes de ejecutar.
- Verificar SIEMPRE el destino del ad en vivo (`curl` + grep de términos de juego online) antes de validar el manifest: el bloqueo Meta es el DESTINO, no el copy.

## Referencias
- `references/metaads-2026-09-07.md` — word_ids/conexiones, Ad Accounts Golden/Paradise, insights por campaña, hallazgo de pixel (0 en todas las webs), plan Bingo Millonario.
- `references/capi-golden-deployment-2026-09-07.md` — detalles del despliegue CAPI + pixel Golden, pruebas end-to-end, Stape por qué NO usarlo.
- `references/capi-implementation-golden-2026-09-07.md` — implementación CAPI en webhook-server.js de Golden (código).
- `references/golden-septiembre-2026-09-07.md` — campaña Golden Septiembre creada (ad set ids, geo keys, presupuestos, parámetros confirmados por Jonathan, pendientes conocidos).
- `references/event-stories-publishing-2026-09-07.md` — publicar stories de evento del cliente (footage raw → 9:16, seleccionar mejor tramo 15-20s, flujo IG 2 pasos, limitación FB stories solo crossposting).
- `references/historias-golden-lucky-eventos-2026-09-07.md` — media IDs de las historias de evento publicadas (8 Golden + 6 Lucky), cortes verificados, regla del Admin (ambas cuentas, tal cual, 15-20s), flujo IG Stories 2 pasos.
