---
name: escalada-tecnica
description: "Use when a task cannot be completed and must be escalated."
tags: [escalada, tickets, buzon, evidencia, protocolo, handoff]
---

# Protocolo de Escalada Tecnica (Regla Bob)

Cuando un agente NO puede completar una tarea (falta de herramientas, 2 intentos fallidos del mismo enfoque, o duda sobre el resultado), la ESCALA al agente tecnico del perfil default via buzon compartido.

## Regla dura anti-falso-exito

PROHIBIDO reportar exito sin evidencia observable (archivo en disco con tamano > 0, respuesta de API, entrada en log). Si no hay evidencia, el estado real es NO LOGRADO y se escala. Nunca digas 'listo' basandote en intencion.

## Cuando escalar (cualquiera de estos)

- La tarea requiere herramientas que no tienes (terminal, ffmpeg, codigo).
- Fallaste 2 intentos del mismo enfoque. PROHIBIDO insistir con variaciones del mismo metodo.
- No puedes verificar el resultado con evidencia.

## Como escalar (agente cliente)

Escribe un ticket JSON en `/opt/data/inbox/<tu-perfil>/pending/ticket-<fecha>-<perfil>-<num>.json`:

```json
{
  "id": "ticket-20260909-nancy-001",
  "tarea": "Descripcion clara y autocontenida de lo que se necesita",
  "archivos": ["/opt/data/ruta/al/archivo"],
  "intentos_fallidos": ["que intentaste y por que fallo"],
  "canal_entrega": "/opt/data/profiles/<perfil>/documentos/ o whatsapp:<numero> o bot-chat:<perfil>",
  "estado": "pending"
}
```

Reglas del ticket:
- La tarea debe ser AUTOCONTENIDA: el agente tecnico no ve tu conversacion.
- Los archivos deben estar bajo /opt/data/ y existir.
- Si el usuario espera respuesta por WhatsApp, indica el numero en canal_entrega.
- Despues de escribirlo, informe al usuario: 'He escalado tu solicitud al equipo tecnico'.

## Como ejecutar (agente tecnico / default)

El cron `escalation-watcher` corre cada 2 min (job `4561df77e8b8`, script `escalation_watcher_gate.sh`). Cuando hay tickets, el script los reclama (pending -> processing) e inyecta instrucciones en el prompt. El agente debe:

1. Ejecutar la tarea con las skills del catalogo.
2. Verificar con evidencia real (ls -la, tamano > 0).
3. Mover el ticket a done/ (con campo evidencia) o failed/ (con campo error). Nunca borrar tickets.
4. NO entregar por WhatsApp directamente salvo que canal_entrega lo pida explicitamente.

## Estados del ticket

pending (en pending/) -> processing (reclamado) -> done (con evidencia) | failed (con error)

## Ubicaciones en PROD

- Buzon: /opt/data/inbox/<perfil>/{pending,processing,done,failed}/
- Script watcher (canonico para cron): /opt/data/home/.hermes/scripts/escalation_watcher.py (copia espejo en /opt/data/scripts/)
- Log del watcher: /opt/data/inbox/watcher.log
- Cron: job 'escalation-watcher' en el perfil default (cada 5 min, deliver local)
- Skill de transcripcion asociada: audio-video-transcription

## Gotchas verificados (2026-09-09)

- El cron exige script RELATIVO a ~/.hermes/scripts/ (no rutas absolutas).
- `hermes cron runs` solo registra ejecuciones con stdout (tickets); runs silenciosos no aparecen.
- API whisper NaN: WAV >~2MB da 413 del proxy nginx -> convertir a MP3 antes. Audio sin voz (-91dB) retorna texto vacio (no es bug); diagnosticar con ffmpeg volumedetect.
- Segmentos <2 min retornan texto vacio; >52 min retornan 503. Chunk recomendado: 50 min.
- Claim atomico: shutil.move pending->processing + flock exclusivo evitan doble procesamiento.

## Lecciones operativas (verificadas en produccion)

- **Un ticket en `pending` sin reclamar = el watcher no corre.** Antes de reenviar o duplicar, comprobar `tail /opt/data/inbox/watcher.log`: si no hay ciclos recientes, el problema es el scheduler, no el ticket.
- **El scheduler muere en silencio si `/opt/data/cron/jobs.json` no es legible por uid 10000.** Sintoma: TODOS los jobs `enabled` con `last_run: None` y en el log del gateway `RuntimeError: Failed to read cron database: Permission denied`. Causa tipica: alguien ejecuta `hermes cron`/CLI como root desde el host y reescribe el store con `root:600`. Fix: `chown 10000:10000` + `chmod 600` (con backup previo) y verificar que `last_run` avanza.
- **Prohibido ejecutar la CLI de Hermes como root sobre `/opt/data`.** Usar `docker exec -u 10000 hermes-agent ...` o el perfil correcto. Cualquier archivo `root:root` dentro de `/opt/data` rompe escrituras de hermes (caso real: `secrets/*.json` 600 root dejaba caidas las conexiones Google del perfil).
- **El bridge solo es alcanzable desde dentro del contenedor.** `127.0.0.1:3000` en el host da conexion rechazada; el `-p <ip-tailscale>:3000` publica sin backend util. Para enviar texto o archivo: `docker exec hermes-agent curl -s -X POST http://127.0.0.1:3000/send` (o `/send-media`) con el payload en un JSON dentro de `/opt/data` (`-d @/opt/data/...json`), no por shell quoting inline.
- **Entregar un archivo:** payload `{"chatId":"<lid>@lid","filePath":"/opt/data/ruta","caption":"..."}` a `/send-media`; exige que el archivo exista dentro del contenedor (montar en `/opt/data`). Respuesta valida: `{"success":true,"messageId":"..."}`; no hay acuse de lectura.
- **Un ticket que exige que un humano reciba el resultado debe declarar el canal explicito y verificarse.** Que el agente cierre el ticket no implica que haya enviado el mensaje: comprobar en `agent.log`/`docker logs` una linea `Sending response ... to <chat>` reciente. Si no existe, el informe se quedo en el buzon y hay que relayarlo.
- **El buzon de entrada no notifica solo: hace falta un wake-gate.** Patron probado (`buzon-from-bob`, perfil default en DEV): cron cada 10 min con `script` bash que lista `from-bob/*.json` y las respuestas en `done/ticket-*.json` por SSH, compara contra un archivo de estado y emite `{"wakeAgent": true}` + el contenido solo si hay algo nuevo (`{"wakeAgent": false}` si no, 0 tokens). Reglas del gate: (a) hacer baseline silencioso del historico en la primera corrida, (b) marcar como visto despues de imprimir, (c) tope de mensajes por ciclo, (d) si SSH falla, silencio con log (no quemar tokens por un corte de red), (e) `deliver: local` y toolsets minimos (`terminal`, `file`).