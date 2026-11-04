#!/usr/bin/env python3
"""Helper de búsqueda web limpia para Ragnar con User-Agent y fallback de parsing."""
import json
import re
import sys
import urllib.parse
import urllib.request
from html import unescape

def search_ddg(query, max_results=5):
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
    }
    req = urllib.request.Request(url, headers=headers)
    results = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            # Parse DDG result snippets
            blocks = re.findall(r'<a class="result__url" href="([^"]+)".*?<a class="result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
            if not blocks:
                # Alternative regex for DDG html
                links = re.findall(r'href="//duckduckgo\.com/l/\?uddg=([^"&]+)"', html)
                titles = re.findall(r'<a class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
                snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
                for i in range(min(len(links), len(titles), len(snippets), max_results)):
                    link = urllib.parse.unquote(links[i])
                    title = re.sub(r'<[^>]+>', '', titles[i]).strip()
                    snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()
                    results.append({"title": unescape(title), "url": link, "snippet": unescape(snippet)})
            else:
                for url_match, snippet_match in blocks[:max_results]:
                    results.append({
                        "url": urllib.parse.unquote(url_match),
                        "snippet": unescape(re.sub(r'<[^>]+>', '', snippet_match).strip())
                    })
    except Exception as e:
        print(f"Error en búsqueda: {e}", file=sys.stderr)
    return results

if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Pico y placa Bogota hoy"
    res = search_ddg(q)
    print(json.dumps(res, ensure_ascii=False, indent=2))
