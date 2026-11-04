---
name: ua-spoofing-eval
description: "Use when a URL fetch is blocked (403/WAF/captcha)."
tags: [user-agent, spoofing, scraping, waf, cloudflare, fetch, curl]
---

# UA-Spoofing Eval & Robust Fetch

Implementación del hallazgo del tweet @doodlestein (UA de IA de confianza en AGENTS.md)
validado con experimento A/B controlado. Evidencia: Wikipedia bloquea curl UA por defecto
(403) y admite todos los spoofed (200); X bloquea UAs tipo bot (402) pero deja pasar
openai/chrome/whatsapp.

## Cuándo usar
- `robust_fetch` bloqueo 403/402/captcha/WAF al leer una URL (caso por defecto de scraping).
- Validar empíricamente si UA-spoofing sirve para un sitio/dominio nuevo.
- Reimaginar la cadena web de Ragnar (ver skill `browser-backend-replacement`).

## Archivos

| Archivo | Rol |
|---|---|
| `/opt/data/tools/robust_fetch.py` | Helper HTTP (curl TLS nativo + UA rotativos + detección de bloqueo). Import python o CLI. |
| `/opt/data/scripts/eval_ua_spoofing.py` | Harness reproducible A/B para medir bloqueos por UA sobre un set de sitios. |

## Uso

```bash
# Leer una URL con rotación (prueba openai, luego chrome):
python3 /opt/data/tools/robust_fetch.py "https://example.com" --full

# Forzar un UA concreto:
python3 /opt/data/tools/robust_fetch.py "https://example.com" --ua openai

# Entradas de lib python:
from robust_fetch import robust_fetch
res = robust_fetch("https://example.com")   # dict: status, body, html_len, blocked, ms, ua

# Evaluar bloqueos por UA sobre varios sitios (harness):
python3 /opt/data/scripts/eval_ua_spoofing.py --sites wikipedia,linkedin,x_user,github,bbc
python3 /opt/data/scripts/eval_ua_spoofing.py --sites x_user --ua openai --rounds 3
```

## Candidatos User-Agent (CANDIDATE_UAS)

| Clave | Valor | Nota |
|---|---|---|
| control_default | (vacío) | baseline bot; Wikipedia lo bloquea (403) |
| spoof_openai | `OpenAI File Downloader, XaiImageApiFetch/1.0` | **el más fiable** — pasa Wikipedia y X |
| spoof_claude | `Claude-User` | pasa la mayoría; da 402 en X |
| spoof_gptbot | `GPTBot/1.0` | igual que claude: 402 en X |
| spoof_whatsapp | `WhatsApp/2.25.1.1` | truco de Signal; pasa X |
| browser_chrome / browser_safari | navegador real | pasa todo; last resort |

## Proceso para sitio nuevo

1. Correr harness con todos los UAs: `python3 /opt/data/scripts/eval_ua_spoofing.py --sites <nuevo_sitio>`
2. Ver qué ok-rate consigue cada UA; anotar el candidato ganador.
3. Forzar ese UA en llamadas futuras al sitio vía `--ua <nombre>`.
4. IMPORTANTE aislar la variable TLS: si falla todo, probar con curl nativo (el harness ya usa curl) vs urllib = blockeo por fingerprint TLS/IP, no por UA.

## Pitfalls

- `--tls-grease` **NO existe** en el curl del VPS (version antigua) — no pasarlo o muere.
- La detección de bloqueo solo se activa para status >=400 o body <200 bytes: un 200 con texto "blocked" (p.ej. wikipedia) NO es bloqueo, es contenido real.
- En X (x.com) los UAs de bot (gptbot/claude) devuelven 402 — usar openai/chrome/whatsapp.
- urllib ok: el stack TLS de Python se fingerprintea y bloquea casi todo AUNQUE lleve UA correcto; por eso robust_fetch delega en curl.

## Related
- `browser-backend-replacement` — cadena web por defecto de Ragnar (actualizada a robust_fetch).
- `agent-reach` — routing multi-plataforma (Jina Reader upstream).