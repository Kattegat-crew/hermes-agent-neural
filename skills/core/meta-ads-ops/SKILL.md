---
name: meta-ads-ops
description: >-
  Operaciones de Meta Ads (Facebook e Instagram) vía Composio y Pixel/CAPI. Diagnóstico de cuentas, métricas, geomarketing, creación de campañas y eventos de conversión.
tags: [meta-ads, facebook, instagram, composio, pixel, capi, geomarketing, marketing]
version: 2.1.0
author: NeuralCrew / Hermes Fleet
---

# Operaciones de Meta Ads (Composio + Pixel/CAPI)

Habilidad canónica para operar campañas de Meta Ads (Facebook e Instagram), auditar métricas de rendimiento, configurar geomarketing por sede física, y enlazar el embudo de conversión mediante el Pixel de Meta y la Conversions API (CAPI).

---

## Cuándo usar esta Skill (Triggers y Síntomas)

Usa esta skill inmediatamente cuando se presente cualquiera de estas situaciones:
- Peticiones del usuario: *"cómo van los anuncios de Meta"*, *"revisa las métricas de la campaña de Golden"*, *"configura el pixel de Facebook"*, *"crea un adset con radio de 5km"*, o *"por qué Composio no conecta con Meta"*.
- Diagnóstico de caídas en entrega de anuncios, tokens expirados de Meta en Composio o discrepancias de atribución entre el cliente web y el backend de leads.
- Creación y estructuración de campañas y ad sets con segmentación geográfica quirúrgica.

---

## 1. Conexión de Cuentas (Vía Composio)

Las cuentas publicitarias operan mediante el toolkit `metaads` de **Composio** (managed OAuth):

```bash
export PATH="/opt/data/home/.composio:$PATH"
composio whoami
composio connections list | jq '.metaads[]'       # Comprobar status y alias por cliente
composio link metaads --no-browser --no-wait      # Genera redirect_url para autorizar
```

> **Corrección 19-oct-2026 — Composio solo sirve para LEER.** La app de Meta de Composio
> está en modo desarrollo, así que `METAADS_CREATE_AD_CREATIVE` falla con
> `error_subcode 1885183` ("la publicación se creó con una app en modo de desarrollo").
> Toda **escritura** (creativos, ads) va por Graph API directa con token propio de una app
> de la agencia **en vivo**. Modelo: **una app para todos los clientes**, un System User y
> un token por Business Manager. Procedimiento completo, verificación y pitfalls:
> `references/alta-app-y-tokens.md`.

### Gotchas Críticos de Autenticación
* **Expiración de Conexiones**: Si el estado es `EXPIRED`, las herramientas fallarán inmediatamente sin mensaje claro. Re-vincular con `composio link metaads`.
* **Cuentas Activas Verificadas**:
  * **Golden**: `metaads_tactic-vison` (`act_1581421999562187`)
  * **Lucky / Paradise**: `metaads_moly-ponent` (`act_1525564931963110`)

---

## 2. Diagnóstico y Geomarketing Quirúrgico

### Lectura de Métricas
Para obtener métricas de cuenta o campaña:
```bash
# Nota: time_range es obligatorio para rangos personalizados
composio execute METAADS_GET_INSIGHTS -d '{"object_id":"act_1581421999562187","level":"account","time_range":{"since":"2026-09-01","until":"2026-10-15"}}'
```

### Trampa de Geomarketing (Auditoría de Ubicaciones)
`METAADS_READ_ADSETS` **NO** devuelve el campo `targeting` (geo) aunque se pida en `fields` (devuelve `targeting: null`).
Para auditar la geolocalización real de un ad set por sede física:
```bash
composio execute METAADS_GET_OBJECT --account <word_id> -d '{"object_id":"<ID_ADSET>","fields":["name","targeting"]}'
```
* **Estrategia del Equipo**: Campaña general (radio de ~5-8 km alrededor de las sedes) con 30% del presupuesto + Ad sets dedicados por sede (radio de ~5 km) con el 70% del presupuesto restante.

---

## 2b. Reporte Diario a Discord — Rotación Mensual de Campañas

El informe diario de pauta en Discord lo genera un script **zero-LLM** (sin consumo de inferencia): `/opt/hermes-agent/skills/specialists/marketing-ads/meta-ads-discord-reporter/scripts/report.py` en DEV (147.93.3.250). El disparo vive en el **crontab root de DEV** (NO en cron de Hermes): 16:00 (Paradise) y 16:02 (Golden) hora Bogotá, vía webhook Discord "Neural Adds Informes". Log: `/var/log/meta-ads-discord-report.log`.

Cada entrada de cron hardcodea `--campaign-id`, `--account` (slug composio), `--webhook-url` y `--client-name`. **Cuando una campaña pausa (rotación mensual), el reporte sigue saliendo con datos de campaña muerta** → re-apuntar el ID (verificado 20-oct-2026 con la rotación a Halloween):

1. **Diagnose:** listar campañas con el MISMO mecanismo del reporter: `composio proxy "https://graph.facebook.com/v21.0/act_<ID>/campaigns?fields=id,name,status,effective_status,objective&limit=100" --toolkit metaads --account <slug>`. Parsear el JSON entre el primer `{` y el último `}` del stdout (igual que hace report.py). Elegir la campaña con `effective_status: ACTIVE` — hay varias viejas PAUSED (no deleted), filtrar por estado, nunca por "más reciente".
2. **Backup:** `crontab -l > /root/crontab.bak-pre-<tag>-$(date +%Y%m%d-%H%M%S).txt`.
3. **Change:** `crontab -l | sed -e 's|<ID_VIEJO>|<ID_NUEVO>|' | crontab -`. NO tocar webhook, slug ni horario.
4. **Verify:** `crontab -l | grep meta-ads-discord-report` muestra los IDs nuevos + readback en la API del ID nuevo (`?fields=id,name,status` devuelve nombre y ACTIVE). Opcional: correr report.py aislado como prueba de pipeline — ojo, cada corrida envía un embed real al canal.

Pitfall: el ad account de Paradise NO se deduce del slug — consultarlo con `me/adaccounts?fields=id,name,account_status` vía el mismo proxy si falta.

---

## 3. Protocolo de Creación Segura de Campañas

Los anuncios consumen presupuesto real. **Regla de oro: Todo se crea en estado PAUSADO.**

1. `METAADS_CREATE_CAMPAIGN`: Crear la campaña con `status: "PAUSED"`.
2. `METAADS_CREATE_AD_SET`: Vincular la campaña, fijar presupuesto diario y geolocalización.
3. `METAADS_CREATE_AD_CREATIVE`: Inyectar los copys aprobados y creativos de video/imagen.
4. `METAADS_CREATE_AD`: Ensamblar el anuncio (en estado pausado).
5. **Aprobación Humana**: Presentar el paquete completo al usuario (inversión diaria, ciudades y creativos). Solo activar con `UPDATE_CAMPAIGN` tras confirmación explícita.
6. **CBO vs. ABO (decisión con evidencia de cuenta, 19-oct):** NO usar presupuesto compartido de campaña (CBO/Advantage) cuando cada adset es una sede geográfica distinta — Meta concentra el gasto en la sede más barata y sacrifica las pequeñas: en Lucky sept-2026 un CBO de 300.000 COP dejó a La Calera con 752 COP de ~248.000 gastados (0,3%). Para cobertura por sede usar ABO (presupuesto por adset). El tipo de presupuesto se fija al crear la campaña y NO es convertible después: hay que recrearla (a $0 no cuesta nada). Regla de viabilidad: presupuesto/día por adset ≥ ~2,5× `min_daily_budget` (COP: 3184); por debajo del mínimo no se sale de aprendizaje y 400.000 COP no rinden repartidos en >4-5 adsets (agrupar sedes por corredor antes que diluir).

### Bloqueo de Escritura en Dev-Mode (error 1885183) → Graph API Directa
Las operaciones de ESCRITURA (`UPDATE_CAMPAIGN`, PATCH de adsets, crear ads) fallan vía Composio con `(#3) Call was not permitted by the ad account owner: application <id> is in dev mode` (error 1885183), aunque las LECTURAS funcionen. No hay workaround desde Composio; la vía canónica de cierre es **Graph API directa con token de System User**:

* Token: app en **Live**, System User con `ads_management`, `ads_read`, `business_management`, con asignadas las cuentas publicitarias Y páginas del cliente.
* Token materializado en `/opt/data/secrets/meta_ads_system_user.env` (`META_ADS_TOKEN=`), permisos 600. NUNCA pegarlo en chat.
* **Vía rápida con token de usuario vía Graph API Explorer (verificada 19-oct):** la app de desarrollador SÍ es obligatoria (Meta no emite token sin app; se usó "Golden Game Feed" `1349398776805033`, no hace falta código ni servidor). Flujo: developers.facebook.com → Graph API Explorer → seleccionar la app → *Generate Access Token* con `ads_management`, `ads_read`, `pages_show_list`, `business_management`. Dos reglas: (1) poner la app en **Live ANTES** de generar el token — con app en dev-mode las escrituras rebotan igual (error 1885183); (2) el token de usuario caduca a horario fijo diario aunque el Explorer muestre "~2 meses" (el 19-oct caducó a las 19:00 Bogotá en plena operación) — generar el token al final del setup, guardar de inmediato en el `.env` de secretos y planear la operación antes de que venza.
* Script operador canónico: `/opt/data/scripts/ads/finish_halloween_ads.py` — audit read-only (default), `--apply` (corrige presupuestos + crea creativos/ads en PAUSED), `--cleanup` (archiva campañas duplicadas), `--activate` (solo con OK del Admin). Verifica siempre leyendo de vuelta tras cada escritura.
* Para ads de video: `POST /act_X/adcreatives` con `object_story_spec = {page_id, instagram_actor_id, video_data: {video_id, image_hash, message, title, link_description, call_to_action:{type,value:{link}}}}`, luego `POST /act_X/ads` con `creative:{creative_id}` y `status:PAUSED`.

### Calibración de Unidades de Presupuesto (OBLIGATORIA antes de crear/auditar)
Los campos de presupuesto (`lifetime_budget`, `daily_budget`, `min_daily_budget`) se devuelven en unidades del offset de moneda de la cuenta, y un offset asumido equivocado = presupuestos ×100 o ×10.000. **Calibrar SIEMPRE empíricamente antes de confiar en un valor:**
1. Leer `min_daily_budget` de la cuenta (ej. cuentas COP de la flota devuelven `3184` ≈ mínimo real en COP → offset 1, unidades enteras).
2. Contraste: `lifetime_budget` de una campaña vieja vs `spend` de insights en la misma campaña (ej. 300000 vs gasto real 239802 → ambos en unidades mayores).
* **Pitfall verificado (Halloween 2026):** pasar los `amount_minor_centavos` del manifest a `CREATE_AD_SET` dejó adsets con `lifetime_budget` ×10.000 (560.000.000 COP en vez de 56.000). Total: auditar cada adset creado con este método antes de cualquier activación.

---

## 4. Arquitectura de Atribución: Pixel + CAPI Server-Side

Para evitar pérdidas por adblockers o navegación en iOS:

1. **Pixel de Navegador (SPA React/Vite)**:
   * El snippet base `fbq('init', PIXEL_ID)` se carga en el `<head>` del `index.html`.
   * **Gotcha Vite**: La etiqueta `<noscript><img .../></noscript>` NO debe ir en `<head>` (Vite falla el build). Colocarla inmediatamente después de la apertura de `<body>`.
   * Disparar `trackPageView` en el watcher de rutas del frontend y `trackLead` exclusivamente tras confirmación exitosa de envío del formulario.
2. **Conversions API (CAPI) en Backend**:
   * En el servidor de webhooks (`webhook-gateway`), enviar el evento `Lead` directamente al Graph API de Meta tras insertar el registro en Postgres:
   ```http
   POST https://graph.facebook.com/v21.0/{PIXEL_ID}/events
   Authorization: Bearer {META_ACCESS_TOKEN}
   Content-Type: application/json

   {
     "data": [{
       "event_name": "Lead",
       "event_time": 1729152000,
       "action_source": "website",
       "user_data": { "em": ["<hash_sha256_email>"], "ph": ["<hash_sha256_phone>"] }
     }]
   }
   ```
