#!/usr/bin/env python3
"""Transcribe audio (nota de voz) usando whisper via NaN Builders API (OpenAI-compatible).

Uso:
    python3 transcribe_audio.py <audio.ogg> [idioma]   # idioma por defecto: es

Puntos clave:
- Lee la API key de /opt/data/config.yaml (stt.openai.api_key). La key NO se puede
  copiar de la salida de herramientas de Hermes (la muestra enmascarada, ej.
  sk-JzB...ohYw); hay que leerla del archivo con yaml.
- Requiere User-Agent de navegador: sin el, la API responde HTTP 403 code 1010 (Cloudflare).
- Audio entrante de WhatsApp/Telegram/Discord suele caer en /opt/data/cache/audio/aud_*.ogg
"""
import sys
import uuid
import json

import yaml
import urllib.request
import urllib.error

CONFIG = "/opt/data/config.yaml"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 transcribe_audio.py <audio> [idioma]", file=sys.stderr)
        sys.exit(2)
    audio_path = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else "es"

    with open(CONFIG) as f:
        cfg = yaml.safe_load(f)
    stt = cfg["stt"]["openai"]
    key = stt["api_key"]
    base = stt["base_url"]
    model = stt.get("model", "whisper")

    with open(audio_path, "rb") as f:
        audio = f.read()

    boundary = uuid.uuid4().hex

    def field(name, value):
        return (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode()

    body = b""
    body += field("model", model)
    body += field("language", lang)
    body += (f'--{boundary}\r\nContent-Disposition: form-data; '
             f'name="file"; filename="voice.ogg"\r\nContent-Type: audio/ogg\r\n\r\n').encode()
    body += audio
    body += f'\r\n--{boundary}--\r\n'.encode()

    req = urllib.request.Request(base.rstrip("/") + "/audio/transcriptions",
                                 data=body, method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("User-Agent", UA)
    req.add_header("Accept", "application/json, text/plain, */*")

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = resp.read().decode()
            print(json.loads(data).get("text", data))
    except urllib.error.HTTPError as e:
        print(f"HTTPError {e.code}: {e.read().decode()[:500]}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
