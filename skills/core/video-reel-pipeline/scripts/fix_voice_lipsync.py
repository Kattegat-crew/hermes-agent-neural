#!/usr/bin/env python3
"""fix_voice_lipsync.py — Re-foniza un clip de reel con voz de marca ElevenLabs
(TTS desde TEXTO corregido) y aplica fal-ai/sync-lipsync para labial real.

Receta validada 2026-08-29 (S1 Lucky, Bingo Millonario). Ver SKILL.md de la skill
creative/reel-voice-lipsync para la tabla de caminos y los pitfalls.

Requiere env: ELEVENLABS_API_KEY, FAL_KEY.
Uso:
  python3 fix_voice_lipsync.py \
    --voice U9tZtg3uJtVgXPkvosWR \
    --text "Hola, soy Lucky, tu trébol de la suerte..." \
    --clip-url https://dominio.com/clips/S1.mp4 \
    --wav-url https://dominio.com/voz/S1-fix.wav \
    --out /tmp/S1_lipsync.mp4
Pasos: TTS -> duración -> atempo a duración del clip -> publica probe de duración
NO incluida (el WAV debe estar YA publicado en URL https pública) -> lipsync
submit + poll -> descarga. El WAV y el clip deben ser alcanzables por fal.ai.
"""
import argparse, json, os, sys, time, urllib.request, urllib.error

def http_json(url, payload=None, headers=None, timeout=90):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                 headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()

def tts(voice_id, text, out_mp3):
    key = os.environ["ELEVENLABS_API_KEY"]
    body = {"text": text, "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75,
                               "style": 0.15, "use_speaker_boost": True}}
    st, data = http_json(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128",
        payload=body,
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"})
    open(out_mp3, "wb").write(data)
    print(f"TTS ok http {st} — {len(data)} bytes -> {out_mp3}")

def lipsync(video_url, audio_url, out_mp4, model="fal-ai/sync-lipsync"):
    key = os.environ["FAL_KEY"]
    h = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    st, data = http_json(f"https://queue.fal.run/{model}",
                         payload={"video_url": video_url, "audio_url": audio_url,
                                  "sync_mode": "cut_off"}, headers=h)
    resp = json.loads(data)
    print(f"lipsync submit {st} request_id={resp.get('request_id')}")
    if st not in (200, 202):
        print("ERROR submit:", data.decode()[:400]); sys.exit(1)
    for i in range(90):
        time.sleep(5)
        _, sd = http_json(resp["status_url"], headers={"Authorization": f"Key {key}"})
        s = json.loads(sd)
        print(f"[{(i+1)*5}s] {s.get('status')}", flush=True)
        if s.get("status") in ("COMPLETED", "OK"):
            _, rd = http_json(resp["response_url"], headers={"Authorization": f"Key {key}"})
            url = json.loads(rd)["video"]["url"]
            _, vd = http_json(url, timeout=180)
            open(out_mp4, "wb").write(vd)
            print(f"OK -> {out_mp4} ({len(vd)} bytes)")
            return
        if s.get("status") in ("FAILED", "ERROR"):
            print("FAILED:", sd.decode()[:600]); sys.exit(2)
    print("TIMEOUT poll"); sys.exit(3)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", required=True)
    ap.add_argument("--text", required=True, help="texto CON respelling aplicado")
    ap.add_argument("--clip-url", required=True)
    ap.add_argument("--wav-url", required=True, help="WAV ya calzado y publicado en https")
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip-tts", action="store_true", help="solo lipsync, WAV ya existe")
    a = ap.parse_args()
    if not a.skip_tts:
        tts(a.voice, a.text, "/tmp/fix_voice_tts.mp3")
        # atempo: calcular fuera con ffprobe y publicar; el WAV debe existir antes
        print("recuerda: atempo + publicar WAV antes de lipsync (ver SKILL.md paso 2-3)")
    lipsync(a.clip_url, a.wav_url, a.out)
