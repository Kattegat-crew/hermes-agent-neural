#!/usr/bin/env python3
"""tts_elevenlabs.py — locución ElevenLabs con tope de gasto mensual y registro en MANIFEST.

Voces FIJAS (octubre 2026): Golden=Angie (YPh7OporwNAJ28F5IQrm),
Paradise=Daniela (tTdCI0IDTgFa2iLQiWu4). Modelo eleven_multilingual_v2.
Tope: $2.00/mes (ELEVENLABS_CAP_USD). Cada request se registra en MANIFEST.jsonl
(ts, label, voice_id, chars, request_id, costo acumulado).

SOLO corre si TTS_APPROVED=1 (gate humano, KANBAN gate 3). El --dry-run del
pipeline NUNCA llama este script.

uso: TTS_APPROVED=1 python3 tts_elevenlabs.py --mes 2026-11 --locuciones loc.json \
        --outdir voz/ [--brand golden]
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.request
import zoneinfo

BOGOTA = zoneinfo.ZoneInfo("America/Bogota")
KEY_FILE = "/opt/marketing-campaign-generator/.env"
API = "https://api.elevenlabs.io/v1"
VOICES = {"golden": "YPh7OporwNAJ28F5IQrm",     # Angie
          "paradise": "tTdCI0IDTgFa2iLQiWu4"}   # Daniela
MODEL = "eleven_multilingual_v2"
COST_PER_1K = 0.18  # tasa payg observada en oct 2026
MANIFEST = "/opt/hermes-agent-data/home/proyectos/rendicion-mensual/ELEVENLABS_MANIFEST.jsonl"
DEFAULT_CAP = 2.00


def api_key():
    if os.environ.get("ELEVENLABS_API_KEY"):
        return os.environ["ELEVENLABS_API_KEY"]
    with open(KEY_FILE, encoding="utf-8") as fh:
        m = re.search(r"^ELEVENLABS_API_KEY=(\S+)", fh.read(), re.M)
        return m.group(1) if m else None


def month_spend(mes):
    """Suma de costo estimado registrado en el MANIFEST para el mes YYYY-MM."""
    if not os.path.exists(MANIFEST):
        return 0.0, 0
    total, chars = 0.0, 0
    with open(MANIFEST, encoding="utf-8") as fh:
        for line in fh:
            try:
                j = json.loads(line)
            except json.JSONDecodeError:
                continue
            if j.get("mes") == mes:
                total += j.get("costo_usd", 0.0)
                chars += j.get("chars", 0)
    return total, chars


def speak(key, text, voice_id, out_mp3):
    body = json.dumps({"text": text, "model_id": MODEL,
                       "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}).encode()
    req = urllib.request.Request(f"{API}/text-to-speech/{voice_id}", data=body, method="POST",
                                 headers={"xi-api-key": key, "Content-Type": "application/json",
                                          "Accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
        rid = r.headers.get("request-id", "n/d")
    with open(out_mp3, "wb") as fh:
        fh.write(data)
    return rid, len(text)


def to_wav(mp3, wav):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp3, "-ar", "48000", "-ac", "1", wav],
                   check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mes", required=True, help="YYYY-MM (para el tope y el MANIFEST)")
    ap.add_argument("--locuciones", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--brand", choices=["golden", "paradise", "all"], default="all")
    args = ap.parse_args()

    if os.environ.get("TTS_APPROVED") != "1":
        print("BLOQUEADO: TTS_APPROVED != 1 (gate humano de gasto, KANBAN gate 3)")
        return 3
    key = api_key()
    if not key:
        print("BLOQUEADO: sin ELEVENLABS_API_KEY en", KEY_FILE)
        return 3

    cap = float(os.environ.get("ELEVENLABS_CAP_USD", DEFAULT_CAP))
    gastado, chars_prev = month_spend(args.mes)
    presupuesto = cap - gastado
    loc = json.load(open(args.locuciones, encoding="utf-8"))
    brands = list(loc) if args.brand == "all" else [args.brand]
    os.makedirs(args.outdir, exist_ok=True)

    print(f"tope ${cap:.2f} · gastado este mes ${gastado:.2f} ({chars_prev} chars) · "
          f"presupuesto restante ${presupuesto:.2f}")
    pend = [(b, beat) for b in brands for beat in loc[b]]
    chars_tot = sum(len(beat["voz"]) for b, beat in pend)
    costo_est = chars_tot / 1000 * COST_PER_1K
    if costo_est > presupuesto:
        print(f"BLOQUEADO: costo estimado ${costo_est:.2f} excede presupuesto "
              f"${presupuesto:.2f} (tope mensual ${cap:.2f})")
        return 4
    print(f"costo estimado: ${costo_est:.2f} ({chars_tot} chars) → OK")

    rc = 0
    for b, beat in pend:
        out_mp3 = os.path.join(args.outdir, f"{b}_b{beat['n']:02d}.mp3")
        out_wav = os.path.join(args.outdir, f"{b}_b{beat['n']:02d}.wav")
        rid, chars = speak(key, beat["voz"], VOICES[b], out_mp3)
        to_wav(out_mp3, out_wav)
        os.remove(out_mp3)
        costo = chars / 1000 * COST_PER_1K
        gastado += costo
        entry = {"ts": dt.datetime.now(BOGOTA).isoformat(timespec="seconds"), "mes": args.mes,
                 "label": f"beat_{b}_{beat['n']}", "voice_id": VOICES[b], "chars": chars,
                 "request_id": rid, "costo_usd": round(costo, 4), "acumulado_usd": round(gastado, 4)}
        with open(MANIFEST, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        print(f"  ok {entry['label']} · {chars} chars · acumulado ${gastado:.2f}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
