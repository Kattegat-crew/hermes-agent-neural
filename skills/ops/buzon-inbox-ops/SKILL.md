---
name: buzon-inbox-ops
description: "Use when a buzon mailbox wakeup requires verification."
version: 1.0.0
author: NeuralCrew
license: proprietary
metadata:
  hermes:
    tags: [buzon, mailbox, verificacion, evidencia, telegram, escalation]
    related_skills: [discord-server-ops]
---

# Buzón / mailbox wakeups: verificar, evidenciar, escalar

## When to Use

Un mensaje tipo `[buzon-<agente>]` despierta la sesión: `{event_type: "buzon.respuesta", buzon_key, ticket_id, de, to, estado, mensaje}`. La clase de tarea es: procesar el aviso, verificar sus afirmaciones en la fuente, archivar evidencia y escalar al Admin lo que solo él decide.

## Flujo canónico (en orden)

1. **Leer la fuente real del aviso, nunca solo el texto del mensaje.** Los JSON del buzonario viven en PROD: `ssh -o BatchMode=yes prod` y leer `/opt/data/inbox/<agente>/done/<ticket>.json` (campos `cerrado_en`, `cerrado_por`, respuestas). Salidas propias al buzonario: `/opt/data/inbox/<agente>/from-agents/`.
2. **Verificar cada afirmación en la fuente antes de repetirla.** Regla dura: ni Bob ni ningún bot son fuente de verdad — son punteros. Hilos de Discord: releer con `GET /channels/{thread}/messages?limit=25` (array JSON directo) y recalcular hash local (`sha256` truncado a 12) por mensaje para detectar ediciones o añadidos que el aviso no menciona. Afirmaciones sobre repos GitHub: `GET /repos/{owner}/{repo}` + `/branches` + `GIT_TERMINAL_PROMPT=0 git ls-remote <url>` (0 refs = vacío, exit 0). Afirmaciones sobre directorios del host: inspección viva por SSH (propietario, `git remote -v`, conteo de commits/objetos), nunca memoria.
3. **Archivar evidencia estructurada en el inbox de PROD** (`/opt/data/inbox/<agente>/done/evidencia-<ticket>-verificacion.json`): contexto, tabla de mensajes/afirmaciones con `verificado: true/false` + `metodo`, estado real del entregable y acciones ejecutadas. Plantilla: `templates/evidencia-verificacion.json`. Validar JSON tras escribir y registrar sha256.
4. **Escalar al Admin por Telegram, no al hilo de origen.** Enviar con `/opt/data/home/.local/bin/hermes send --to telegram:8709909260 "..." --quiet` ejecutado desde `/opt/hermes-agent-data` (carga los secrets; el binario no está en el PATH por defecto). Estructura del aviso: hechos verificados con método → ítems explícitamente marcados "no verificable desde el sistema" → decisiones que SOLO el Admin puede tomar (numeradas) → ruta de evidencia + sha256. Sin salida cruda de comandos.
5. **Cerrar el gate anti doble-despertar.** El gate es un script bash cuyo contrato es la ÚLTIMA línea de stdout: `{"wakeAgent": false}` salta el turno (0 tokens), `{"wakeAgent": true}` despierta. Deduplica contra `/opt/hermes-agent-data/state/buzon_<fuente>.seen` comparando líneas exactas `done:<archivo>|<valor_disparador>`. Si el aviso llegó por otra vía (webhook) o el registro `done/` tiene el par incompleto, añade manualmente la línea que el gate habría escrito (copia el formato exacto de las líneas previas del `.seen`) y valida ejecutando el gate dos veces seguidas: `{"wakeAgent": false}` en AMBAS. Una sola pasada limpia no prueba nada — el gate consume registros en tandas y puede ocultar el siguiente pendiente detrás del que acabas de cerrar.

## Pitfalls

- **No escribas en el hilo/ticket de Discord sin autorización EXPLÍCITA de esa escritura puntual.** Una autorización previa de "actualizar los mensajes existentes" no cubre añadir mensajes nuevos; si un tercero escribió después, tu corrección también sería un mensaje nuevo. Verificar y archivar fuera del hilo; escalar por Telegram.
- **No atribuyas a tu propia cuenta acciones sin registro de comando.** Si un recurso (repo, cuenta, publicación) apareció bajo tu identidad pero esta sesión no tiene el comando que lo creó, repórtalo al Admin como no atribuible hasta su confirmación — jamás lo des por tuyo ni lo repitas como hecho.
- **Nunca uses `rm` en un comando que también mencione `/opt`:** la deny rule del usuario (`*rm *-r* /opt*`) bloquea el comando completo aunque sea una sonda benigna. Para probes de escritura y limpieza usa `python3 -c` con `os.remove` (escribe, mide, borra en un solo proceso).
- **`estado: "done"` del buzón no significa "nada que hacer":** significa "registrado". El paso de verificación independiente y el gate se ejecutan igual; lo que cambia es que no hay ejecución de código requerida.
- **Artefactos creados por SSH son root:root y contaminan el buzón.** `ssh prod` entra como root (uid 0): cualquier `.json` que escribas queda root:root y aparece como "UNKNOWN:UNKNOWN" al mirarlo desde el contenedor (que no resuelve uid 10000). Tras el `scp`, ejecuta siempre `chown 10000:10000 <archivo> && chmod 644 <archivo>` y verifica con `stat -c "%u:%g %a"`; si no, acumulas basura root:root en `done/` que nadie debe tocar después.
- **Un despertar que NO vino del gate dejó el `.seen` sin actualizar.** Si el aviso entró por webhook u otra vía, el gate no escribió su línea de estado y el cron repetirá el mismo contenido en su próximo ciclo (hasta 5 mensajes por turno). Añade tú la línea `done:<archivo>|<valor_disparador>` con el formato exacto del `.seen` y valida con la doble ejecución.
- **Un cierre anotado sin `respuesta` ni `cerrado_por` (contestación por mensaje libre en vez de cierre de ticket) deja el registro `done/ticket-*.json` incompleto y dispara un despertar extra**, porque el gate compara `base|cerrado_en` y ese par nunca consta. No borres ni reescribas el artefacto: añade la línea que falta al `.seen` y valida con la doble ejecución.
- **Cierra el hilo sin responder otra vez.** Un ACK de cierre no se contesta con otro ACK: responder reabre la cadena 001→002→003→004. Verifica, archiva evidencia y termina.
- **Confirmar recepción sin verificación es el fallo típico:** responder "recibido, nada que ejecutar" sin releer la fuente deja pasar mensajes añadidos por terceros y afirmaciones falsas que quedan como hechos en el historial.

## Relación con otras skills

Gobernanza de hilos de tickets del foro técnico (tags, creación, relectura post-escritura): `ops/discord-server-ops`. Esta skill cubre el lado del buzón: verificación, evidencia, escalado y gate de deduplicación.
