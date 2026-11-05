#!/usr/bin/env python3
"""Generate the alvidaa background wallpapers (abstract, dark, TV-safe).

Pure stdlib — writes 1920x1080 PNGs to launcher/bg/. Diagonal gradient +
two soft radial glows + light dithering noise so the TV's upscaler doesn't
band. Dark-glass tuning: the launcher page (#07080c base) dims wallpapers
at 0.6 and adds its own vignette, so peaks stay quiet — glows echo the
page's own ambient bloom palette (steel blue / indigo / teal) at ~10-15%
of the old v1 brightness.
"""
import math
import os
import random
import struct
import zlib

W, H = 1920, 1080
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "launcher", "bg")

THEMES = [
    # base sits just above #07080c; glow peaks stay under ~25% channel lift
    {"top": (11, 16, 24), "bot": (6, 7, 11), "glow": (44, 86, 130),   # steel blue
     "glow2": (26, 44, 66)},
    {"top": (12, 13, 22), "bot": (6, 7, 11), "glow": (72, 74, 140),   # indigo
     "glow2": (40, 40, 78)},
    {"top": (9, 17, 20), "bot": (5, 8, 10), "glow": (36, 110, 118),   # teal slate
     "glow2": (22, 64, 66)},
]

def png(rows):
    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))

def render(theme, seed):
    rnd = random.Random(seed)
    rows = []
    gx, gy, gr = W * 0.72, H * 0.3, H * 0.9  # primary glow center / radius
    gx2, gy2, gr2 = W * 0.18, H * 0.85, H * 0.7  # counter-glow, low corner
    for y in range(H):
        row = bytearray()
        t = y / H
        for x in range(W):
            u = (x / W + t) / 2  # diagonal blend
            r = theme["top"][0] * (1 - u) + theme["bot"][0] * u
            g = theme["top"][1] * (1 - u) + theme["bot"][1] * u
            b = theme["top"][2] * (1 - u) + theme["bot"][2] * u
            d = math.hypot(x - gx, y - gy) / gr
            glow = max(0.0, 1.0 - d) ** 2 * 0.45
            r += theme["glow"][0] * glow
            g += theme["glow"][1] * glow
            b += theme["glow"][2] * glow
            d2 = math.hypot(x - gx2, y - gy2) / gr2
            glow2 = max(0.0, 1.0 - d2) ** 2 * 0.3
            r += theme["glow2"][0] * glow2
            g += theme["glow2"][1] * glow2
            b += theme["glow2"][2] * glow2
            n = rnd.randint(-2, 2)  # dither
            row += bytes(max(0, min(255, int(v) + n)) for v in (r, g, b))
        rows.append(row)
    return rows

def main():
    os.makedirs(OUT, exist_ok=True)
    for i, th in enumerate(THEMES, 1):
        path = os.path.join(OUT, f"bg{i}.png")
        with open(path, "wb") as f:
            f.write(png(render(th, i)))
        print(path, os.path.getsize(path), "bytes")

if __name__ == "__main__":
    main()
