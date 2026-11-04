# Caso Lucky Brothers - fases y estado (16-sep-2026)

Detalle de sesion para el alta de Lucky al pipeline de informes. Las fases NO estan ejecutadas - esperan autorizacion del Admin (F0 manda mensajes reales).

## Estado del sondeo (todo read-only, verificado)
- Buzon lucky-gmail - mismo KASSIUSS (luckybrothers@kassiuss.me), HTML identico al de Golden, parser reutilizable tal cual.
- ~201 informes en el inbox (~33 dias de historico para backfill ago->hoy).
- 6 sedes exactas - LA CALERA, LA CALERA GARDENS, TUNJA ONCE, CHIQUIQUIRA 1, CHIQUIQUIRA 2, FUNZA.
- Secrets ya existentes en PROD - lucky-gmail.json y lucky-drive.json.
- Drive - NO existe Sheet de ventas de Lucky (verificado sondeo_drive_lucky.py) - se crea uno nuevo en F3. Precedente de duplicados - carpetas homonimas 'Fotos Locales' x2.

## Mapa de entrega verificado (profile_routes)
- Chats de Helmer - los entrega el perfil `helmer`. Chats de Yulieth - los entrega el perfil `yulieth`. El chat del Admin - perfil `default`.
- `platforms.whatsapp.enabled: false` NO impide entregar a los chats propios del perfil (nancy saca 12 recordatorios diarios asi).
- El error 'platform whatsapp not configured/enabled' es el fallback fallido cuando el perfil intenta un chat que NO es suyo.

## Fases pendientes de OK
- F0 - prueba de canal (2 mensajes reales a Helmer y Yulieth).
- F1 - marcas.yaml + ventas.py, Golden intacto (paridad contra su XLSX actual).
- F2 - backfill ago->hoy + captura diaria 16:00.
- F3 - Sheet nuevo en Drive de Lucky (4 pestanas/mes, mes vivo delante).
- F4 - diario 07:10 + faltantes cada 5 min -> Helmer y Yulieth (cada uno desde su perfil dueño).
- F5 - PDF mensual membreteado -> Admin (perfil default).
- F6 - cierre de conocimiento (brain, Engram, memoria, ledger, skills).

## Preguntas abiertas al Admin (16-sep)
1. OK para F0 (2 mensajes reales).
2. ¿El mensual de Lucky va solo al Admin (recomendado) o tambien a Helmer/Yulieth.
3. ¿Diario igual que Golden (07:10 consolidado + faltantes cada 5 min) o resumen unico a hora fija (recomendado igual).