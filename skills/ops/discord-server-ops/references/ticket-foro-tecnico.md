# Plantilla de ticket — foro 🛠️ tickets-tecnicos

Destino: foro `1554957746980261938` (guild `1493354289266167808`). Usar cuando el Admin pide «arma un ticket» para trabajo técnico de la flota.

## Tags del foro

- Tags disponibles: `Implementación` (`1554957746980261940`), `Pendiente` (`1554957746980261942`).
- Si el foro cambia de configuración, resolver los ids reales con `GET /channels/1554957746980261938` → `available_tags`; no asumir los de esta lista.
- Crear el hilo con `applied_tags: ["<id_tag>", ...]` en el payload; un ticket sin tag queda fuera del flujo del foro.

## Esqueleto del mensaje raíz (en este orden)

1. **Responsable:** `<@id>` del humano encargado + quién creó el ticket + prioridad + ámbito.
2. **Objetivo:** una línea con el entregable final.
3. **Contexto:** 2-4 bullets con solo los datos duros necesarios para actuar.
4. **Tareas numeradas** en el orden en que se ejecutan. La tarea 1 suele ser verificar supuestos no confirmados en fuente oficial antes de invertir tiempo.
5. **Deadline interno:** al menos 24 h antes del deadline real (colchón de entrega).
6. **Criterios de aceptación:** numerados y verificables uno a uno — una URL, una salida de comando pegada, una captura. Nunca «quede bien».
7. **Fuera de alcance:** qué NO entra y por qué (evita que el ticket crezca sin control).

## Reglas de publicación

- El mensaje raíz tiene límite de 2000 chars: contar antes de enviar. Si el ticket necesita más, publicar un **segundo mensaje** en el hilo con los insumos ya preparados (drafts de copy, storyboards, datos de referencia) — el ticket queda escaneable y los insumos a un scroll.
- El responsable SIEMPRE se menciona con `<@id>`, no con texto plano: un `@Nombre` escrito a mano no notifica. Verificar en la respuesta de la API que `mentions` contenga el id real.
- Nunca incluir datos de clientes ni cifras sensibles sin registro: si la evidencia menciona a un cliente, quitar la mención hasta que exista registro formal.

## Receta

1. Construir el payload localmente con python (`json.dumps(..., ensure_ascii=False)`) y contar `len(body)` — el mensaje raíz admite máximo 2000 chars.
2. Autenticar con las credenciales del bot de la flota según lo documentado en la sección «Verificar escribilidad del bot» del SKILL.md: el secreto vive solo en el host PROD, no en los `.env` de DEV/contenedor. Ejecutar el POST REST desde ese host; el secreto nunca aparece en salidas de comando ni dentro del payload.
3. POST REST v10: `POST /channels/{foro}/threads` con `{name, message:{content}, applied_tags:[...]}`.
4. Limpiar el payload de `/tmp` del host remoto al terminar.

## Verificación post-creación (obligatoria)

Antes de reportar el enlace al Admin:

1. `GET /channels/{thread_id}` → confirmar `name`, `applied_tags` y `parent_id` correctos.
2. `GET /channels/{thread_id}/messages?limit=10` → confirmar contenido completo y menciones resueltas.
3. Reportar el enlace en formato `https://discord.com/channels/{guild}/{thread_id}`.
