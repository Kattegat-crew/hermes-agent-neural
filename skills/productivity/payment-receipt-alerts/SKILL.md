---
name: payment-receipt-alerts
description: "Use when a QR payment receipt must alert the team"
tags: [pagos, payments, qr, bre-b, alertas, gmail, webhook, idempotencia]
version: "1.0"
author: Ragnar
created: 2026-09-10
category: devops
metadata:
  hermes:
    tags: [pagos, bre-b, qr, alertas, gmail, activepieces, webhook, casino]
    related_skills: [activepieces-flow-editing, activepieces-selfhost-ops, activepieces-connection-api, notification-delivery-reliability]
---

# Alertas de pago en segundos (recibos bancarios / Bre-B / QR)

Convierte el **correo de notificación de pago del banco** en un **aviso operativo inmediato** (valor, quién pagó, hora, código de operación).

## When to Use

- Un local cobra por **QR** y hay que confirmar **en segundos** que el pago entró antes de entregar efectivo.
- Caso real (Golden Game / Lucky Brothers): el cliente paga por QR y la cajera le entrega el efectivo para jugar en la máquina — es un **retiro encubierto**. El riesgo son los **QR falsos / comprobantes falsos**: si el aviso sale del **banco** (no de una captura de pantalla), la cajera puede entregar sin miedo.
- En general: cualquier correo de notificación de pago que deba convertirse en alerta operativa.

## Caso verificado (10/09/2026) — Lucky Brothers / The Grand Paradise

- Buzón: `luckybrothers.sas@gmail.com` (conexión ActivePieces `lucky-gmail`; secreto materializado en `/opt/data/secrets/lucky-gmail.json`, chmod 600).
- Remitente: `notificacionesBreB@bbva.com` — asunto **"Recibiste dinero en tu cuenta a través de Bre-B."**
- Volumetría real medida: **~40-46 pagos/día**, entre **$20.000 y $700.000**, promedio ~$122.000, 56 pagadores distintos en una semana → **no es bajo volumen**: el diseño debe aguantar picos sin perder ni duplicar avisos.
- Campos parseables del cuerpo (HTML → texto): fecha y hora, valor recibido, persona que envía, tipo de llave (Código de comercio), cuenta destino, **código de operación** (único por pago → llave natural de idempotencia).
- Formato exacto, muestra y regexes: `references/bre-b-bbva-receipt-format.md`.
- Lector re-ejecutable: `scripts/read_receipts.py`.

## ⚠️ Limitación estructural — aclarar ANTES de construir

El correo **no identifica la sede**: todos los pagos de todos los locales caen a la **misma cuenta destino** y el tipo de llave es genérico. Se puede avisar *"entró $80.000 de WILSON ORLANDO IBANES a las 11:13"*, pero **no** determinar automáticamente a qué local avisar. Salidas: (a) un solo grupo que reciba todo (la cajera empareja por valor + nombre), o (b) una cuenta/llave Bre-B por sede.
Aclararlo con el Admin **antes** de prometer "aviso por local".

## Latencia: NO prometer "segundos" con polling

- El trigger de Gmail de ActivePieces **hace polling** (minutos, no segundos). Sirve como respaldo, no como solución.
- Para segundos: **correo entrante con webhook** — un filtro de Gmail reenvía el recibo a un buzón con ruta entrante (Mailgun routes, o Cloudflare Email Worker) → POST al webhook → flujo AP → notificación. Mailgun ya está en el roadmap del funnel, así que se reutiliza infraestructura.
- Endurecimiento mínimo del flujo:
  1. **Validar el remitente** (solo el correo verificado del banco). Sin esto, cualquiera reenvía un correo falso al mismo buzón y el sistema "confirma" un pago inexistente.
  2. **Deduplicar por código de operación** (idempotencia): si el webhook se reintenta, no avisar dos veces.
  3. **Nunca** inferir un pago desde una captura/imagen: solo desde el correo del banco.

## Cómo leer el buzón (para diseñar y validar)

```bash
python3 scripts/read_receipts.py --secret /opt/data/secrets/lucky-gmail.json \
    --query 'from:notificacionesBreB@bbva.com newer_than:7d' --limit 30
# --raw imprime el texto plano de cada correo (para ajustar regexes)
```

- El secreto lo produce `verify_connection.py` (refresh_token + client_id + client_secret).
- **Rate limit:** leer mensajes uno por uno devuelve **403** si no se espacia → el script duerme (~0,25 s) y reintenta con backoff. Incluir ese patrón si se escribe uno mismo.
- **`metadataHeaders` debe ir como parámetro repetido** (`urlencode(..., doseq=True)`). Si se pasa como lista dentro de un solo string, los headers vuelven **vacíos** sin error visible.
- Query útil para descubrir el emisor real cuando no se conoce: `newer_than:20d` sin filtro y revisar remitentes (así se detectó `notificacionesBreB@bbva.com`).

## Contrato del aviso (contenido mínimo)

```
✅ PAGO CONFIRMADO — $80.000 · WILSON ORLANDO IBANES ORTIZ · 11:13 · op 1196…395
```

El **valor + nombre** permiten a la cajera emparejar con la persona que tiene al frente; el **código de operación** permite auditar después. Corto y sin tablas: va a un canal de móvil (WhatsApp/Telegram).

## Fases acordadas (patrón del Admin)

1. Primero **UNA** empresa (Lucky, cuyo correo ya está conectado) → pruebas reales → luego replicar a la otra.
2. **Golden Game** aún no tiene OAuth de **lectura** en ActivePieces (solo una conexión `Gmail Golden` de tipo **SMTP**, envío): conectar su Gmail antes de la fase 2. Verificar el tipo de pieza antes de asumir que se puede leer.
3. Todo corre en **ActivePieces de PROD** (`ap-app`/`ap-worker`, `100.73.30.29:8088`), no en dev.

## Pitfalls

- **No confundir "breve" con una herramienta**: en este negocio es **Bre-B**, el sistema de pagos inmediatos de Colombia; los recibos llegan del banco del local.
- **No prometer latencia** que el mecanismo elegido no da (polling ≠ segundos).
- **No dar por hecho** que el correo trae la sede: ver la limitación estructural arriba.
- **No guardar secretos** en el repo ni en el chat: van materializados en `/opt/data/secrets/` (chmod 600).
- **No mezclar** la hora del encabezado (UTC) con la del cuerpo (hora local Colombia) al construir el aviso.

## Arquitectura en Producción (Actualizado 02/10/2026)

El sistema opera bajo un patrón de **dos capas (Tiempo Real + Consistencia Eventual)**:

### 1. Capa de Tiempo Real (ActivePieces)
- Polling cada 60 segundos (`*/1 * * * *` en BullMQ) en bandejas Gmail.
- Ingesta, parseo de HTML a campos estructurados, escritura granular a Google Sheets y alerta a Discord.
- **Mapeo oficial de Google Sheets:**
  - **Lucky Brothers:** Flow `e2yTTyYCWj0DAWHTX8lLw` → Spreadsheet `1bAcrcBjddAAqxo8V3xnwmOElk_9bAay5G-w1ZREUfGo` | `sheetId: 1686104785` (pestaña `Bre-B Lucky — Pagos`).
  - **Casino Golden Game:** Flow `ybZF7O6TgBbKiAvvVvdHV` → Spreadsheet `1j0vsPs4R4owvm_gisidizO0j0xckeZpK4z-Mev2xYu0` | `sheetId: 720415717` (pestaña `Bre-B Golden — Pagos`).

### 2. Capa de Red de Seguridad (Reconciliador Cron)
- Ejecución periódica cada 4 horas (`0 */4 * * *`) en Ragnar:
  `/usr/bin/flock -n /tmp/reconcile_breb.lock /usr/bin/python3 /root/breb-reports/reconcile_breb.py --tenant all --apply >> /root/breb-reports/reconcile.log 2>&1`
- Concilia contra Gmail completo, inyecta pagos caídos por fallas de red y purga registros corruptos usando **Google Sheets API v4** sin sobreescribir pestañas de informes (`Informe Septiembre`, `Informe Octubre`).

### 3. Regla Crítica de Operación (ActivePieces Worker Cache)
- `ap-worker` compila y almacena en memoria RAM (`cached`) y disco (`/opt/docker/activepieces/cache/v11/flows/{flowVersionId}/cache.json`) las versiones publicadas.
- **NUNCA** modificar `sheetId` o configuraciones mediante `UPDATE` directo en PostgreSQL (`ap-db`) sin purgar la caché y ejecutar `LOCK_AND_PUBLISH` vía la API REST de ActivePieces; de lo contrario, el worker seguirá ejecutando en memoria los IDs obsoletos.

## Referencias

- `references/bre-b-bbva-receipt-format.md` — muestra real del recibo BBVA Bre-B, tabla de campos, regexes y volumetría.
- `scripts/read_receipts.py` — lector/parser re-ejecutable del buzón (refresh + Gmail API + rate-limit safe).
- `scripts/reconcile_breb.py` — script de conciliación no destructiva con Google Sheets API v4.

