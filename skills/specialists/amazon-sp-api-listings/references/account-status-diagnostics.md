# Account Status Diagnostics — Amazon AU (stranded / inactive store)

Procedimiento verificado (2-nov-2026) para diagnosticar por qué una cuenta con listings Active e inventario FBA recibido no vende. La causa comercial fue confirmada vía API: motivo stranded exacto "Please verify your account status" en los 3 SKU.

## Flujo de diagnóstico vía SP-API

1. Credenciales: en PROD leerlas de Vaultwarden (`/usr/local/bin/vw get "Terceros/Amazon SP-API - NeuralCrew"`), NO del `.env` local. Auth: POST `https://api.amazon.com/auth/o2/token` con refresh_token.
2. Endpoint para Amazon AU: `https://sellingpartnerapi-fe.amazon.com` (no el -na). Marketplace id del item `SP_API_MARKETPLACE_ID` del secret.
3. Crear reportes `POST /reports/2021-06-30/reports` con `marketplaceIds`, y encuestar `GET /reports/2021-06-30/reports/{id}` hasta `processingStatus=DONE` (poll cada ~12s; tipicamente DONE en <1 min).
   - `GET_STRANDED_INVENTORY_UI_DATA` → motivo de stranded EXACTO por SKU (aqui: "Please verify your account status").
   - `GET_MERCHANT_LISTINGS_ALL_DATA` → estado de listings (pueden decir Active aunque no haya ofertas).
   - `GET_FBA_MYI_ALL_INVENTORY_DATA` → stock real en FC (afwd / reserved).
4. Descargar el documento: `GET /reports/2021-06-30/documents/{docId}` → URL firmada; body TSV gzip, parsear con csv delimiter="\t" y utf-8-sig.
5. Confirmar el bloqueo de venta: Pricing API `GET /products/pricing/v0/price?MarketplaceId=..&SellerSKU=..` con `ItemOffersAvailable` → `NoBuyableOffers` en cada SKU.

## Quirks y límites de la API

- `GET /sellers/v1/account` responde HTTP 200 pero el payload trae `errors: [{code: "404", message: "Account not found for <seller-id>"}]` — SIEMPRE inspeccionar el body, no fiarse del status HTTP. No probar que la cuenta no exista.
- SP-API NO expone flujo para completar la verificación de cuenta (SIV) ni para activar el marketplace: es tarea de Seller Central/soporte humano. No intentar PATCH de cuenta.
- Account Health API puede reportar `NORMAL` con 200 puntos aun con el marketplace Inactive: NO usarlo para descartar bloqueos de activación.
- Cambiar fotos/copy de listings no resuelve un bloqueo de cuenta.

## Interpretación de "Please verify your account status"

Es un mensaje GENÉRICO de bloqueo de cuenta, no confirma que falte subir identidad. Foros Seller Central AU revisados (2-nov-2026):

- Caso AU casi idéntico (marketplace Inactive, sin banner ni tareas): la solicitud de verificación aparecía solo en **Gestionar casos de soporte** como "Under review", no en Información de cuenta.
- Bucle "Reactivate → Inactive → Charge Methods": si la reactivación redirige a cobros, probar otro método de cobro válido (tarjeta de cobro ≠ cuenta bancaria de depósitos).
- Pedir escalado a SIV a ciegas puede generar otro bucle: un vendedor AU recibió "esto no es de verificación de identidad" desde SIV.
- Existen causas no-identidad detrás del mismo mensaje (ej. verificación fiscal pendiente en UK).

## Ruta de activación recomendada

1. Seller Central con AU seleccionado → **Gestionar casos** buscando expedientes de Identity Verification / Account Review / Registration / Reactivation.
2. Revisar Notificaciones de rendimiento e Información de cuenta (incluido método de cobro de AU).
3. Si no hay acción disponible: abrir caso de diagnóstico de bloqueo con evidencia API (ids de reportes stranded, NoBuyableOffers por SKU, Account Health NORMAL, y el 404 de getAccount como anomalía adicional). Texto de caso listo en la sesión del 2-nov-2026; pedir requisito EXACTO, no instrucciones genéricas de edición de listings.
