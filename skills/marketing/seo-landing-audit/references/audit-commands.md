# Audit Command Cookbook

Proven commands for the seo-landing-audit procedure (run from the DEV host against production; adjust domains).

## 1. Status sweep of all sitemap routes

```bash
for u in $(curl -s https://DOMAIN.com.co/sitemap.xml | grep -o 'https://[^<]*'); do
  echo "$u -> $(curl -s -o /dev/null -w '%{http_code}' "$u")"
done
```

## 2. Raw-HTML sweep: titles, placeholders, map links

```bash
for u in $(curl -s https://DOMAIN.com.co/sitemap.xml | grep -o 'https://[^<]*'); do
  h=$(curl -s "$u")
  echo "== $u"
  echo "  title: $(echo "$h" | grep -o '<title>[^<]*' | head -1)"
  echo "  placeholders: $(echo "$h" | grep -ci 'PENDIENTE\|TODO')"
  echo "  map place_id: $(echo "$h" | grep -o 'google.com/maps[^"]*' | grep -c 'place_id')"
done
```

## 3. Rendered DOM per route (headless chromium)

```bash
mkdir -p /tmp/audit
for p in / /bono /contacto /eventos /terminos /terminos-aguinaldo /politica-datos; do
  f=/tmp/audit/d$(echo $p | tr '/' '_').html
  timeout 35 chromium --headless=new --no-sandbox --disable-gpu \
    --virtual-time-budget=4000 --dump-dom "https://DOMAIN.com.co$p" > $f 2>/dev/null
  t=$(grep -o '<title>[^<]*' $f | head -1)
  h1=$(grep -o '<h1[^>]*>[^<]*' $f | head -1)
  echo "$p | $t | H1: $h1"
done
```

Flags matter: `--no-sandbox` (container), `--virtual-time-budget` (or JS routes render blank). If chromium is missing on the host, run the loop over `ssh dev` from the agent container.

## 4. Raw-vs-rendered comparison + similarity vs home (prerender duplication)

```bash
python3 - <<'PYEOF'
import re, glob

def text(p):
    h = open(p, encoding='utf-8', errors='ignore').read()
    t = re.sub(r'<script.*?</script>|<style.*?</style>', '', h, flags=re.S)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', t)).strip()

def bigrams(s):
    w = s.lower().split()
    return set(zip(w, w[1:]))

home = bigrams(text('/tmp/audit/d_.html'))  # adjust to the home dump filename
for f in sorted(glob.glob('/tmp/audit/d*.html')):
    b = bigrams(text(f))
    sim = len(home & b) / max(len(home | b), 1)
    print(f, 'sim vs home:', round(sim, 2))
PYEOF
```

Near-1.0 = the route's raw HTML is a copy of the home body (prerender never wrote per-route content). ~0 = route has its own raw HTML.

Same parser, checking title-vs-H1 mismatch and keyword presence in rendered text:

```python
for kw in ['Halloween', 'Aguinaldo', '11 de noviembre', '1 de noviembre', 'Ley 1581']:
    print(kw, t.count(kw))
```

A keyword that exists only in `<title>` while the H1/body shows the current campaign = stale seoMeta; two conflicting date strings on one page = content contradiction.

## 5. Headers, caching, TTFB

```bash
curl -sI -H 'Accept-Encoding: gzip, br' https://DOMAIN.com.co \
  | grep -iE 'content-encoding|cache-control|cf-cache-status|strict-transport'
curl -s -o /dev/null -w 'ttfb=%{time_starttransfer}s size=%{size_download}\n' https://DOMAIN.com.co
```

## 6. Alternate verification paths (before reporting a "missing")

```bash
# GSC verification — DNS TXT, not just meta tag:
dig +short TXT DOMAIN.com.co | grep google-site-verification
# og:image real file:
curl -s -o /tmp/og.webp 'OG_URL'; file /tmp/og.webp; ls -l /tmp/og.webp
# Repo freshness vs local dist:
ssh dev 'cd /opt/REPO && git log -1 --format="%h %ci" && stat -c "%y" dist/index.html'
```

If `dist/index.html` mtime predates the HEAD commit, local-mode audit results are void.

## 7. Gate blind-spot probe

```bash
# What the gate actually detects (placeholders? forbidden content?):
ssh dev 'grep -n "PENDIENTE\|TODO\|placeholder" /opt/REPO/scripts/qa_landing.py'
# Run the gate's own tests:
ssh dev 'cd /opt/REPO && python3 -m pytest tests/ -q'
```

Zero hits for a detector the checklist implies = structural false green; report it as a gate defect, then run that check manually over live URLs.
