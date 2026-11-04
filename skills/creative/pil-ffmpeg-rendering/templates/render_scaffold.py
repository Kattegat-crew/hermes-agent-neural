#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scaffold: render animation previews with PIL + numpy, encode to MP4 with ffmpeg.
Copy this file, keep the helpers, and write one `scene(t) -> PIL Image` per
concept. Frames are piped as raw RGB to ffmpeg — see CRITICAL pitfalls in
SKILL.md: rgb24 vs rgba, seconds timeline, select comma escaping.

Working reference implementation: /opt/data/scripts/paradise_clips/
"""
import math, os, random, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 720
FPS = 30

FD = "/usr/share/fonts/truetype/dejavu/"
FL = "/usr/share/fonts/truetype/liberation/"

def font(size, bold=False, serif=False, italic=False):
    if serif:
        path = FD + ("DejaVuSerif-Bold.ttf" if bold else "DejaVuSerif.ttf")
    elif italic:
        path = FL + "LiberationSerif-Italic.ttf"
    else:
        path = FD + ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    return ImageFont.truetype(path, size)

# ---------- easing ----------
def clamp01(v):
    return max(0.0, min(1.0, v))

def ease_out_cubic(t):
    t = clamp01(t)
    return 1 - (1 - t) ** 3

def ease_out_back(t):
    t = clamp01(t)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2

def ease_in_out(t):
    t = clamp01(t)
    return t * t * (3 - 2 * t)

def lerp(a, b, t):
    return a + (b - a) * t

# ---------- primitives ----------
def new_frame(bg=(10, 8, 10)):
    return Image.new("RGBA", (W, H), bg + (255,))

def vertical_gradient(img, stops):
    d = ImageDraw.Draw(img)
    for y in range(H):
        frac = y / (H - 1)
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= frac <= p1:
                t = (frac - p0) / (p1 - p0)
                c = tuple(int(c0[j] + (c1[j] - c0[j]) * t) for j in range(3))
                d.line([(0, y), (W, y)], fill=c + (255,))
                break

def glow_text(img, xy, text, fnt, fill, glow, radius=14, anchor="mm"):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text(xy, text, font=fnt, fill=glow + (200,), anchor=anchor)
    layer = layer.filter(ImageFilter.GaussianBlur(radius))
    d2 = ImageDraw.Draw(layer)
    d2.text(xy, text, font=fnt, fill=fill + (255,), anchor=anchor)
    img.alpha_composite(layer)

class Particles:
    """Gold-dust style floating particles with twinkle. seed for determinism."""
    def __init__(self, n, seed, area=(0, 0, W, H), speed=(20, 90), size=(1, 4),
                 colors=((245, 214, 110), (212, 175, 55), (255, 240, 180))):
        rnd = random.Random(seed)
        self.p = []
        for _ in range(n):
            self.p.append({
                "x": rnd.uniform(area[0], area[2]),
                "y": rnd.uniform(area[1], area[3]),
                "vy": rnd.uniform(-speed[1], -speed[0]),
                "vx": rnd.uniform(-20, 20),
                "s": rnd.uniform(size[0], size[1]),
                "c": rnd.choice(colors),
                "tw": rnd.uniform(0, 6.28),
            })
    def update(self, dt):
        for q in self.p:
            q["x"] += q["vx"] * dt
            q["y"] += q["vy"] * dt
            q["tw"] += dt * 7
    def draw(self, img, alpha=1.0):
        d = ImageDraw.Draw(img)
        for q in self.p:
            a = int(255 * alpha * (0.5 + 0.5 * math.sin(q["tw"])))
            if a <= 4:
                continue
            r = q["s"]
            d.ellipse([q["x"] - r, q["y"] - r, q["x"] + r, q["y"] + r], fill=q["c"] + (a,))

# ---------- encode ----------
def frames_for(duration, fn, fps=FPS):
    """fn(t_sec) -> PIL Image. t_sec runs 0..duration in REAL seconds (i/FPS)."""
    total = int(round(duration * fps))
    for i in range(total):
        yield fn(i / fps)

def encode(frames_iter, out_path, fps=FPS, total=None):
    """Pipe RGB frames (3 bytes/px) to ffmpeg with -pix_fmt rgb24."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),
        "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-preset", "medium",
        out_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = 0
    for frame in frames_iter:
        proc.stdin.write(frame.tobytes())
        n += 1
        if total and n % 60 == 0:
            print(f"  {n}/{total}", flush=True)
    proc.stdin.close()
    proc.wait()
    print(f"OK {out_path} ({n} frames)")

# ---------- QC helpers (run AFTER encode) ----------
# import numpy as np; from PIL import Image
# im = np.array(Image.open(png).convert("RGB")).astype(int)
# red = ((im[:,:,0] > 120) * (im[:,:,1] < 90) * (im[:,:,2] < 90)).sum()
# gold = ((im[:,:,0] > 120) * (im[:,:,1] > 90) * (im[:,:,2] < 200)).sum()
# Extract frame: ffmpeg -ss T -frames:v 1 out.png  (or select=eq(n\\,N) with escaped comma)

if __name__ == "__main__":
    # Example scene: fading gold text
    def scene(t):
        img = new_frame()
        if t > 0.2:
            fnt = font(64, bold=True)
            glow_text(img, (W // 2, H // 2), "PRUEBA", fnt, fill=(212, 175, 55), glow=(160, 130, 45))
        prts = Particles(40, seed=1)
        prts.update(t)
        prts.draw(img, alpha=0.8)
        return img.convert("RGB")
    encode(frames_for(2.0, scene), "/tmp/demo.mp4", total=60)
