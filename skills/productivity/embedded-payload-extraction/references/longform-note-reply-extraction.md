# Extracting long-form payloads carried in an author's self-reply (X/Twitter)

## When this applies

The root tweet is a hook — "`# Give below prompt to your Hermes agent👇`", "prompt in the reply", "thread 🧵" — and the real payload (full prompt, spec, step list) lives in the **author's own reply**, published as a long-form note (>280 chars).

What does NOT work:
- `api.fxtwitter.com/<user>/status/<id>` — returns only the root tweet (`tweet.text`); no thread, no replies.
- `og:description` / `<title>` on the fixupx render — truncated at ~276 chars and root-only.
- The `amplify_video_thumb` preload only tells you there is video, not text.

What DOES work: the fixupx.com HTML carries the payload inside `dehydratedData` (relay records); a long reply shows up as `NoteTweetResults` -> `NoteTweet` with a `text:` field.

## Step 1 — download the HTML

```bash
curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36" \
  "https://fixupx.com/<user>/status/<tweet_id>" -o /tmp/fx.html
wc -c /tmp/fx.html   # simple tweet ~40-80KB; with a long note the HTML grows past 150KB
```

Sanity check: if the page mentions `note_tweet_results` / `NoteTweet`, the long text is in there.

## Step 2 — extract

Preferred: run the bundled script (root tweet + all embedded notes as JSON):

```bash
python3 /opt/data/skills/research/embedded-payload-extraction/scripts/extract_longform_note.py \
  "https://x.com/<user>/status/<tweet_id>"
```

Manual, verified approach (anchor by a distinctive phrase + wide window):

```python
h = open('/tmp/fx.html', encoding='utf-8', errors='ignore').read()
k = 'First reuse what you already know'      # any fragment you saw in the truncated OG text
BS = chr(92)
seg = (h[h.find(k)-1000 : h.find(k)+8000]
       .replace(BS + 'n', chr(10))
       .replace(BS + '"', '"'))
print(seg)
```

The full note sits a few hundred chars after `NoteTweet",text:"`. If the print is cut off, advance the offset (`seg[3400:]`) — do NOT re-fetch.

Cleaner variant, anchored on the record type:

```python
import re, html
BS = chr(92)
h = open('/tmp/fx.html', encoding='utf-8', errors='ignore').read()
for m in re.finditer(re.escape('__typename:"NoteTweet",text:"'), h):
    j, buf = m.end(), []
    while j < len(h):
        c = h[j]
        if c == BS:
            buf.append(h[j+1]); j += 2; continue
        if c == '"':
            break
        buf.append(c); j += 1
    print('===== NOTE =====')
    print(html.unescape(''.join(buf)))
```

**Pitfall with the short anchor `text:"`:** it also matches the root tweet's `full_text:"`, which yields only the 279-char hook and makes you think the note is missing. Always anchor on `__typename:"NoteTweet",text:"` or on a phrase unique to the reply.

## Step 3 — other useful signals in the HTML

- `replyCount:N` plus the presence of `note_tweet_results` means there is a reply / long note.
- FXTwitter's `tweet.quote` gives the quoted tweet and helps frame the thread.
- Fallbacks if the reply is not in the fixupx HTML: `/opt/data/scripts/tweet-scraper.py` (Nitter) or an external search on a distinctive phrase from the prompt.

## Verified case — 2026-09-10

URL: `https://x.com/BkashJosi/status/2097980995735785752`
- Root (hook): "My Hermes Agent has a newspaper for me now… # Give below prompt to your Hermes agent👇"
- FXTwitter: root only. OG: cut off at "Would you read…".
- Author's self-reply = a ~5.5K-char long note containing the full "Hermes Agent Times" prompt (4 pages, anti-fabrication rules, cron, Obsidian, printing). Retrieved from the fixupx HTML with the method above.

## Reporting consequence

The Links de X group format (Relevancia / Resumen / Key Takeaway / Stack / Accion) must be built from the REPLY payload, not the hook.
