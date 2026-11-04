---
name: notification-delivery-reliability
description: "Use when a cron message or alert never reached the user."
tags: [cron, delivery, entrega, notificaciones, alertas, whatsapp, telegram, verificacion]
version: 1.0.0
author: Ragnar
metadata:
  hermes:
    tags: [cron, entrega, notificaciones, whatsapp, telegram, verificacion]
    category: devops
    related_skills: [scheduled-job-diagnosis, whatsapp-bridge-operations, hermes-scheduled-jobs]
---

# Fiabilidad de entrega de notificaciones y reportes programados

Clase de trabajo: **"el job corrió pero el mensaje nunca llegó"** y su versión preventiva (un reporte/alerta que NO puede perderse). Aplica a crons Hermes, daemons de aviso, digests y alertas — el fallo es siempre el mismo y siempre invisible: el sistema sigue verde, el usuario simplemente no se entera.

Validado 10/09/2026 con el paquete diario del calendario de campaña (Golden/Lucky): el job marcó `ok` y el mensaje no llegó **dos días seguidos**; nadie lo detectó hasta que el usuario preguntó "¿a qué horas llega hoy?".

## Regla central: `ran` ≠ `delivered`

`last_status: ok` (y la fila `completed` en `executions.db`) significan que el agente/script terminó. **La entrega es un paso posterior y se registra en otro campo.** Nunca reportes "enviado" sin evidencia en el canal destino.

## Diagnóstico (en orden)

1. **Entrega en el registro del job** (`/opt/data/cron/jobs.json`, o `hermes cron list` → `⚠ Delivery failed: …`):
   ```bash
   python3 -c "import json;d=json.load(open('/opt/data/cron/jobs.json'));[print(j['name'],j.get('last_status'),j.get('last_delivery_error')) for j in d['jobs']]"
   ```
   `last_delivery_error` con texto = el contenido se generó y se perdió al enviar.
2. **Recurrencia — el paso que cambia el veredicto** (`last_delivery_error` solo guarda el último):
   ```bash
   grep -ahE "delivery error|send failed" /opt/data/logs/agent.log | sed -E 's/(.{19}).*/\1/' | uniq -c | tail
   ```
   Un fallo aislado se reintenta; una tasa de pérdida (ej. ~15% de los envíos, 2 días seguidos sin entregar) exige cambio de diseño, no retry manual.
3. **Health del transporte NO es evidencia**: `curl -s 127.0.0.1:3000/health` puede responder `connected` en el mismo instante en que un envío falla con RST. Tampoco lo es el log del bridge: si el reset ocurre a nivel TCP, **no queda ninguna línea**.
4. **Recupera el contenido** de la corrida: `cron/output/<jobid>/<fecha>_<hora>.md`. Si es `root:root`, léelo con `docker exec <ctr> cat …` (el backend root del Desktop escribe ahí).
5. **Quién ejecutó el job** (hay varios tickers compitiendo por el mismo `jobs.json`):
   ```bash
   python3 -c "import sqlite3;c=sqlite3.connect('/opt/data/cron/executions.db');[print(r) for r in c.execute('select job_id,pid,status,claimed_at from executions order by claimed_at desc limit 20')]"
   ps -eo pid,uid,args | grep -a 'hermes serve\|gateway run'
   ```
   Útil para saber si el fallo se correlaciona con un ticker concreto (p. ej. el backend root `hermes serve --isolated`).

## Modos de fallo catalogados

- **Envío único sin reintento.** El adaptador de WhatsApp (`/opt/hermes/plugins/platforms/whatsapp/adapter.py` ~L1770–1839) hace un solo `POST http://localhost:{bridge_port}/send` (aiohttp, 30 s) y ante excepción devuelve `{"error": "WhatsApp send failed: <e>"}`; no hay cola ni dead-letter. Errores observados: `[Errno 104] Connection reset by peer`, `Server disconnected`.
- **Ruido benigno que distrae.** El bridge reconecta solo con loops `Connection closed (reason: 428/503)` — eso NO es la causa del envío perdido; no persigas ese log.
- **Falso verde por status.** Cualquier tablero que solo lea `last_status` mostrará todo sano mientras el usuario no recibe nada.

## Remediación

1. **Redundancia de destino (barata y efectiva).** `deliver` acepta varios destinos (lista o string con comas): `whatsapp:<jid>,telegram:<chat_id>`. El scheduler entrega **por target** y un target caído hace `continue` sin abortar los demás (verificado en `/opt/hermes/cron/scheduler.py`, `_deliver_result`; forma canónica del campo en `hermes_cli/cron/jobs.py`: `deliver = job.get("deliver") or ["local"]; if isinstance(deliver, str): deliver = [deliver]`).
   - Elige el respaldo por utilidad real de push al móvil, no por "otro canal": Telegram ya probado entregando a diario suele ser mejor respaldo que el canal de equipo.
2. **Reenvío manual inmediato** desde el `.md` de la corrida cuando el usuario pregunta — la respuesta útil es el contenido, no la disculpa.
3. **Cambio sobre `jobs.json` = alto impacto**: backup del archivo + OK explícito del usuario antes de aplicar.

## Elegir y validar el destino (preventivo)

La mitad de los casos "no llegó" se evita eligiendo bien el destino **antes** de confiar en él.

1. **Gramática del campo `deliver`** (Hermes): `local` (solo guarda), `origin`, `all` (todos los home channels), `bot-chat[:<perfil>]`, `platform:chat_id[:thread_id]` (ej. `discord:1542126606900920340`, `telegram:-100…:17585`). Se pueden combinar con comas y un target caído **no** aborta los demás. `failure_deliver` desvía SOLO los avisos de fallo (`local` los silencia): úsalo cuando el job entrega en un canal compartido.
2. **`attach_to_session: true`** hace la entrega *continuable*: el usuario puede responder y el agente recibe el brief en contexto. Es la bandera que convierte un aviso en flujo de aprobación — pero solo aplica a `origin`, al home fallback y a **un** target explícito; los targets broadcast nunca se adjuntan. No lo des por hecho: si el job lo ejecuta un ticker standalone (p. ej. el backend root del Desktop) puede no haber relay vivo, así que **no** apoyes el flujo de aprobación solo en él.
3. **Regla de oro para flujos de aprobación:** el canal destino debe ser uno donde el mensaje del usuario **enrute al agente** (en Discord: canal presente en `discord.free_response_channels` del perfil). Con eso el reply "Dale <ID>" se procesa por routing normal, sin depender de `attach_to_session`.
4. **Identidad vs. respondibilidad:** publicar vía webhook permite un nombre propio, pero un mensaje de webhook no arrastra hilo de sesión. Si el usuario aprobará ahí, publica con el **bot**; deja el webhook para avisos de solo lectura.
5. **Antes de prometer un canal nuevo:** verificar que el remitente puede escribir (permisos del bot) y hacer **una prueba real** (POST de prueba y borrarlo si es ruido) — el health del transporte no es evidencia.
6. **Migrar destinos es alto impacto:** backup de `jobs.json` + OK explícito, aplicar, y después disparar cada job a mano para confirmar llegada real (no basta con que el campo quedó escrito).

Detalle operativo (auditoría de webhooks de Discord, IDs del servidor NeuralCrew, checklist de migración): `references/delivery-channel-migration.md`. Verificador reutilizable: `scripts/discord_verify_webhook.py`.

## Verificación que vale: el contexto del scheduler, no tu sesión

Un POST exitoso **desde la sesión del agente** no prueba que el automatismo vaya a entregar:
el agente corre con otro uid y otro entorno (secretos hidratados en memoria, `DISCORD_*`
inyectado). El job corre con un entorno limpio. Un "enviado, status 200" obtenido a mano no
cubre el camino que correrá el lunes.

1. **Sonda con entorno limpio** (mismo binario, uid del scheduler) — imprimir longitud y
   prefijo, nunca el token:
   ```bash
   env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/root python3 -c "
   import sys; sys.path.insert(0,'/opt/data/scripts'); import ncl_discord_mcp as m
   for p in ('roshi','default'):
       try: t=m.load_bot_token(p); print(p,'OK',len(t),t[:6]+'…')
       except Exception as e: print(p,'FALLA',e)
   "
   ```
   Falla típica por perfil: `-32001` (vault `/etc/hermes-vault` es `root:root 700`). Detalle y
   workarounds en `hermes-secrets-v022x-ops`.
2. **Entorno del proceso que de verdad ejecuta**, no el de tu shell:
   `tr '\0' '\n' < /proc/<pid>/environ | grep -oE '^DISCORD[A-Z0-9_]*='`.
3. **Propaga el exit code.** El `post`/`curl` debe ser el ÚLTIMO comando del wrapper (el status
   de un `if` es el de su último comando) y el script debe salir ≠0 si el envío falla. Sin esto
   el job queda `last_status: ok` con `post:401` impreso en el `.md`. Probar el fallo a
   propósito con un canal inválido y exigir `rc=1`.
4. **Un scheduler por alerta.** `grep -r` en `/etc/cron.d/` antes de crear un job Hermes para
   la misma tarea: dos programaciones = dos barridos y dos mensajes el mismo día.

## Cómo responder al usuario

- Di en una línea *qué* falló (el envío, no el canal ni el job) y *desde cuándo* (número de días/ocurrencias).
- Entrega el contenido que nunca llegó, en el chat donde está preguntando.
- Cierra con la mitigación propuesta y pide autorización; no apliques el cambio sin confirmación.

## References

- `references/cron-delivery-losses.md` — evidencia completa (timestamps, campo por campo, comandos) del caso 08–10/09/2026.
- `references/delivery-channel-migration.md` — migrar los crons de un canal frágil a uno estable: destino, identidad, ruteo de respuestas, auditoría de webhooks y checklist.
- `scripts/discord_verify_webhook.py` — localiza el webhook de una URL en el guild, compara el token carácter por carácter y opcionalmente manda una prueba.

## Skills relacionadas (user-owned, no editables por el curator)

`scheduled-job-diagnosis`, `whatsapp-bridge-operations`, `instant-notification-daemons`, `hermes-scheduled-jobs` cubren territorio vecino. Si una de ellas debe corregirse o ampliarse: `hermes curator adopt <nombre>` primero.
