---
name: web-fetch
description: "Use when a fetch needs headers, timeouts or retries."
tags: [http, scraping, curl, httpx, fetch, backoff, research]
license: MIT
compatibility: hermes, opencode, python, bash
metadata:
  hermes:
    tags: [http, scraping, web, curl, requests, httpx, fetch, research]
    category: research
---

# Web Fetch & Robust HTTP Content Retrieval

Best practices for autonomous agents fetching remote web pages, API payloads, and documentation cleanly without getting blocked or hanging indefinitely.

## 1. Core Principles

- **Always Enforce Timeouts**: Never make an HTTP request without explicit connect and read timeouts (default: 10s connect, 30s read).
- **Realistic Headers**: Send realistic `User-Agent`, `Accept`, and `Accept-Language` headers to avoid immediate 403 Forbidden bot filters.
- **Backoff & Jitter**: Implement exponential backoff for transient HTTP 429 (Too Many Requests) and 5xx errors.
- **Fail Fast on Heavy Payloads**: Check `Content-Length` and `Content-Type` before downloading arbitrary files to avoid memory bloat.

---

## 2. Essential CLI Workflows (`curl`)

```bash
# Fetch HTML cleanly following redirects with timeout and custom User-Agent
curl -fsSL --connect-timeout 10 --max-time 30 \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36" \
  -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
  "https://example.com" -o /tmp/page.html

# Fetch API JSON with error code surfacing
curl -sS -w "\nHTTP_STATUS:%{http_code}\n" \
  -H "Accept: application/json" \
  "https://api.example.com/data"
```

---

## 3. Production Python Retrieval Pattern (`httpx`)

```python
import httpx
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
}

def fetch_content(url: str, retries: int = 3, backoff: float = 1.5) -> str:
    with httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0), headers=HEADERS, follow_redirects=True) as client:
        for attempt in range(retries):
            try:
                response = client.get(url)
                if response.status_code == 429:
                    sleep_time = backoff ** attempt
                    time.sleep(sleep_time)
                    continue
                response.raise_for_status()
                return response.text
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt == retries - 1:
                    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {e}")
                time.sleep(backoff ** attempt)
```

---

## 4. When to Escalate to Headless Browsers

If the target site requires JavaScript execution, displays Cloudflare Turnstile / Bot Detection, or returns empty `<div id="root"></div>`, escalate to `research/scrapling` or Playwright automation rather than raw HTTP fetching.
