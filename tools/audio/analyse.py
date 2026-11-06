#!/usr/bin/env python3
"""Report whether a raw S16_LE capture contains real audio or silence.

Usage: analyse.py cap.raw [channels] [rate]

The probe already prints peak/RMS, but a second opinion on the pulled file
catches the case where the device returned data that is not silence but also
not the programme (a dead carrier, a DC offset, or a decoder tap that is
running but muted upstream).
"""
import struct
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 2
    path = sys.argv[1]
    channels = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    rate = int(sys.argv[3]) if len(sys.argv) > 3 else 48000

    with open(path, "rb") as f:
        data = f.read()
    n = len(data) // 2
    if n == 0:
        print("empty capture")
        return 1

    samples = struct.unpack("<%dh" % n, data[: n * 2])
    peak = max(abs(s) for s in samples)
    mean = sum(samples) / n
    rms = (sum(s * s for s in samples) / n) ** 0.5
    frames = n // channels
    secs = frames / rate

    # crude DC-offset check: a stuck device often returns a constant value
    distinct = len(set(samples[: min(n, 200000)]))

    print(f"file      {path}")
    print(f"frames    {frames} ({secs:.2f}s @ {rate}Hz, {channels}ch)")
    print(f"peak      {peak} / 32767")
    print(f"rms       {rms:.1f}")
    print(f"dc offset {mean:.1f}")
    print(f"distinct  {distinct} sample values")

    if peak == 0:
        print("\nVERDICT: digital silence. Nothing was playing, or this PCM is "
              "not the output mix.")
        return 1
    if distinct <= 2:
        print("\nVERDICT: constant value, not audio. The device opened but is "
              "not carrying a signal.")
        return 1
    if rms < 20:
        print("\nVERDICT: near-silence. Something is there but very quiet — "
              "check whether the TV volume or a mute is upstream of the tap.")
        return 0
    print("\nVERDICT: real audio. This PCM carries a signal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
