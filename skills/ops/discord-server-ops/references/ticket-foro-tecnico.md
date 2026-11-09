# Plantilla de ticket — foro 🛠️ tickets-tecnicos

Destino: foro `1554957746980261938` (guild `1493354289266167808`). Usar cuando el Admin pide «arma un ticket» para trabajo técnico de la flota.

## Tags del foro

El foro usa 12 etiquetas en tres ejes. Resolver los ids SIEMPRE en vivo (`GET /channels/1554957746980261938` → `available_tags`); los de abajo son referencia al 09-nov-2026:

- **Responsable:** `Chucho` (1555025478450946119), `Jonathan` (1555025462684819496)
- **Tipo:** `Mantenimiento` (1554957746980261939), `Implementación` (1554957746980261940), `Incidente` (1554957746980261941)
- **Estado:** `Pendiente` (1554957746980261942), `En curso` (1554957746980261943), `En revisión` (1554957746980261944), `Cerrado` (1554957746980261945), `Bloqueado` (1554957746980261946)
- **Entorno:** `DEV` (1554957746980261947), `PROD` (1554957747005685860)

Obligatorio: **tipo + estado + etiqueta del responsable**. Entorno solo cuando el trabajo toca una máquina concreta. Un ticket sin tag de responsable o sin mención real contraviene el topic del foro.

## Vía única: scripts/crear_ticket.py

```bash
python3 /opt/hermes-agent/skills/ops/discord-server-ops/scripts/crear_ticket.py \
  --titulo "TKT — ..." --responsable <id_numerico> \
  --tipo Implementacion --estado Pendiente [--entorno DEV] \
  --cuerpo /tmp/ticket.md [--dry-run]
```

Valida antes de postear: tipo/estado válidos, mención `<@id>` presente en el cuerpo, secciones `Objetivo` / `Criterios de aceptación` / `Fuera de alcance`, cuerpo ≤ 2000 chars. Mapea username→etiqueta con `ALIAS_RESPONSABLE` (`jemadiar`→Chucho, `killer420w`→Jonathan): si entra un responsable nuevo, agregar el alias ahí. Tras el POST relee el hilo y falla con exit 1 si `applied_tags` o `mentions` no cuadran.

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
