# Brave Leo BYOM con NaN Builders (verificado 2026-08-19)

Leo (IA de Brave) soporta **BYOM — Bring Your Own Model** vía protocolo
OpenAI-compatible. NaN responde sin problema (testeado contra la API real:
auth + `/v1/models` + chat completion con payload estilo Brave = OK).

## Configuración

1. Abrir `brave://settings/leo`
2. Sección **Bring Your Own Model / Custom model** → **Add custom model**
   (el texto del botón varía según versión; el formulario es el mismo).
3. Rellenar, guardar y **seleccionar el modelo como activo**.

| Campo | Valor |
|---|---|
| Label / Model Name | `NaN DeepSeek` (etiqueta libre) |
| Model Request Name | `deepseek-v4-flash` (string exacto del campo `model`) |
| Server Endpoint | `https://api.nan.builders/v1/chat/completions` |
| Context Size | `128000` (Brave lo usa como tope de contexto de página; el modelo es 1M) |
| API Key | la `NAN_API_KEY` |
| Vision Support | OFF (NaN rechaza imágenes en chat → HTTP 400) |
| Tool Support | OFF |
| System Prompt | opcional |

Chat models alternativos: `qwen3.6`, `mimo-v2.5`, `gemma4` (cambiar solo el
Model Request Name).

## Cómo funciona Brave por debajo (confirmado en brave-core / oai_api_client)

- El **Server Endpoint se POSTea verbatim** — URL COMPLETA de chat
  completions, no base. El validador de URL acepta `http://localhost`,
  `http://127.0.0.1` o `https://`.
- Payload que manda Leo: `content` como **LISTA de parts** OpenAI multimodal
  (`[{"type":"text","text":...}]`), `stream:true`,
  `temperature` **hardcodeada a 0.7**, `max_tokens`, y un array `tools` solo
  si Tool Support está ON.
- Con Tool Support ON es anti-roundtrip `role:"tool"` — NaN no lo soporta;
  mantener OFF.
- User-Agent de Brave = Chrome real → pasa Cloudflare de NaN (error 1010
  solo pega con UA no-navegador).
- El System Prompt se manda literal al modelo, sin inyección de contexto.

## Troubleshooting

- "Network error" / Leo no responde: endpoint **sin slash final** y modelo
  **SELECCIONADO como activo** (no solo configurado) — error #1.
- Respuestas de plantilla: API key vacía o slash final.
- Verificar antes desde terminal con curl (con UA de navegador) al endpoint
  completo; ver skill `nan-builders-api` para el bloque de test.
- Temperature fija 0.7; no hay campo para cambiarla, usar otro cliente si
  hace falta.

## AI Browsing (agéntico) — clics y navegación

Leo normal **NO toca páginas** (solo resume la activa / QA). La navegación
agéntica es otra feature: **AI Browsing**, experimental.

Fechas: anunciado 10/12/2025 en Nightly; 05/05/2026 ampliado a todos los
canales de release. Docs piden desktop (Win/macOS/Linux) + Nightly 1.87+;
Leo Premium NO requerido. Android/iOS planeados.

Activar:
1. `brave://flags` → buscar `#brave-ai-chat-agent-profile` → **Brave AI browsing** → Enabled
2. Relaunch
3. Un icono de agente en el input de Leo (sidebar o `brave://leo-ai`) → abre
   **perfil aislado** (cookies/cache/sesiones aparte; NO toca tu perfil normal).

Riesgos documentados por Brave: **prompt injection** (instrucciones en el
contenido web), tareas con login fallidas, comportamiento inestable
(experimental). No usarlo en banca/salud/legal/hacienda.

## System prompt recomendado (asistente de navegación/investigación)

```
You are Leo, Brave's private browsing assistant. Help the user research,
compare, and organize information from the web. Always reply in the user's
language. Be concise (under 120 words unless asked for detail). When
navigating, prioritize: understand the task, plan steps, verify the source
is real and keep the date, and organize results in tables when there are
comparisons. Say clearly where each attributable fact came from. Never
invent prices, dates, or facts. Use browser tools only when the user
authorizes. Always back claims with a citation block.
```

(Para usuarios hispanos se entrega en español directo en el chat; aquí se
documenta el bloque para copiar.)