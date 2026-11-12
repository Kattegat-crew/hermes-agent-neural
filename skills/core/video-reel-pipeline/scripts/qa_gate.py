#!/usr/bin/env python3
"""qa_gate.py — QA determinista de un film. Cero tokens, cero VLM.

Detecta lo que un modelo de video NO puede distinguir en un film oscuro:
frames realmente vacíos (voz sobre negro) frente a diseño oscuro intencional.

Uso:
  python3 qa_gate.py video.mp4 [--fps 1] [--std 9] [--mean 13] [--allow 0,22,30,43]

Salida: tabla por segundo + lista de frames vacíos.
Exit: 0 sin vacíos fuera de las ventanas permitidas · 1 hay vacíos · 2 no se pudo medir.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

try:
    from PIL import Image, ImageStat, ImageFilter
except ImportError:
    print("ERROR: falta Pillow (pip install pillow)", file=sys.stderr)
    sys.exit(2)


class GateError(RuntimeError):
    """El artefacto no se puede medir: no hay veredicto posible (nunca se aprueba)."""


def probe(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
             "-show_entries", "format=duration,size", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=60)
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
        raise GateError(f"ffprobe no ejecutable: {exc}") from exc
    if out.returncode != 0:
        raise GateError(f"ffprobe falló: {(out.stderr or '').strip()[:200]}")
    try:
        d = json.loads(out.stdout or "{}")
        st = d["streams"][0]
        num, den = str(st["r_frame_rate"]).split("/")
        fps = round(int(num) / int(den), 2)
        duration = float(d["format"]["duration"])
        size = int(d["format"]["size"])
        width, height = int(st["width"]), int(st["height"])
    except (json.JSONDecodeError, KeyError, IndexError, ValueError, TypeError, ZeroDivisionError) as exc:
        raise GateError(f"metadatos ilegibles en {path}: {exc}") from exc
    if duration <= 0 or fps <= 0 or width <= 0 or height <= 0:
        raise GateError(f"metadatos no positivos en {path}: {duration}s {fps}fps {width}x{height}")
    return {"w": width, "h": height, "fps": fps, "dur": duration, "size": size}


def frame_at(path, t, tmp):
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t}", "-i", str(path),
                        "-frames:v", "1", tmp], check=True, capture_output=True, timeout=120)
        return Image.open(tmp).convert("L")
    except (OSError, subprocess.SubprocessError) as exc:
        raise GateError(f"no se pudo extraer el frame {t}s: {exc}") from exc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--fps", type=float, default=1.0)
    ap.add_argument("--std", type=float, default=9.0)
    ap.add_argument("--mean", type=float, default=13.0)
    ap.add_argument("--allow", default="", help="segundos tolerados vacíos (intencionales)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    try:
        meta = probe(a.video)
        allow = {float(x) for x in a.allow.split(",") if x.strip()}
        tmp = os.path.join(tempfile.gettempdir(), "qa_gate_frame.png")
        empties, rows = [], []
        t = 0.0
        while t < meta["dur"]:
            im = frame_at(a.video, round(t, 2), tmp)
            st = ImageStat.Stat(im)
            edge = ImageStat.Stat(im.filter(ImageFilter.FIND_EDGES)).mean[0]
            empty = st.stddev[0] < a.std and st.mean[0] < a.mean
            rows.append((t, st.mean[0], st.stddev[0], edge, empty))
            if empty and not any(abs(t - x) <= 0.5 for x in allow):
                empties.append(round(t, 1))
            t += a.fps
    except GateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)

    if not a.quiet:
        print(f"{meta['w']}x{meta['h']} · {meta['fps']} fps · {meta['dur']:.2f}s · "
              f"{meta['size']/1e6:.1f} MB")
        print("  t   mean    std  edges  estado")
        for (t, m, s, e, emp) in rows:
            print(f"{t:4.1f} {m:6.1f} {s:6.1f} {e:6.2f}  {'VACIO' if emp else 'ok'}")

    if empties:
        print(f"\nFALLA: {len(empties)} frames vacíos sin justificar -> {empties}")
        print("Un film donde la voz habla sobre negro se lee como caída. "
              "Mantén el elemento saliente hasta que entre el siguiente.")
        sys.exit(1)

    print(f"\nOK: {len(rows)} muestras, ningún frame vacío fuera de las ventanas permitidas.")
    sys.exit(0)


if __name__ == "__main__":
    main()
