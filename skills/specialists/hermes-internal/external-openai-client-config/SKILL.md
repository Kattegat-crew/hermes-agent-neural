---
name: external-openai-client-config
description: "Use when adding an OpenAI-compatible provider to a client."
tags: [openai-compatible, brave, leo, byom, endpoint, provider, api]
---

# Configurar provider OpenAI-compatible en clientes AI externos

Cubre cómo aparcir un endpoint OpenAI-compatible (típicamente NaN Builders u
otro provider custom) en un asistente AI que no es Hermes — Brave Leo (BYOM),
etc. NO confundir con `provider-manager` (ese gestiona providers en el
`config.yaml` de Hermes).

## Regla de oro del endpoint

El cliente externo **POSTea la URL exacta que le des, verbatim** — no le
añade `/v1`, no reescribe paths. Por eso el campo *Server Endpoint* debe ser
la URL **COMPLETA** del chat completions:

```
https://api.nan.builders/v1/chat/completions
```

no solo `https://api.nan.builders/v1`. Dejar slash final suele romper.

## Brave Leo BYOM — pasos

1. `brave://settings/leo` → **Bring Your Own Model / Custom model** → **Add custom model**
2. Rellenar la tabla de campos (ver `references/brave-leo-byom.md` — incluye
   la config exacta para NaN + el System Prompt de navegación).
3. Guardar y **seleccionar el modelo como ACTIVO** (solo configurado = no funciona).

Campos comunes (varía el label, no la semántica):
`Label`, `Model Request Name` (= string `model`), `Server Endpoint`,
`Context Size`, `API Key`, `Vision Support`, `Tool Support`, `System Prompt`.

## Comportamiento de Brave por debajo (confirmado en brave-core)

- Manda `content` como **LISTA de parts** OpenAI multimodal
  (`[{"type":"text","text":...}]`), `stream:true`, `max_tokens`.
- **`temperature` hardcodeada a 0.7** — sin campo para cambiarla.
- User-Agent real de Chrome → pasa Cloudflare/UA-gated APIs (el error
  "403 code 1010" solo pega con UA no-navegador).
- Con Tool Support ON inyecta un array `tools` y espera roundtrip
  `role:"tool"` — providers sin tool-calling (como NaN) pueden fallar;
  mantener OFF.

## AI Browsing (agéntico) — SI el usuario quiere clics/navegación

El Leo normal **NO toca páginas** (solo resume la activa). La navegación
agéntica es otra feature experimental: **AI Browsing**.
- Activar: `brave://flags` → `#brave-ai-chat-agent-profile` → Enabled → Relaunch.
- Corre en **perfil aislado** (no toca cookies/sesiones reales).
- Riesgos documentados por Brave: prompt injection, tareas con login fallidas.
- Detalle y fechas de release en `references/brave-leo-byom.md`.

## Troubleshooting

- "Network error": endpoint sin slash final + modelo **seleccionado activo**.
- Respuestas de plantilla: API key vacía o slash final.
- Verificar el endpoint antes desde terminal con curl (ver skill `nan-builders-api`).

<!-- absorbido de specialists/hermes-internal/vscode-ai-extension-configuration (censo 2026-09-24) -->
## Trigger

When configuring VSCode AI extensions (OpenCode, Continue, Copilot, etc.) or when the user wants an AI chat interface in the VSCode sidebar.

## Approach

1. **Check Extension Capabilities**: Some extensions (like the official `opencode` VSCode extension) lack a UI for model/provider switching. They often only expose a `tab` key to cycle between "plan" and "build" modes.
2. **Recommend Alternative**: If the extension lacks model configuration UI, recommend **Continue.dev** (`Continue - AI paired developer`). It is open-source, free, and natively supports OpenAI-compatible APIs via a simple JSON config.
3. **Configure Continue**:
   - **Preferred method**: Use the Continue UI. Click the **"API Key"** tab (key icon 🔑) for cloud APIs — NOT the "Local" tab (which is for Ollama only). Click "+ Add Chat model", select provider "OpenAI" (works for any OpenAI-compatible API like NaN, LiteLLM, etc.), enter model ID, API key, and **Base URL** (may require clicking "Click here to view the full list" to reveal custom provider options).
   - **Alternative method**: Open VSCode Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) → `Continue: Open Config`. Edit `config.json` (NOT `config.ts`) to add an `openai` provider block pointing to the custom API.
   - Structure:
     ```json
     {
       "models": [
         {
           "title": "Custom Model Name",
           "provider": "openai",
           "model": "model-id",
           "apiKey": "your-api-key",
           "apiBase": "https://api.provider.com/v1"
         }
       ]
     }
     ```
   - Save (`Ctrl+S`). **Reload VSCode** (`Ctrl+Shift+P` → "Reload Window") — changes are not always detected live.
   - Check the "Select model" dropdown in the Continue sidebar.

## Pitfalls & Notes

- **OpenCode Extension Limitation**: Does not support changing models via UI. Only `tab` cycles modes. CLI config (`opencode.json`) applies to terminal usage, not the extension.
- **Continue Config**: Requires `apiBase` for any non-OpenAI API. Ensure trailing `/v1` is included if the provider uses it.
- **Provider Type**: Always use `"provider": "openai"` for OpenAI-compatible endpoints (NaN, LiteLLM, local Ollama, etc.).
- **Use `config.json`, NOT `config.ts`**: TypeScript config (`config.ts`) requires compilation and can fail silently. `config.json` is the reliable fallback.
- **Auto-regenerated files**: If `config.ts` or `config.yaml` are auto-regenerated by the extension, do NOT delete them — they may be intentionally managed by Continue. Focus on `config.json` or the UI instead.
- **UI Tab matters**: The "Local" tab is for Ollama only. For cloud APIs (NaN, LiteLLM, etc.), use the **"API Key"** tab.
- **Base URL hidden**: In the "+ Add Chat model" UI, the "Base URL" field may be hidden. Click "Click here to view the full list" to reveal custom provider options.
- **Reload required**: After editing config files, always reload VSCode (`Ctrl+Shift+P` → "Reload Window") — changes are not always detected live.
- **Conflicting files**: Having both `config.ts` and `config.json` can cause conflicts. Prefer `config.json` or use the UI exclusively.

## Verification

- Check sidebar dropdown for new model name.
- Send a test message. Look for successful response without "model not allowed" errors.