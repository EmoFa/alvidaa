#!/usr/bin/env python3
"""Generate the per-input placeholder assets (backgrounds + logos).

Pure stdlib — writes small PNGs to launcher/next/assets/. These are the two
review placeholders for the input-asset layer (issue #34): one neutral set
and one obviously-different set, so the cross-fade + logo mechanism can be
screened without waiting for real art. Real art later drops into the same
paths (or anywhere the launcher dir can serve) and config.inputs points at
them via the 'bg' / 'logo' fields.

Neutral set: 960x540 near-black wash with a faint horizontal breath — reads
as "no art yet" next to the dark-glass page. Distinct set: deep amber with a
diagonal sweep, impossible to confuse with the default wallpaper even on a
bad TV panel. Logos are 128x128 wordmark chips ("IN 1" / "IN 2") drawn as
blocky glyphs — placeholder quality by design, not vendored art.
"""
import math
import os
import struct
import zlib

W, H = 960, 540
LOGO = 128
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "launcher", "next", "assets")


def png(path, w, h, rows):
    # rows: list of bytearrays, one per row, RGB triplets
    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    hdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", hdr))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def bg_rows(base, glow, sweep):
    rows = []
    for y in range(H):
        row = bytearray()
        v = y / (H - 1)
        for x in range(W):
            u = x / (W - 1)
            # vertical breath + one diagonal sweep + one radial glow
            col = lerp(base, tuple(int(c * 1.5) for c in base), 0.5 + 0.5 * math.sin(v * math.pi))
            d = (u + v) % 1.0
            col = lerp(col, sweep, max(0.0, 0.35 - abs(d - 0.5) * 1.6))
            g = math.hypot(u - 0.72, v - 0.3)
            col = lerp(col, glow, max(0.0, 0.30 - g * 0.55))
            row.extend(col)
        rows.append(row)
    return rows


def logo_rows(chip, text_px):
    # blocky 128x128 chip with a 2-glyph "IN" mark + index dot
    rows = []
    for y in range(LOGO):
        row = bytearray()
        for x in range(LOGO):
            col = chip
            # rounded-corner chip mask
            dx, dy = min(x, LOGO - 1 - x), min(y, LOGO - 1 - y)
            if dx + dy < 10:
                col = tuple(int(c * 0.35) for c in chip)
            # the "IN" mark: two vertical bars + a diagonal (blocky N)
            if 34 <= x < 50 and 44 <= y < 84:
                col = (238, 242, 247)
            if 58 <= x < 74 and 44 <= y < 84:
                col = (238, 242, 247)
                # carve the N's diagonal
                if 58 + (y - 44) * 16 // 40 <= x < 58 + (y - 44) * 16 // 40 + 6:
                    col = chip
            # index dot: top-right, lights up for the distinct set
            if text_px and 96 <= x < 112 and 16 <= y < 32:
                col = text_px
            row.extend(col)
        rows.append(row)
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    # neutral: quiet slate, barely off the page base (#0d1017-ish)
    png(os.path.join(OUT, "bg-neutral.png"), W, H,
        bg_rows((13, 16, 23), (38, 46, 60), (20, 25, 34)))
    # distinct: deep amber — unmistakable against every wallpaper we ship
    png(os.path.join(OUT, "bg-distinct.png"), W, H,
        bg_rows((64, 34, 6), (196, 120, 32), (120, 62, 10)))
    # logos: same chip, the distinct one carries the lit index dot
    png(os.path.join(OUT, "logo-neutral.png"), LOGO, LOGO,
        logo_rows((30, 37, 50), None))
    png(os.path.join(OUT, "logo-distinct.png"), LOGO, LOGO,
        logo_rows((120, 62, 10), (245, 158, 11)))
    for f in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, f)
        print(f"{f}: {os.path.getsize(p)} bytes")


if __name__ == "__main__":
    main()
