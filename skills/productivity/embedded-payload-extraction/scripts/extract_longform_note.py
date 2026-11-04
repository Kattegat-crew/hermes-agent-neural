#!/usr/bin/env python3
"""Extract a tweet's root text plus any long-form note (self-reply) embedded in fixupx HTML.

Usage:
    python3 extract_longform_note.py https://x.com/<user>/status/<tweet_id> [--html PATH]

Why: api.fxtwitter.com returns ONLY the root tweet. When the root is a hook
("prompt below"), the payload lives in the author's self-reply, published as a
long note, and IS present in the fixupx.com HTML hydration state.
"""
import argparse
import html as htmllib
import json
import re
import sys
import urllib.request

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}
BS = chr(92)
NOTE_ANCHOR = '__typename:"NoteTweet",text:"'


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "ignore")


def to_fixupx(url: str) -> str:
    return re.sub(r"https?://(www\.)?(x|twitter)\.com", "https://fixupx.com", url)


def to_api(url: str) -> str:
    return re.sub(r"https?://(www\.)?(x|twitter)\.com", "https://api.fxtwitter.com", url)


def root_tweet(url: str) -> dict:
    try:
        data = json.loads(fetch(to_api(url)))
    except Exception as exc:  # network / JSON issues -> caller still gets the HTML notes
        return {"error": str(exc)}
    t = data.get("tweet", {})
    return {
        "author": "@" + (t.get("author", {}) or {}).get("screen_name", "?"),
        "created_at": t.get("created_at"),
        "text": t.get("text"),
        "likes": t.get("likes"),
        "views": t.get("views"),
        "replies": t.get("replies"),
    }


def embedded_notes(page: str) -> list:
    """Walk the escaped JSON string that follows every NoteTweet marker."""
    out = []
    for m in re.finditer(re.escape(NOTE_ANCHOR), page):
        j, buf = m.end(), []
        while j < len(page):
            c = page[j]
            if c == BS:
                buf.append(page[j + 1])
                j += 2
                continue
            if c == '"':
                break
            buf.append(c)
            j += 1
        text = htmllib.unescape("".join(buf))
        if text and text not in out:
            out.append(text)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("url")
    ap.add_argument("--html", help="use an already-downloaded fixupx HTML file")
    args = ap.parse_args()

    if args.html:
        page = open(args.html, encoding="utf-8", errors="ignore").read()
    else:
        page = fetch(to_fixupx(args.url))

    payload = {
        "url": args.url,
        "root": root_tweet(args.url),
        "notes": embedded_notes(page),
        "html_bytes": len(page),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not payload["notes"]:
        print(
            "[warn] no embedded NoteTweet found - check whether the HTML contains "
            "'note_tweet_results', or fall back to /opt/data/scripts/tweet-scraper.py",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
