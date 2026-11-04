---
name: email-report-ingestion
description: Use when Gmail report emails need parsing into digest crons.
---

# Ingesta de informes por correo → digest programado

Patrón verificado en producción (14-sep-2026): los datos operativos de un cliente
(informes de venta diaria KASSIUSS/Golden Game, notificaciones de pago Bre-B) llegan
como correos con tablas HTML a un buzón Gmail del que tenemos secret OAuth por owner.
La skill cubre las dos mitades: (1) leer y parsear esos correos vía Gmail REST
directo, (2) convertir el resultado en un cron digest con retraso controlado.

## 1. Acceso Gmail vía secret por owner (REST directo)

Los secretos viven en `/opt/data/secrets/{owner}-gmail.json` con claves
`refresh_token`, `client_id`, `client_secret` (owners: golden, helmer, jacqueline,
jonathan, lucky, nancy, neuralcrew). Son 0600; jamás imprimir sus valores.

Flujo verificado:

1. POST `https://oauth2.googleapis.com/token`, body form-urlencoded
   `grant_type=refresh_token&refresh_token=...&client_id=...&client_secret=...`
   → devuelve `access_token`.
2. GET `https://gmail.googleapis.com/gmail/v1/users/me/messages?q=<query>&maxResults=N`
   con header `Authorization: Bearer`.
3. GET `/users/me/messages/{id}?format=full` para el cuerpo completo
   (o `format=metadata&metadataHeaders=Date&...` para solo cabeceras).

Scripts listos (verificados 14-sep-2026 contra golden-gmail):

- `scripts/gmail_search.py <secret.json> "<query>" [max]` — lista `Fecha | From | Asunto` + total estimado.
- `scripts/gmail_fetch_text.py <secret.json> "<asunto exacto>"` — cuerpo plano (HTML→texto).
- `scripts/gmail_fetch_tables.py <secret.json> "<asunto exacto>"` — tablas HTML como filas `a | b | c`.

Pitfalls:

- HTTP 403/429 de cuota → reintentar con sleep ~1.2 s (los scripts ya lo hacen).
- `body.data` de Gmail es base64**url** SIN padding: rellenar con `=` hasta múltiplo de 4.
- `q` soporta `from:` y `subject:"frase exacta"`; el TOTAL devuelto es una ESTIMACIÓN.
- Con cuerpo tipo tabla con estilo inline, regex sobre `<table>/<tr>/<td>` +
  `html.unescape` rinde mejor que un strip HTML genérico.

## 2. Cron digest con retraso ("20 min después del último correo")

No se usa trigger de correo: se usa un cron Hermes `no_agent` (script puro,
determinista) con tick corto dentro de la ventana esperada (p. ej. cada 5 min de
06:00 a 12:00). El script:

1. Busca el set de correos del día (p. ej. 6 informes de sedes) agrupados por
   **fecha de referencia** (parseada del ASUNTO, no del header Date — puede diferir).
2. Si falta alguno → calla (stdout vacío = sin entrega).
3. Si están todos: `last = max(header Date)`; dispara solo si
   `ahora ≥ last + retraso` Y esa fecha aún no fue reportada (archivo de estado
   clave fecha → dedup idempotente).
4. Imprime el informe a stdout; la entrega la hace el cron con `deliver: origin`
   (origin.platform=whatsapp), patrón ya operativo en el perfil helmer de PROD.
   OJO: la entrega WhatsApp de crons pierde ~15% de mensajes sin reintento.

Jitter de entrega ≈ intervalo del tick; elegirlo según la tolerancia del usuario.

## 3. Equivalente dentro de ActivePieces

Flow de referencia (Bre-B Golden, id `ybZF7O6TgBbKiAvvVvdHV`): PIECE_TRIGGER
`@activepieces/piece-gmail` / `gmail_new_email_received` (auth = conexión del owner
+ filtro `from`) → acción CODE con `stripHtml()` + `pick(/regex/)` por campo sobre
texto aplanado → acción de salida (`google-sheets insert_row`). Caso KASSIUSS
completo (tabla, sedes, horarios, decisiones de diseño abiertas):
`references/kassiuss-golden-informes.md`.
