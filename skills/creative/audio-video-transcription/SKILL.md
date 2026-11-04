---
name: audio-video-transcription
description: "Use when transcribing audio/video via whisper API."
tags: [transcripcion, whisper, audio, video, ffmpeg, stt, subtitulos, transcription]
---

# Audio/Video Transcription via NaN Builders Whisper API

Transcribe audios and videos to text using the whisper endpoint at https://api.nan.builders/v1

## API Details

- **Endpoint:** POST https://api.nan.builders/v1/audio/transcriptions
- **API Key:** From config stt.openai.api_key (load with yaml.safe_load)
- **Model:** whisper
- **Language:** es (Spanish)
- **Supported formats:** MP3, WAV, OGG (MP3 recommended)

## Critical Limits (Verified 2026-09-08)

| Parameter | Value |
|---|---|
| Minimum segment duration | ~2 minutes (shorter returns empty text) |
| Maximum segment duration | ~52 minutes (55+ returns HTTP 503) |
| Recommended chunk size | 50 minutes |
| Processing speed | ~30 seconds per 50-min chunk |

## Workflow

### Step 1 - Extract audio (if video)
```bash
ffmpeg -i input_video.mp4 -vn -ar 16000 -ac 1 -b:a 64k audio.mp3
```

### Step 2 - Split into 50-min chunks
```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 input.mp3
ffmpeg -i input.mp3 -ss 0 -t 3000 -c copy chunk_01.mp3
ffmpeg -i input.mp3 -ss 3000 -t 3000 -c copy chunk_02.mp3
ffmpeg -i input.mp3 -ss 6000 -t 1200 -c copy chunk_03.mp3
```

### Step 3 - Transcribe each chunk
```python
import yaml, requests, json, time

with open(os.path.expanduser("~/hermes-agent/data/config.yaml")) as f:
    cfg = yaml.safe_load(f)

api_key = cfg["stt"]["openai"]["api_key"]
base_url = cfg["stt"]["openai"]["base_url"]
url = f"{base_url}/audio/transcriptions"

chunks = ["chunk_01.mp3", "chunk_02.mp3", "chunk_03.mp3"]
offsets = [0, 3000, 6000]

all_segments = []
for i, path in enumerate(chunks):
    with open(path, "rb") as f:
        resp = requests.post(url,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (f"chunk_{i+1}.mp3", f, "audio/mpeg")},
            data={"model": "whisper", "language": "es", "response_format": "verbose_json"},
            timeout=300)
    r = resp.json()
    for seg in r.get("segments", []):
        seg["start"] += offsets[i]
        seg["end"] += offsets[i]
        all_segments.append(seg)
```

### Step 4 - Generate .docx (optional)
Use python-docx to create a formatted Word document with timestamps, headers every 10 min, and title page.

## Failure Modes

- Empty text on short segments (less than 2 min) - API ignores them. Always use 2+ min chunks.
- HTTP 503 on long segments (more than 52 min) - Split into smaller chunks.
- NaN Builders whisper endpoint NOT accessible via hermes-llm-proxy. Use direct api.nan.builders/v1 endpoint with the stt.openai.api_key from config.

## Quick Reference Script

```python
import yaml, requests, json, time, subprocess, os

def transcribe_media(input_path, output_txt=None):
    with open(os.path.expanduser("~/hermes-agent/data/config.yaml")) as f:
        cfg = yaml.safe_load(f)
    api_key = cfg["stt"]["openai"]["api_key"]
    base_url = cfg["stt"]["openai"]["base_url"]
    url = f"{base_url}/audio/transcriptions"

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", input_path],
        capture_output=True, text=True)
    duration = float(result.stdout.strip())

    mp3_path = input_path.rsplit(".", 1)[0] + "_16k.mp3"
    subprocess.run(["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", "-b:a", "64k", mp3_path],
                   capture_output=True)

    chunk_duration = 3000
    chunks = []
    offsets = []
    for start in range(0, int(duration), chunk_duration):
        chunk_num = len(chunks) + 1
        chunk_path = f"/tmp/transcribe_chunk_{chunk_num:02d}.mp3"
        subprocess.run(["ffmpeg", "-y", "-i", mp3_path, "-ss", str(start),
                       "-t", str(min(chunk_duration, duration - start)),
                       "-c", "copy", chunk_path], capture_output=True)
        chunks.append(chunk_path)
        offsets.append(start)

    all_segments = []
    for i, (path, offset) in enumerate(zip(chunks, offsets)):
        with open(path, "rb") as f:
            resp = requests.post(url,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (f"chunk_{i+1}.mp3", f, "audio/mpeg")},
                data={"model": "whisper", "language": "es", "response_format": "verbose_json"},
                timeout=300)
        r = resp.json()
        for seg in r.get("segments", []):
            seg["start"] += offset
            seg["end"] += offset
            all_segments.append(seg)

    full_text = "\n".join(s["text"].strip() for s in all_segments)
    if output_txt:
        with open(output_txt, "w") as f:
            f.write(full_text)

    for c in chunks:
        os.remove(c)
    if os.path.exists(mp3_path):
        os.remove(mp3_path)

    return full_text, all_segments
```