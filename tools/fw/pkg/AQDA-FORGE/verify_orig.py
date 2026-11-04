#!/usr/bin/env python3
"""S1: byte-exact verification of known offsets in usb_EE5600FF.pkg (READ ONLY)."""
import hashlib, struct, sys

P = "usb_EE5600FF.pkg"

def hexdump(buf, base, width=16):
    out = []
    for i in range(0, len(buf), width):
        chunk = buf[i:i+width]
        h = " ".join(f"{b:02x}" for b in chunk)
        a = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        out.append(f"{base+i:012d} 0x{base+i:09x}  {h:<47}  |{a}|")
    return "\n".join(out)

f = open(P, "rb")
size = f.seek(0, 2)
print(f"path={P}")
print(f"size={size}")
h = hashlib.sha256()
f.seek(0)
while True:
    b = f.read(1 << 20)
    if not b:
        break
    h.update(b)
print(f"sha256={h.hexdigest()}")

def rd(abs_off, n):
    f.seek(abs_off)
    return f.read(n)

AQ0 = 80956104
AQHASH = 80991124
D3W = 80991123
USIG = 613234259
print("\n== aqda start / MtK8 header ==")
print(hexdump(rd(AQ0 - 16, 96), AQ0 - 16))
print("\n== 3rdw descriptor region (aqda rel 35019) ==")
print(hexdump(rd(D3W - 8, 96), D3W - 8))

name = rd(D3W, 4)
flags = struct.unpack("<I", rd(D3W + 4, 4))[0]
ln = struct.unpack("<I", rd(D3W + 8, 4))[0]
const = rd(D3W + 12, 16)
subhash = rd(D3W + 28, 32)
marker = rd(D3W + 60, 1)
data = D3W + 60
print("\n== 3rdw fields ==")
print(f"name={name!r} ({name.hex()})")
print(f"flags@{D3W+4}=0x{flags:08x} bytes={rd(D3W+4,4).hex()}")
print(f"len@{D3W+8}={ln} (0x{ln:x})")
print(f"const@{D3W+12}={const.hex()}")
print(f"subhash@{D3W+28}={subhash.hex()}")
print(f"marker@{D3W+60}=0x{marker.hex()} data@{data} end={data+ln}")

print("\n== next descriptor at end of 3rdw data ==")
print(hexdump(rd(data + ln - 8, 96), data + ln - 8))

print("\n== aqda hash region end / boundary ==")
print(hexdump(rd(AQHASH - 24, 48), AQHASH - 24))

print("\n== usig region ==")
print(hexdump(rd(USIG, 128), USIG))
print("...")
print(hexdump(rd(USIG + 256 - 16, 128), USIG + 240))
print("\n== trailer ==")
print(hexdump(rd(size - 96, 96), size - 96))

print("\n== aqda descriptor header (MtK8 image) first 64B ==")
print(hexdump(rd(AQ0, 64), AQ0))
n = rd(AQ0, 4)
alen = struct.unpack("<I", rd(AQ0 + 4, 4))[0]
print(f"magic={n!r} desc_len_le@{AQ0+4}={alen} (0x{alen:x}) -> hash end {AQ0+alen}")
print(f"hash_region=[{AQ0},{AQ0+alen}) length={alen}")
print(f"boundary bytes at end: {rd(AQ0+alen-4,12).hex()}")
f.close()
