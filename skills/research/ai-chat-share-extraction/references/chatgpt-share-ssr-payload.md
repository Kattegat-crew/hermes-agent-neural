# Payload SSR de un share de ChatGPT — formato y marcadores

## Marcador exacto (comprobado 11/09/2026)

```html
<script nonce="...">window.__reactRouterContext.streamController.enqueue("[{\"_1\":2,\"_3\":-5,\"_4\":-5},\"loaderData\",{\"_5\":6,\"_7\":8},\"actionData\",\"errors\",\"root\",{...}"]);</script>
```

- Es el `single-fetch` de **React Router v7**: `arr[0]` = root, con claves `loaderData`,
  `actionData`, `errors`. **No** es Next.js RSC (`self.__next_f` no existe en esta página:
  buscarlo da 0 y lleva a concluir por error que el HTML viene vacío).
- Búsquedas que SÍ funcionan sobre el HTML crudo: `streamController.enqueue`,
  `linear_conversation`, `sharedConversationId`, `continue_conversation_url`.
- Búsquedas que dan 0 porque el JSON va escapado dentro del string JS: `"parts"`,
  `"author"`, `"mapping"`, `"create_time"`. Hay que des-escapar primero (paso 3 del SKILL).

## Estructura (tras decodificar el flatten)

```
arr[0] (root)
└── loaderData
    └── routes/share.$shareId.($action)
        ├── sharedConversationId  -> "<uuid del share>"
        ├── moderationMode / meta
        └── serverResponse.data
            ├── title            -> "<nombre real del hilo>"
            ├── create_time      -> epoch
            └── linear_conversation: [ {message: {id, author.role, content.content_type, content.parts[]}}, ... ]
```

`content.parts[]`: strings (texto) o dicts (referencia a imagen/asset).
`content_type` observados: `text`, `multimodal_text`, `code`, `thoughts`,
`reasoning_recap`, `execution_output`, `model_editable_context`.

## Números del caso trabajado (share `6aa3d64f-c388-83e9-b053-0f4f92859a09`)

- HTML: 1.049.385 bytes · payload: 6.987 elementos · 526 KB de string escapado.
- Título: «Rama: Compartir imágenes de contexto».
- 251 nodos → **36 user + 89 assistant + 109 tool + 16 system**; ~131.000 chars de texto.
- Tras filtrar ruido y redactados quedaron **54 mensajes con texto** (67 KB de markdown).
- Contenido útil recuperado: guion cinematográfico para Seedance de un reel de casino,
  el prompt del "personaje maestro" de referencia y ~10 prompts de edición de imágenes
  escena por escena con sus correcciones. Los nodos `tool` (los renders) venían redactados.

## Qué NO se recupera

- Salidas de plugins/tools: `The output of this plugin was redacted` (texto literal).
- Imágenes: punteros `file-service://file-…` / `sediment://…` → requieren sesión.
  Público: `https://ogimg.chatgpt.com/conversation/<share-id>/igc.png` (thumbnail 1200x630).
- Adjuntos de sandbox: `sandbox:/mnt/data/...` (solo el nombre del archivo).
