---
name: embedded-payload-extraction
description: "Use when meta or OG is truncated; pull hydration JSON"
tags: [hydration, payload, json, og, spa, extraccion, longform, x-twitter]
---

# Embedded Payload Extraction

Getting the **real** content out of a modern page when the visible metadata gives you only a summary.

## Trigger

Any of these:

- `og:description` / `<title>` / a public API return a short or truncated version of the content ("…", "Would you read…") and you know the real body is longer.
- The post/page is a **hook** pointing elsewhere: "prompt below👇", "thread 🧵", "link in reply", "details in the reply".
- The page is a SPA: HTML full of embedded JSON, `<div id="app">`, and the useful text never appears in the rendered markup you fetched.
- You need a payload that the vendor's own API does not expose (e.g. replies/threads).

## Signal ladder — try in this order

1. **Alternate text endpoints** first — `rel="alternate" type="text/markdown"`, `.md`, `.json`, `.txt` in `<head>`. Cheapest and cleanest when they exist.
2. **Public JSON APIs** (e.g. `api.fxtwitter.com/<user>/status/<id>`) — give structured metadata, but often only for the *root* object. Assume they are incomplete for threads, replies, and long-form bodies.
3. **Hydration state in the HTML** — the fallback that almost always has the full text. This is what this skill is for.

Always fetch with a real Chrome User-Agent. Python/urllib default UAs get 403s on Cloudflare-fronted hosts.

## Core technique — anchor + window

Do not try to parse the whole document. Find a **distinctive phrase** that you already know appears in the truncated version, then print a wide window around it:

```python
h = open('/tmp/page.html', encoding='utf-8', errors='ignore').read()
k = 'First reuse what you already know'      # any fragment from the truncated OG text
BS = chr(92)
seg = (h[h.find(k)-1000 : h.find(k)+8000]
       .replace(BS + 'n', chr(10))
       .replace(BS + '"', '"'))
print(seg)
```

This survives unknown wrapper syntax: you are reading the raw escaped JSON, not a parsed object. If the print is cut off, advance the offset (`seg[3400:]`) instead of re-fetching.

Escaping note: in Python source, always build a backslash with `chr(92)` (or `BS = chr(92)`) rather than nested literal backslashes — it removes a whole class of quoting bugs when writing this from inside a tool call.

## Escaped-JSON walker (when you need the exact string)

Anchor on the **record type**, never on a generic key:

```python
import re, html
BS = chr(92)
h = open('/tmp/page.html', encoding='utf-8', errors='ignore').read()
for m in re.finditer(re.escape('__typename:"NoteTweet",text:"'), h):
    j, buf = m.end(), []
    while j < len(h):
        c = h[j]
        if c == BS:
            buf.append(h[j+1]); j += 2; continue
        if c == '"':
            break
        buf.append(c); j += 1
    print(html.unescape(''.join(buf)))
```

Generic form: locate the key that introduces the object you want (`data-page=`, `self.__next_f.push`, `dehydratedData`, `note_tweet_results`, …), then walk to the closing unescaped quote.

## Verified case — X/Twitter long note in the author's self-reply

- Root tweet text was a hook ("… # Give below prompt to your Hermes agent👇"); the real payload (~5.5K chars) was the author's own reply, published as a long-form **note**.
- `api.fxtwitter.com/<user>/status/<id>` returned **only the root tweet** — no thread, no replies.
- `og:description` from the fixupx render truncated at ~276 chars.
- The full note **was** in the fixupx HTML (`dehydratedData` → `note_tweet_results` → `NoteTweet` → `text:`).

Full recipe, escape walker, and the reusable script:
- `references/longform-note-reply-extraction.md`
- `scripts/extract_longform_note.py` — prints root tweet + every embedded note as JSON.

## Pitfalls

- **Short anchors lie.** Searching for `text:"` also matches the root object's `full_text:"` and hands you the 279-char hook, making it look like the long content is missing. Anchor on the full record type (`__typename:"NoteTweet",text:"`) or a phrase unique to the long body.
- **Do not normalise the payload while extracting.** Read it verbatim; only unescape, never re-wrap or "fix" line breaks.
- **Escaped vs unescaped double quotes.** A naive `re.search(r'text:"(.*?)"')` stops at the first inner quote and silently truncates. Walk the string char by char.
- **Re-fetching to "get more" wastes a round trip.** The whole payload is already in the file you saved; page through the window.
- **API completeness assumptions.** A vendor API returning one object does not mean that object is the whole conversation. Threads, replies, quoted posts and long-form bodies are usually separate records.
- **Environment claims age.** If a skill or note claims a tool (e.g. `curl`) is unavailable, verify it in the live environment before designing around the absence — the constraint may be stale.

## Reporting consequence

Summarise the **payload**, not the hook. When a post is a hook plus a long reply, the summary, key takeaway, stack and recommended action must all come from the reply body — closing a report on the hook alone is a failed extraction.


<!-- absorbido de productivity/web-content-extraction (censo 2026-09-24) -->
## Técnica principal: alternate markdown/plain-text endpoints (confirmado 08/2026)


Muchos sitios de documentación sirven una versión **markdown plana** de cada artículo aunque la app sea JS-heavy. Lo anuncia el `<head>`:

```html
<link rel="alternate" type="text/markdown" href="https://<host>/help/cli.md">
```

1. Fetch del HTML y buscar en `<head>`:
   `rel="alternate" type="text/markdown"` (o `.json` / `.txt`)
2. Fetch de la URL del href (`...md`) en vez del HTML completo.

Caso real Bitwarden Help: `/help/cli/` = 1.4MB de HTML (app Inertia, JSON embebido); `/help/cli.md` = ~40KB de markdown limpio y completo (incluye código, tablas, notas). Sin Inertia, sin banners, sin scripts.

## UA header obligatorio


Usar siempre UA de Chrome real — muchos sitios (Bitwarden, r.jina.ai da 403 con el default) vetam el UA de urllib por defecto:

```python
headers = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  "Accept": "text/markdown,text/plain;q=0.9,text/html;q=0.8",
  "Accept-Language": "en-US,en;q=0.5",
}
```

## Script mínimo (urllib, sin curl)


```python
import urllib.request
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "Accept": "text/markdown,text/plain;q=0.9"})
with urllib.request.urlopen(req, timeout=30) as r:
    data = r.read().decode("utf-8", errors="ignore")
```

Pitfalls:
- **curl NO está instalado** en este VPS — usar urllib.
- Si hay `decompress`/data zlib, urllib lo maneja solo (Content-Encoding gzip lo descomprime automáticamente).
- Páginas con 403 (r.jina.ai) — probar extraer el `.md` directo del sitio antes de pedir readers externos.

## Cadena de fallback completa

1. `web_extract` (Firecrawl) → 2. browser tool → 3. urllib directo (UA Chrome) con búsqueda de alternate markdown → 4. agent-reach/obscura si están instalados → 5. reportar al usuario.

## Referencias

- `references/bitwarden-cli-case.md` — caso completo Bitwarden Help: síntoma, extracción del .md, resultado.