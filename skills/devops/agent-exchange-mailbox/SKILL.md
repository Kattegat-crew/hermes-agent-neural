---
name: agent-exchange-mailbox
description: Use when routing a request to Bob on PROD via the mailbox.
tags: [hermes, prod, inter-agent, mailbox, discord]
version: 1.0
author: ragnar
license: internal
metadata:
  hermes:
    tags: [hermes, prod, inter-agent, mailbox, discord]
    related_skills: [hermes-cron-ops, notification-delivery-reliability]
---

# agent_exchange.py — Buzón agentes ↔ Bob (PROD)

## When to Use

- Cuando un agente necesita entregar una tarea/solicitud a Bob (o responder tickets de Bob) en PROD.
- Cuando Discord rechaza con 403 editar un mensaje creado por otro bot: la edición se pide por este buzón, no se insiste con la conexión propia.

Ruta en PROD: `/opt/data/scripts/agent_exchange.py` (vía `ssh prod`). Canal bidireccional agentes ↔ Bob.

## Comandos verificados

```bash
ssh prod 'python3 /opt/data/scripts/agent_exchange.py send --from ragnar --prioridad alta --asunto "..." --tarea "..."'
# Flags opcionales de send: --deliver, --archivo, --intento
ssh prod 'python3 /opt/data/scripts/agent_exchange.py list --agent ragnar'
ssh prod 'python3 /opt/data/scripts/agent_exchange.py read --agent ragnar [--todo]'
```

- `send` = agente → Bob (crea ticket). `notify` = Bob → agente (mensaje libre, sin ticket). `reply` = Bob → agente (cierra un ticket).
- `send` deposita en `/opt/data/inbox/<agente>/pending/<ticket-id>.json` y el cron `escalation-watcher` lo reclama en ≤5 min; la respuesta queda en `/opt/data/inbox/<agente>/done/<ticket-id>.json`.
- Verificar recepción SIEMPRE con `list --agent <agente>` (pending → processing → done) antes de dar la tarea por encaminada.

## Trampas

1. **Webhook de aviso `buzon-bob` puede fallar sin pérdida:** si imprime `[exchange] webhook buzon-bob no enviado (buzon.nuevo, deposito intacto): Connection refused`, el depósito en `pending/` está intacto y el watcher lo recoge igual. No reenviar por el fallo del webhook; confirmar con `list`.
2. **Discord: no se puede editar el mensaje de otro bot.** Intentar sobrescribir un mensaje raíz creado por Bob desde otra conexión devuelve 403 Permission. El camino correcto es pedirle la edición a Bob por este buzón (con la instrucción exacta de qué sobrescribir), no insistir con la conexión propia.
3. El aviso de nuevo mensaje al agente destino llega por webhook/routing propio de cada perfil; el emisor no debe asumir entrega instantánea — hay latencia del watcher.

## Lado receptor: mensaje nuevo de Bob (cron buzon-bob)

Los mensajes entrantes llegan como JSON en `ssh prod /opt/data/inbox/<agente>/from-bob/`; el cron inyecta un extracto, pero el JSON original en PROD es la fuente (lee el archivo cuando el extracto recorte contenido o falte evidencia).

1. **Verifica los estados afirmados de forma independiente del eco del reporte.** Un PATCH exitoso NO prueba el estado final: un reporte puede citar hashes de una versión intermedia si hubo dos corridas sobre el mismo objetivo. Para mensajes de Discord, haz GET del mensaje por API con el token bot de `/opt/data/secrets/discord-nca-bot.token` (headers `Authorization: Bot <token>` y User-Agent de bot), compara `len(content)`, `edited_timestamp` y `sha256(content)[:12]` contra lo reportado, y solo entonces da por verificado.
2. **Responde por acción, no por acuse.** Si el mensaje es un cierre informativo sin pedidos ni errores, NO contestes al buzón: el ping-pong de acuses entre bots satura el canal. Registra el estado verificado en el archivo de campaña correspondiente (`/opt/hermes-agent-data/brain/campaigns/…`) y cierra el turno. Responde solo si hay que corregir, escalar, o el emisor pidió confirmación explícita.
3. **Distingue reporte de corrección cuando haya varias corridas.** Si el emisor manda un mensaje que corrige uno anterior, el último es el estado vigente y el anterior queda superado; cita los hashes/datos del último en tu registro, nunca los del primero.
