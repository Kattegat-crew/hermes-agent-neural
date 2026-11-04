# Layout KASSIUSS - Golden vs Lucky (sondeo 16-sep-2026)

Verificacion read-only sobre correos reales para decidir si el parser de Golden (`kassiuss_diaria.py`, 529 lineas) sirve para Lucky.

## Veredicto
El HTML es IDENTICO entre marcas. El parser de Golden se reutiliza tal cual. Probado con el correo real de LA CALERA del 15-sep - fila `023 Maquinas`, Neto $2.841.315 extraido sin cambios.

## Datos del sondeo
- Sender Lucky - `luckybrothers@kassiuss.me` (mismo sistema KASSIUSS que Golden).
- Sedes Lucky verificadas - LA CALERA, LA CALERA GARDENS, TUNJA ONCE, CHIQUIQUIRA 1, CHIQUIQUIRA 2, FUNZA.
- Buzon Lucky - ~201 informes en el inbox (~33 dias de historico para backfill).
- Fila `Maquinas` - 13 celdas, indices de venta [3][4][5][6][7]; sanidad minima >=8 celdas; Neto = Bruto - Pagos - Jackpot.

## Patrones de sondeo read-only reutilizables
- Remoto - `scp -o ConnectTimeout=15 -q <sonda> root@100.73.30.29:/tmp/` + `ssh ... 'docker cp /tmp/<sonda> hermes-agent:/tmp/; docker exec -u hermes hermes-agent python3 /tmp/<sonda>'`.
- Salidas acotadas con head/tail. Tokens y credenciales SIEMPRE [REDACTED].
- Sondeos de esta sesion (desechables, /opt/data/workspace/ventas/) - sondeo_whatsapp.py (device-list/lid-mapping), sondeo_lucky_gmail.py (buzon), sondeo_chats.py (perfil->chat), sondeo_layout_kassiuss.py (comparativa layout), sondeo_drive_lucky.py (Sheet existente - NO hay Sheet de ventas de Lucky, crear uno; precedente de duplicados - 'Fotos Locales' x2).

## Riesgos operativos
- FUNZA irregular (15-sep 10:29, 16-sep no llego) - el diario tolera faltantes y lista pendientes.
- LA CALERA es prefijo de LA CALERA GARDENS - match exacto, nunca por prefijo.
- Asunto con prefijo de marca pegado - normalizar antes de rutear.
- Backfill grande - pausas entre lotes por rate limit de Gmail.