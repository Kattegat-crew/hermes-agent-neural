# FXTwitter API — X/Twitter Extraction Without Login

## Method

FXTwitter (`api.fxtwitter.com`) returns full tweet metadata as JSON, bypassing X's login wall.

### URL Format

- Normal tweet: `https://api.fxtwitter.com/USER/status/TWEET_ID`
- Article/anonymous: `https://api.fxtwitter.com/i/status/TWEET_ID`

### Response Structure

```json
{
  "code": 200,
  "tweet": {
    "url": "https://x.com/USER/status/ID",
    "id": "ID",
    "text": "Tweet content",
    "author": {
      "screen_name": "user",
      "name": "Display Name",
      "followers": 12345,
      "description": "Bio"
    },
    "created_at": "Thu Aug 13 02:45:37 +0000 2026",
    "views": 17435,
    "likes": 74,
    "replies": 10,
    "retweets": 5,
    "lang": "en",
    "is_note_tweet": true,
    "article": {  // only for X Articles
      "title": "Article Title",
      "preview_text": "First paragraph...",
      "content": { "blocks": [...] }  // full Draft.js content
    },
    "card": {  // linked content preview
      "title": "Preview Title",
      "description": "Preview description"
    },
    "media_entities": [...]  // images, videos
  }
}
```

### Extraction Strategy

1. Call `web_extract([f"https://api.fxtwitter.com/{user}/status/{id}"])` 
2. Parse JSON from `content` field (wrapped in ````json\n...\n````)
3. For `i/status` URLs: the response reveals the real author (e.g., `VibeMarketer_` for what looked like an anonymous link)
4. If `tweet.text` is empty, check `tweet.article` for long-form content
5. If tweet has no text and no article, it's a link-only tweet — use `tweet.card.title` as description

### Rate Limiting

FXTwitter may return 429 if hit too fast. Add `time.sleep(0.3)` between calls. In practice, 31 concurrent extractions worked with minimal 429s.

### Pitfalls

- `tweet.created_at` format: `"Thu Aug 13 02:45:37 +0000 2026"` — extract date with `[:10]` after parsing or regex `\w+ (\w+ \d+ \d{4})`
- `tweet.lang` is the original language; translate to Spanish for tags/description
- Some tweets have `text` in Chinese/Japanese — the content is still extractable and translatable
- `tweet.article.content.blocks` is Draft.js format: parse `type` (header-two, unordered-list-item, etc.) + `text`

## Comparison with Alternatives

| Method | Login Required | Content Quality | Speed |
|--------|---------------|----------------|-------|
| FXTwitter API | No | Full (text, metrics, article) | ~1-2s |
| x.com direct | Yes (login wall) | Blocked for unauth | N/A |
| Nitter | No | Partial, often broken | Slow |
| web_search + cached | No | Fragmented | Variable |

FXTwitter is the clear winner for programmatic extraction.