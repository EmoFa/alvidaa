#!/usr/bin/env python3
"""Generate the alvidaa background wallpapers (abstract, dark, TV-safe).

Pure stdlib — writes 960x540 PNGs to launcher/bg/. Diagonal gradient + one
soft radial glow + light dithering noise so the TV's upscaler doesn't band.
"""
import math
import os
import random
import struct
import zlib

W, H = 960, 540
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "launcher", "bg")

THEMES = [
    {"top": (30, 52, 92), "bot": (8, 12, 22), "glow": (70, 160, 255)},    # deep blue
    {"top": (24, 66, 56), "bot": (6, 14, 18), "glow": (60, 220, 190)},    # teal
    {"top": (58, 38, 88), "bot": (14, 9, 20), "glow": (190, 110, 255)},   # dusk purple
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
    gx, gy, gr = W * 0.72, H * 0.3, H * 0.9  # glow center / radius
    for y in range(H):
        row = bytearray()
        t = y / H
        for x in range(W):
            u = (x / W + t) / 2  # diagonal blend
            r = theme["top"][0] * (1 - u) + theme["bot"][0] * u
            g = theme["top"][1] * (1 - u) + theme["bot"][1] * u
            b = theme["top"][2] * (1 - u) + theme["bot"][2] * u
            d = math.hypot(x - gx, y - gy) / gr
            glow = max(0.0, 1.0 - d) ** 2 * 0.6
            r += theme["glow"][0] * glow
            g += theme["glow"][1] * glow
            b += theme["glow"][2] * glow
            n = rnd.randint(-3, 3)  # dither
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
