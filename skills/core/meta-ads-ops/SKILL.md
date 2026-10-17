---
name: meta-ads-ops
description: >-
  Operaciones de Meta Ads (Facebook e Instagram) vía Composio y Pixel/CAPI. Diagnóstico de cuentas, métricas, geomarketing, creación de campañas y eventos de conversión.
tags: [meta-ads, facebook, instagram, composio, pixel, capi, geomarketing, marketing]
version: 2.0.0
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

Las cuentas publicitarias operan mediante el toolkit `metaads` de **Composio** (managed OAuth, sin necesidad de crear app propia en Meta):

```bash
export PATH="/opt/data/home/.composio:$PATH"
composio whoami
composio connections list | jq '.metaads[]'       # Comprobar status y alias por cliente
composio link metaads --no-browser --no-wait      # Genera redirect_url para autorizar
```

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

## 3. Protocolo de Creación Segura de Campañas

Los anuncios consumen presupuesto real. **Regla de oro: Todo se crea en estado PAUSADO.**

1. `METAADS_CREATE_CAMPAIGN`: Crear la campaña con `status: "PAUSED"`.
2. `METAADS_CREATE_AD_SET`: Vincular la campaña, fijar presupuesto diario y geolocalización.
3. `METAADS_CREATE_AD_CREATIVE`: Inyectar los copys aprobados y creativos de video/imagen.
4. `METAADS_CREATE_AD`: Ensamblar el anuncio (en estado pausado).
5. **Aprobación Humana**: Presentar el paquete completo al usuario (inversión diaria, ciudades y creativos). Solo activar con `UPDATE_CAMPAIGN` tras confirmación explícita.

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
