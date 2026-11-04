---
name: entregables-de-campana-versionado
description: "Use when a client datum arrives after delivery."
tags: [campanas, entregables, versionado, cliente, ledger, audio, docx]
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
metadata:
  hermes:
    tags: [campaña, entregable, versionado, cliente, insumo, ledger, contenido]
    category: creative
    related_skills: [cunas-de-audio-campana, voice-message-transcription, pending-task-ledger, guiones-campana-por-canal]
---

# Entregables de campaña versionados (cuando el insumo llega después)

## Trigger

- Llega una **nota de voz o un mensaje del cliente** con el dato que faltaba para un entregable ya redactado (guion, cuña, pieza, guía).
- El Admin **corrige sede, alcance o mecánica** después de que el entregable se entregó.
- El pedido es del tipo *"agregando esta información"* / *"con esto que me mandó el cliente"*.
- El cliente entrega **el material audiovisual que faltaba** (reel, video, imagen) por Drive cuando las piezas del calendario ya existen.

## Regla de oro: versionar, no rehacer

Un dato nuevo **no** reabre el trabajo desde cero. Se emite la siguiente versión del MISMO documento
(`v3`, `v4`…), con un encabezado que diga **qué cambió y qué pendiente cerró**, y las fichas anteriores
se conservan legibles (si el dato se cae después, no hay que reconstruir nada).

Caso real: el 14/09/2026 el cliente mandó por audio la dirección que bloqueaba el guion de perifoneo de
Chiquinquirá → `v3` incorporó dirección + `v4` añadió el set nuevo, sin tocar el resto del documento. El
costo de no hacerlo así ya se había pagado el 10/09: una corrección de sede hizo rehacer el guion completo.

## El insumo suele llegar en nota de voz

1. Transcribir con la skill `voice-message-transcription` (no pedirle al Admin que lo escriba).
2. Extraer **solo datos duros**, no volcar la transcripción al chat:
   - dirección o ubicación (y sus referencias: "al lado de la Alcaldía", "al lado de El Éxito");
   - **nombres propios** de producto/estreno tal como los dijo el cliente;
   - números que **describen** el producto ("de ocho puestos") — los montos y probabilidades siguen prohibidos si no están verificados;
   - **el verbo revela el estado**: "llevamos / ya tenemos" ⇒ instalado; "le van a instalar" ⇒ todavía no.
3. **Dato dudoso del dictado** (un nombre propio, una cifra que solo existe en el audio): se incluye y se pide la confirmación **en la misma respuesta** donde se entrega la versión nueva. No se omite en silencio ni se bloquea el trabajo por eso.

## Cuando el insumo es MATERIAL AUDIOVISUAL (video que entrega el cliente)

El mismo principio (versionar, no rehacer) aplica cuando el cliente manda el material por Drive después de que las filas del calendario ya existen. Antes de agendar publicación:

1. **Descargar y medir con `ffprobe`** (resolución, duración): no confiar en el nombre del archivo.
2. **Transcribir el audio y revisar frames** (inicio/medio/cierre) con visión: marcas de agua de apps (MixCam, CapCut), pantallas divididas y demás recursos PROHIBIDOS por el cliente, y el texto de los pósters finales.
3. **Cruzar el texto en pantalla contra el candado T&C vigente**: lo que el póster diga y el T&C prohíba (p. ej. "Reserva tu cartón" vs "no existen reservas") NO entra al copy; se anota la discrepancia para el cliente. El material NO se edita sin autorización expresa.
4. **Cablear al calendario** (fila nueva o existente → `listo_para_aprobacion`, copy propuesto con candado, portada) y reportar en UN mensaje: qué es cada pieza (medido), copy completo, discrepancias sin tocar el video, y ventana de aprobación explícita (slot+2h, sin catch-up).

## Cierre en tres capas (no solo el documento)

| Capa | Ruta | Qué se escribe |
|---|---|---|
| Documento de trabajo | la que fije la skill del entregable (p. ej. `/opt/data/plans/GUION-<SEDE>-…md`) | versión nueva, encabezado con el cambio, ficha de datos y pendientes actualizados |
| Skill + `references/` | skill que gobierna ese tipo de entregable | el caso: datos verificados, decisiones y correcciones |
| Ledger de pendientes | `/opt/data/brain/tasks/` | estado del pendiente — **siempre con el CLI**, nunca editando a mano |

En el ledger: `python3 /opt/data/scripts/pending_tasks.py` (`state`, `close --evidencia`, `sync`,
`verify`). El detalle fino de avance vive en el documento, no en el ledger.

## Reporte al Admin

- Entregar en el chat **el set actualizado completo** (las locuciones/piezas que cambian), no una descripción del cambio.
- Decir en 2-3 líneas qué decisión tomaste por él (dosis, repetición de datos duros, qué nombre propio entró) y por qué.
- Cerrar con **UNA sola pregunta de producción** (voz, formato, quién aprueba) y ofrecer el siguiente artefacto (DOCX con membrete para el cliente). No re-listar todo lo pendiente: se repite el archivo y se pide el OK.

## Pitfalls

- **No editar a mano el ledger de pendientes** (ni el `.jsonl` ni el `pending.md`), aunque sea solo la `nota`: el md lleva el sha del store y cualquier escritura directa deja `verify` en exit 2. Reparación: `pending_tasks.py sync` y luego `verify` hasta exit 0.
- **No reenviar el mismo set como si fuera nuevo** cuando el Admin pide el mismo entregable un minuto después: confirmar qué está ya entregado y responder con la versión que cambió (o con la pregunta de producción pendiente).
- **El material aprobado manda sobre la ficha del brain**: si un afiche/banner vigente contradice la ficha del cliente, se anota la discrepancia y no se descarta la sede ni el dato por la ficha.
- **No prometer el entregable final sin la firma humana**: la versión nueva queda como borrador versionado hasta el OK explícito del Admin.
- Las skills que gobiernan estos entregables pueden ser **user-owned** (mis patches se rechazan): si hay que corregirlas, `hermes curator adopt <nombre>`.

## Referencias

- `references/chiquinquira-perifoneo-v3-v4-2026-09.md` — el caso completo: audio del cliente → `v3` (dirección) → `v4` (set monográfico), decisiones sobre el nombre propio y el error/reparación del ledger.
