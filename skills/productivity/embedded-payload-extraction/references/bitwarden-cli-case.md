# Caso Bitwarden Help (`/help/cli/`) — 2026-08-19

## Síntoma
- `web_extract` → `"Web tools are not configured. Set FIRECRAWL_API_KEY..."`
- `browser_navigate` → timeout tras 120s (página ~1.1-1.4MB, app Inertia)
- `agent-reach` → `command not found` (CLI ausente en este VPS)
- `r.jina.ai/URL` → HTTP 403

## Solución que funcionó
1. Fetch directo del HTML con urllib + UA Chrome → 1,143,134 bytes (1.1MB) de app Inertia, con el contenido útil embebido en `<div id="app" data-page="{...}">` como JSON escapado.
2. TIERRA: en el `<head>` del HTML hay:
   `<link rel="alternate" type="text/markdown" href="https://bitwarden.com/help/cli.md" inertia>`
3. Fetch de `https://bitwarden.com/help/cli.md` con UA Chrome + `Accept: text/markdown` → **~40,575 bytes de markdown limpio** (40.5KB), texto completo del artículo: instalación, login, comandos core, organizaciones, ejemplos con código y tablas.

## Lecciones
- Escanear SIEMPRE `<link rel="alternate" type="text/markdown|text/plain|application/json">` antes de scrapear el HTML completo de una SPA de documentación.
- El patrón `google.com/help/xxx.md` es común en sitios Inertia-based (Bitwarden lo usa). También probar `<url>.md` directamente.
- urllib descomprime gzip/br automáticamente vía headers estándar; no hace falta manejo manual.
- UA default de urllib (Python-urllib/x) es vetado por Bitwarden y Jina → siempre UA Chrome real.