---
name: amazon-ads-au-ops
description: Use when managing Amazon Ads AU campaigns, bids or orders.
---

# Amazon Ads AU — Operación de campañas (Digital Expressions)

## When to Use
- Leer/diagnosticar campañas de Amazon Ads AU (métricas, bids, presupuesto) desde la consola.
- Crear o modificar campañas, keywords, negatives o cupones en Seller/Ads AU.
- Consultar estado de créditos NSI, facturación o incentivos de nuevo vendedor AU.
- Consultar inventario/listings/órdenes vía SP-API (creds en /opt/data/.env).

## Contexto de la cuenta
- Seller ID `A2VHNMV7YZM9CX` · Marketplace AU `A39IBJ37TRP1C6` · entityId Ads AU `ENTITY24CTELJR8JE53` (US vieja: `ENTITY3VJ12SLGNX8P6`)
- 3 ASINs snuffle mats: B0HFVZCNPQ (PS-3052, A$39.99) · B0HFW1Q1GW (PS-3058, A$44.99) · B0HFW54MNC (PS-3095, A$36.99)
- Repo del proyecto: `/opt/digital-expresions-amazon` (finance/ tiene cliente SP-API y Google; docs/estado-y-pendientes.md)
- SP-API creds: `AMAZON_SPAPI_*` en `/opt/data/.env`. La Ads API NO comparte credenciales: exige app LWA nueva con redirect URI (la actual es self-auth) — pendiente.
- Acceso consola: navegador LOCAL del usuario (sesión passkey de Ads viva; Seller Central NO tiene sesión). Login Ads con password cuando passkey falle ("Sign in with your password").

## Quirks de la consola Ads (leídos a la mala)
- Los widgets de métricas NO aparecen en `innerText` ni en network entries visibles: **usar `capture_screenshot()` + `vision_analyze`** para leer KPIs (Clicks, Purchases, CPC, Total cost) y tablas. Límite duro: UN solo intento de innerText — si los widgets no están, screenshot inmediato (esta sesión quemó ~10 turnos iterando goto_url antes de probar screenshot).
- El SPA carga con `new_tab(url)`; `goto_url` al mismo dominio lo deja en "Loading widget" eterno. Si colapsa: pestaña nueva.
- Links con el entityId equivocado cargan nav pero sin datos — sacar el link real desde la tabla all-campaigns.
- Inputs React (nombres, budget, textarea de keywords): `document.execCommand('insertText')` tras focus/select; el setter nativo de `value` NO dispara los handlers.
- El bid del "keyword group" (fila 'Keywords related to your product category') es un input aparte que abre con click físico (`click_at_xy`), id `kwp:kwp-bid-input-field`; es el DEFAULT BID del ad group, no un bid por keyword.
- Al pegar keywords por Enter list: match types Broad/Phrase/Exact = 3 filas por keyword. Las sin suggested bid abren modal con alternate bid — rechazar con "Don't add keywords" (regex con apóstrofe tipográfico `’`, no ASCII).
- Forecast exige budget ≥ A$20 para mostrar.
- Billing → Promotions = estado de créditos/promos. Créditos se aplican solos y se consumen antes de cobrar la tarjeta.

## Estado campañas (07-nov-2026)
1. **"Snuffle mats"** ID `A0204318BAI5NYXBS63L`: SP Automatic, A$5/día, bid default 1.50 (subido de 1.00), Delivering. Gasto inicial A$2.26/4d — cuello de botella era el bid, no el presupuesto.
2. **"SM-manual-broad-01"** ID `A04454593F9IGDM5ZBWGC`: SP Manual, A$15/día, dynamic bids down-only, 3 productos, 53 keywords (broad/phrase/exact, núcleo: snuffle mat, dog snuffle mat, foraging mat, nosework...), 14 negatives phrase (dog bed, pee pad, yoga mat, door mat, litter, grass...). Bid default A$1.78, keyword-level A$0.75-0.94.
- Campaña vieja US "Campaña kits" (2023, pausada): ignorar.

## Créditos NSI (regla de oro)
NO son gratis: match 1:1 por gasto (A$75→A$75, A$300→A$300, A$1.500→A$1.500). Requisitos: campaña SP dentro de 90 días de 1er ASIN buyable (✓ 4-nov), completar gasto de cada nivel en 30 días del launch (~4-dic), créditos llegan ≤14 días hábiles y expiran en 30 días. Decisión Plon: perseguir A$1.500 solo si el checkpoint de ~20-nov muestra CVR>0 con 50+ clicks. Otros bonos: A$150 PCP / A$300 Amazon SEND (verificar cómo entró el primer envío FBA).

## Sin Brand Registry (decisión Plon 07-nov)
No hay trademark → sin Vine, A+, Sponsored Brands ni crédito 5%. Cuando se quiera: IP Australia acepta filing online (~A$250-400, 1h) y Amazon Brand Registry AU ACEPTA marcas pending — desbloqueo rápido, no meses.

## Watcher de órdenes SP-API (ventas → Discord + Sheet)

- Órdenes en `Pending`: Amazon aún NO revela OrderTotal ni precios de ítems. NO escribirlas al Sheet (fila fantasma con precio 0) y NO saltarlas en silencio — preferencia de Plon: anunciarlas como "📥 Orden recibida · en espera (Pending)" en el hilo de ventas y re-anunciarlas completas con precio/margen al salir de Pending. El silencio entre compra y confirmación es exactamente lo que dispara "no me llegó nada a Discord".
- Un fallo de la API NO es "cero ventas": con HTTP != 200 en /orders, salir por stderr + `sys.exit(1)` para que el runner dispare la alerta de fallo. Disfrazar un fallo de silencio en un watcher de ventas es la peor salida posible — nadie revisa un "sin novedades" que miente.
- Patrón `no_agent` (stdout entregado verbatim): imprimir SOLO cuando hay venta/reembolso o en DRY. Sin novedades, stdout vacío = Discord en silencio; nada de logs de diagnóstico en el stdout de producción.
- No confiar en el token de un bot para posteo directo sin antes probarlo (`GET /users/@me`): un token revocado da 403 en TODO, incluso listando guilds, y el script puede haber "funcionado" semanas atrás. Preferir la entrega por el runner (stdout → deliver) sobre posteo directo con token propio.
- Si una fila fantasma (Pending con precio 0) YA salió publicada, corregir en dos frentes el mismo turno: (1) borrar la orden de TODOS los frentes de dedupe — la entrada de `seen_sales` en `watch_state.json` Y la fila en el Sheet de Ventas (col B, vía `sheet_existing_orders()`); dejar cualquiera de los dos hace que el watcher la siga considerando "ya registrada" para siempre y la venta real nunca se escriba; (2) publicar nota de corrección en el MISMO hilo de ventas invalidando la fila. Una fila `AUD 0.00 · margen negativo` sin corrección se lee como venta con pérdida y genera pánico fundado.
- Para borrar una fila del Sheet con `deleteDimension`: resolver primero el `sheetId` interno de la pestaña desde `spreadsheets().get()` (los tabs NO usan sheetId por índice — asumir 0 ejecuta la llamada "sin error" y no borra nada). Verificar SIEMPRE releyendo `values().get()` tras el delete: el éxito del batchUpdate no prueba nada.
- Mapa de hilos de Discord del canal finanzas: `/opt/hermes-agent-data/amazon-spapi-setup/discord_threads.json` (ventas, devoluciones, inventario, incidencias, p&l semanal, fees). Usar el ID del hilo, no el canal padre — un canal padre eliminado/movido responde 404 y el post se pierde en silencio.
- Verificar un posteo directo por el HTTP 200 del POST, no releyendo el canal: el bot de finanzas tiene Send Messages pero puede carecer de Read Message History (POST 200, GET 403) — concluir "falló" por el GET es falso negativo.
- Pausas de emergencia de crons y radio de negocio: ver hermes-cron-health (§ Reinicio del gateway y pausas de emergencia). Regla concreta: tras una pausa masiva, reactivar PRIMERO el watcher de ventas; una venta que entra durante la pausa no se anuncia nunca retroactivamente salvo re-consulta manual de la API.

## Reglas duras
- Nunca cambiar precio ni stock sin OK explícito de Plon.
- Cupones = palanca de descuento de launch; NO bajar precio base (mata historial y riesgo Buy Box al subir). DECISIÓN PLON 07-nov: UN cupón único de **18%** para los 3 ASINs, inicia 8-nov (reemplaza el plan 15/15/20).
- Primeras 2-4 semanas se optimiza por CTR/impresiones, NO por ACoS. Negativizar términos con ~20 clicks sin venta.
- Graduar convertidores del search term report a campañas Exact a partir de la semana 3.
- Subidas de precio: escalones de ~5% con ventas en cada nivel.
- Marketplace mediana pet supplies AU: A$12-25; benchmarks: CPC A$0.60-0.90, CVR 8-10% sin reviews, ~7 clicks/venta.
- Ventana clave: Black Friday 28-nov-2026; reseñas objetivo vía botón Request a Review (compliant) hasta tener Brand Registry.
