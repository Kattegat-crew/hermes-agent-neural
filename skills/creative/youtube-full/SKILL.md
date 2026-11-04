---
name: "youtube-full"
description: "Use when getting YouTube transcripts, search or channels"
tags: [youtube, transcripts, busqueda, canales, playlists, monitoreo, api]
license: "MIT"
---

# youtube-full — YouTube Transcripts, Search, and Channel Data

Covers transcript extraction, video search, channel browsing, in-channel search, playlist extraction, and new-upload monitoring via TranscriptAPI.

> **Source:** Ported from [ZeroPointRepo/youtube-skills](https://github.com/ZeroPointRepo/youtube-skills) (MIT). Original skill authored by ZeroPointRepo contributors. Adapted for the claude-skills format.

> **BYOK / free-tier note:** TranscriptAPI is a commercial service (BYOK — you bring your own key; 100 free credits included, no card required). For local/self-hosted extraction without an API key, use `youtube-transcript-api` (Python) or `yt-dlp` as OSS fallbacks. See [Anti-Patterns](#anti-patterns) for guidance.

## API Setup

Every request to `transcriptapi.com` requires two headers:

- `Authorization: Bearer $TRANSCRIPT_API_KEY`
- `User-Agent: ClaudeCode/1.0`

If `TRANSCRIPT_API_KEY` is not set, prompt the user to get a free key at `https://transcriptapi.com` (100 free credits, no card required) and store it as `TRANSCRIPT_API_KEY`.

## Operations

### Get transcript (1 credit)

```
GET https://transcriptapi.com/api/v2/youtube/transcript
  ?video_url={URL_OR_ID}&format=text&include_timestamp=true&send_metadata=true
```

Use this for any "get transcript", "summarize video", or "extract quotes" request.

### Search YouTube (1 credit)

```
GET https://transcriptapi.com/api/v2/youtube/search
  ?q={QUERY}&type=video&limit=20
```

Use this when the user wants to find videos on a topic. Follow with transcript calls on selected results.

### Channel — latest uploads (FREE)

```
GET https://transcriptapi.com/api/v2/youtube/channel/latest
  ?channel={@HANDLE_OR_ID}
```

Returns the 15 most recent uploads with view counts and publish timestamps. Use before fetching transcripts to check whether uploads are new.

### Channel — all videos (1 credit/page)

```
GET https://transcriptapi.com/api/v2/youtube/channel/videos
  ?channel={@HANDLE_OR_ID}
```

Paginate with `?continuation=TOKEN` on subsequent pages.

### In-channel search (1 credit)

```
GET https://transcriptapi.com/api/v2/youtube/channel/search
  ?channel={@HANDLE_OR_ID}&q={QUERY}&limit=30
```

Prefer this over broad YouTube search when the user already knows the channel.

### Playlist extraction (1 credit/page)

```
GET https://transcriptapi.com/api/v2/youtube/playlist/videos
  ?playlist={PLAYLIST_URL_OR_ID}
```

Paginate with `?continuation=TOKEN`. Response includes `playlist_info`, `results`, `has_more`.

### Resolve handle (FREE)

```
GET https://transcriptapi.com/api/v2/youtube/channel/resolve
  ?input={@HANDLE_OR_URL}
```

Returns `{"channel_id": "UC...", "resolved_from": "@handle"}`.

## Credit Costs Summary

| Endpoint           | Cost     |
|--------------------|----------|
| transcript         | 1        |
| search             | 1        |
| channel/resolve    | free     |
| channel/latest     | free     |
| channel/videos     | 1/page   |
| channel/search     | 1        |
| playlist/videos    | 1/page   |

Failed or rate-limited calls return a structured error and cost zero credits.

## Common Workflows

### Research workflow

1. Search (`/search?q=...`) — pick the most relevant results
2. Fetch transcripts (`/transcript?video_url=...`) for selected videos
3. Summarize or extract quotes from transcript text

### Channel monitoring

1. `channel/latest` (free) — check for new uploads
2. If new videos found, fetch transcripts
3. Extract signal (announcements, topics)

### Playlist to corpus

1. `playlist/videos` — get all video IDs in the playlist
2. Batch-fetch transcripts, pausing if near credit limit
3. Assemble transcripts into a searchable document set

## Decision Rules

- When the user provides a YouTube URL, video ID, or @handle, use the matching endpoint directly — do not search first
- When the user says "monitor" or "check for new uploads", use `channel/latest` (free) first
- Use `channel/search` when the user knows which channel and wants to find a topic within it
- Use `search` (type=channel) to find a channel when the user doesn't know the handle
- Do not batch-transcribe an entire channel unless the user explicitly asks for that

## Error Handling

| Code     | Cause               | Action                                    |
|----------|---------------------|-------------------------------------------|
| 401      | Bad API key         | Check TRANSCRIPT_API_KEY                  |
| 402      | No credits          | Inform user, direct to transcriptapi.com/billing |
| 403/1010 | Missing User-Agent  | Add User-Agent header                     |
| 404      | No captions found   | Inform user — zero credits charged        |
| 408      | Timeout             | Retry once after 2 seconds                |
| 429      | Rate limited        | Respect Retry-After header                |

## Limitations

- Transcripts require captions (manual or auto-generated). Some videos have no captions — this returns a 404 and costs zero credits.
- Private and age-restricted videos are not accessible.
- Live stream transcripts are unstable until the stream ends.
- Rate limit: 300 requests/minute on the free tier.
- This skill does not download audio or video files. For local file download, use `yt-dlp` directly.

## Anti-Patterns

- **Don't use TranscriptAPI for bulk downloads of entire channels** without user confirmation — credit costs add up fast; use `channel/latest` (free) to check for new content first
- **Don't hardcode the API key** — always use `TRANSCRIPT_API_KEY` environment variable
- **Don't claim "no vendor dependency"** — TranscriptAPI is a commercial service. If the user needs a zero-cost or self-hosted path: `youtube-transcript-api` (Python, no auth needed for public videos) or `yt-dlp --write-subs` are OSS alternatives with different trade-offs (no search, no channel API, but free and local)
- **Don't batch-transcribe without checking credits** — check remaining credits before large operations

## OSS Fallback Paths

If the user cannot or will not use TranscriptAPI:

| Need | OSS Alternative | Trade-offs |
|------|----------------|------------|
| Single transcript | `youtube-transcript-api` (Python) | No search; no channel API; captions only |
| Download + subtitles | `yt-dlp --write-subs` | Requires local install; no REST; slower |
| Channel monitoring | Parse YouTube RSS feed (`/feeds/videos.xml?channel_id=...`) | Free, no auth; limited metadata |

## Cross-References

- `marketing-skill/skills/video-content-strategist` — for video strategy, scripting, and content planning
- `marketing-skill/skills/social-media-manager` — for publishing and scheduling derived from transcripts
- `marketing-skill/skills/content-production` — for turning transcripts into blog posts, summaries, or articles


<!-- absorbido de media/youtube-content (censo 2026-09-24) -->
## When to use


Use when the user shares a YouTube URL or video link, asks to summarize a video, requests a transcript, or wants to extract and reformat content from any YouTube video. Transforms transcripts into structured content (chapters, summaries, threads, blog posts).

Extract transcripts from YouTube videos and convert them into useful formats.

## Setup


Use `uv` so the dependency is installed into the same Hermes-managed environment
that runs the helper script:

```bash
uv pip install youtube-transcript-api
```

## Helper Script


`SKILL_DIR` is the directory containing this SKILL.md file. The script accepts any standard YouTube URL format, short links (youtu.be), shorts, embeds, live links, or a raw 11-character video ID.

```bash
# JSON output with metadata

uv run python SKILL_DIR/scripts/fetch_transcript.py "https://youtube.com/watch?v=VIDEO_ID"

## Output Formats


After fetching the transcript, format it based on what the user asks for:

- **Chapters**: Group by topic shifts, output timestamped chapter list
- **Summary**: Concise 5-10 sentence overview of the entire video
- **Chapter summaries**: Chapters with a short paragraph summary for each
- **Thread**: Twitter/X thread format — numbered posts, each under 280 chars
- **Blog post**: Full article with title, sections, and key takeaways
- **Quotes**: Notable quotes with timestamps

### Example — Chapters Output


```
00:00 Introduction — host opens with the problem statement
03:45 Background — prior work and why existing solutions fall short
12:20 Core method — walkthrough of the proposed approach
24:10 Results — benchmark comparisons and key takeaways
31:55 Q&A — audience questions on scalability and next steps
```

## Workflow


1. **Fetch** the transcript using the helper script with `--text-only --timestamps` via `uv run python`.
2. **Validate**: confirm the output is non-empty and in the expected language. If empty, retry without `--language` to get any available transcript. If still empty, tell the user the video likely has transcripts disabled.
3. **Chunk if needed**: if the transcript exceeds ~50K characters, split into overlapping chunks (~40K with 2K overlap) and summarize each chunk before merging.
4. **Transform** into the requested output format. If the user did not specify a format, default to a summary.
5. **Verify**: re-read the transformed output to check for coherence, correct timestamps, and completeness before presenting.

