#!/usr/bin/env python3
"""VTT -> texto plano para análisis de transcripciones de video.

Uso: python3 vtt_to_text.py <archivo.vtt> [salida.txt]

- Elimina cabeceras WEBVTT/NOTE, índices de cue y líneas de timestamps.
- Deduplica cues repetidos (los captions automáticos repiten líneas entre cues
  consecutivos al hacer rolling captions).
- Inserta marcas [HH:MM] por minuto para poder citar minutos concretos.
- Reflow: une las líneas cortas de captions en párrafos por minuto.
"""
import re
import sys

TS = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})[.,]\d{3}\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[.,]\d{3}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None

    seen: set[str] = set()
    minutes: dict[int, list[str]] = {}
    for raw in open(src, encoding="utf-8", errors="ignore"):
        line = raw.strip()
        m = TS.match(line)
        if m:
            minute = int(m.group(1)) * 60 + int(m.group(2))
            minutes.setdefault(minute, [])
            continue
        if not line or line.upper().startswith(("WEBVTT", "NOTE", "STYLE", "KIND", "LANGUAGE")):
            continue
        if line.isdigit():  # índice de cue
            continue
        if line.startswith(("[", "(")) and line.rstrip(("]", ")")).endswith(")") and len(line) < 40:
            continue  # [música], [aplausos], etc.
        if line in seen:
            continue
        seen.add(line)
        # asignar al último minuto visto
        if minutes:
            minutes[max(minutes)].append(line)

    out: list[str] = []
    for minute in sorted(minutes):
        text = " ".join(minutes[minute])
        out.append(f"[{minute // 60:02d}:{minute % 60:02d}] {text}")
    result = "\n\n".join(out) + "\n"
    if dst:
        open(dst, "w", encoding="utf-8").write(result)
        print(f"OK {dst} ({len(result)} chars, {len(minutes)} minutos)")
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
