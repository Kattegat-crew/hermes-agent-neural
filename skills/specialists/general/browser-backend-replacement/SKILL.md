---
name: browser-backend-replacement
description: "Use when navigating, reading or scraping any web page."
tags: [web, browser, navegacion, scraping, agent-reach, obscura, fetch, fallback]
---

# Browser Backend Replacement for Hermes

Evaluate and deploy alternative headless browsers to replace or supplement Camofox/agent-browser in Hermes.

## When to Use

- Navegar, leer o scrapear cualquier página web (tarea por defecto: usar esta cadena)
- Browser tool failing ("Cannot connect to browser", timeouts)
- Necesitar scraping/extracción de contenido multi-plataforma

## Architecture Overview

Cadena de navegación por defecto (2026-07-31, Camofox eliminado):

1. **Agent-Reach** — CLI multi-plataforma (web/Jina Reader, YouTube, Bilibili, V2EX, RSS, GitHub). Instalado en `/usr/local/bin/agent-reach`, skill: `agent-reach`.
2. **Obscura** — navegador headless Rust (`/opt/data/obscura-bin/obscura fetch|scrape|serve`)
3. **web-exploration** — curl/python fallback (nota: curl NO está instalado, usar python urllib)

El browser tool interactivo de Hermes (snapshot/click/type) usa `agent-browser` CLI local (no hay backend camofox).

## Evaluation Checklist

When evaluating a new browser backend:

1. **Protocol compatibility** — Does it expose CDP (Chrome DevTools Protocol)?
2. **API surface** — Can it do: snapshot, click, type, navigate, console?
3. **Stealth capabilities** — Anti-detection, fingerprint spoofing?
4. **Resource usage** — Memory, CPU, startup time?
5. **Installation** — Binary size, dependencies, platform support?

## Obscura Integration

Obscura is a Rust headless browser that exposes CDP on port 9222.

### CLI Usage (Recommended)
```
# Fetch page content directly
obscura fetch <URL> --eval "document.title"
obscura fetch <URL> --dump html
obscura fetch <URL> --selector ".main-content"

# Start CDP server
obscura serve --port 9222 --stealth
```

### Important Notes

- **Hermes browser tool is NOT directly compatible** with Obscura as a CDP backend
- The Hermes browser tool is hardcodeado for Camofox or Browserbase
- Use Obscura as a **complementary CLI tool**, not as a browser backend replacement
- For CDP server mode: `obscura serve --port 9222 --stealth` (may need to adjust port if 9222 is in use)

### Fallback Chain for Browser Tasks

Cuando necesites navegar/leer una página, sigue este orden SIEMPRE:

1. **Agent-Reach** (`agent-reach` CLI + skill agent-reach) — web/Jina Reader para páginas generales, canales específicos por plataforma
2. **robust_fetch** (`/opt/data/tools/robust_fetch.py`, script CLI o import python) — HTTP layer con TLS de navegador (curl nativo) + User-Agent rotativos de IA de confianza. **PRIMARIO para lecturas brutas de URL** cuando Jina falla o vuelve bloqueado. Uso: `python3 /opt/data/tools/robust_fetch.py "https://URL" --full`. Reproduce el fixing del UA-spoofing (Wikipedia 403->200).
3. **Obscura CLI** (`obscura fetch <URL> --dump text|html|links`) — para páginas con JS que ni Jina ni curl lean
4. **x-tweet-scrape** — para X/Twitter links via fxtwitter (los UAs de tipo bot generan 402 en X; preferir openai/chrome/whatsapp si se fuerza curl en x.com)
5. **Report failure** al usuario con lo intentado

### Estado canales Agent-Reach (2026-08-02)

- `exa_search`: **ACTIVO** — mcporter v0.12.4 (npm global, `~/.npm-global/bin`) + servidor `exa` en `/opt/hermes/config/mcporter.json` (stdio `npx -y exa-mcp-server`) con EXA_API_KEY real en `/opt/data/.env`. Uso: `mcporter call exa.web_search_exa query="..." numResults=N` (también `web_fetch_exa`). Probado 02/08/2026 OK.
- `twitter`: NO configurado (decidido 02/08) — usar skill `x-tweet-scrape` para extraer tuits.
- `reddit`/`facebook`/`instagram`/`xiaohongshu` (off): requieren OpenCLI (sesión Chrome) o CLIs específicos con login

### Notas instalación

- npm global usa prefix `~/.npm-global` (no `/usr/local`, sin sudo). PATH ya lo incluye.
- **curl SÍ está instalado y es el HTTP layer preferido** via `robust_fetch.py`. Para descargas binarias grandes también sirve `urllib.request.urlretrieve()`.

### Installation Notes

- Binary is ~80MB, no sudo needed for basic usage
- Use `nohup` for background processes (systemd may not work without sudo)
- Download from GitHub releases: `obscura-x86_64-linux.tar.gz`
- Python fallback for download: `urllib.request.urlretrieve()`

## Pitfalls

- **DON'T** try to configure Obscura as a Hermes browser backend — it won't work without Hermes code changes
- **DON'T** assume CDP port 9222 is free — Camofox may use it
- **DON'T** retry a hanging CDP connection 10+ times — use loop-detection skill
- **DO** test Obscura with simple pages first (example.com) before complex sites
- **DO** use `obscura fetch` for content extraction, not for interactive browsing

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Obscura binary not found | Check `/opt/data/obscura-bin/obscura` |
| CDP server not responding | Try `obscura fetch` CLI instead |
| Port 9222 already in use | Use `--port 9223` or different port |
| Page loads but JS fails | Some sites need full browser (Obscura/Camofox) |
| No sudo for system services | Use `nohup` or process manager |
| curl blocked on a site | Retry via `robust_fetch.py` (curl TLS nativo + UA rotativo) antes de bajar a urllib |
| X/Twitter returns 402 | Usar UA `spoof_openai`/`browser_chrome`/`spoof_whatsapp` (los de tipo bot dan 402) |
