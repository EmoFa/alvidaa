#!/usr/bin/env python3
"""S3: aqda header layout, boundary bytes, hash-length field hunt, usig data dump."""
import struct
P = "usb_EE5600FF.pkg"
f = open(P, "rb")
def rd(o, n):
    f.seek(o); return f.read(n)
def hd(o, n, w=16):
    b = rd(o, n)
    for i in range(0, len(b), w):
        c = b[i:i+w]
        print(f"0x{o+i:09x}  " + " ".join(f"{x:02x}" for x in c).ljust(47) +
              "  |" + "".join(chr(x) if 32 <= x < 127 else "." for x in c) + "|")
    return b

print("== aqda mtk8 header, first 0x180 ==")
h = hd(80956104, 0x180)
print("\nprintable runs in first 0x1200 of aqda:")
b = rd(80956104, 0x1200)
cur = bytearray(); start = 0
for i, x in enumerate(b):
    if 32 <= x < 127:
        if not cur: start = i
        cur.append(x)
    else:
        if len(cur) >= 6:
            print(f"  0x{80956104+start:09x} +{start}: {cur.decode()}")
        cur = bytearray()
if len(cur) >= 6:
    print(f"  0x{80956104+start:09x} +{start}: {cur.decode()}")

print("\n== tail of aqda header region: 80990848..80991144 ==")
hd(80990848, 0x120)

print("\n== hunt for 35020/35019 near aqda ==")
seg = rd(80950000, 50000)
for val in (35020, 35019):
    for endian, tag in (("<", "LE"), (">", "BE")):
        pat = struct.pack(endian + "I", val)
        offs = []; i = seg.find(pat)
        while i != -1:
            offs.append(80950000 + i); i = seg.find(pat, i + 1)
        print(f"  {tag} {val}: {[hex(x) for x in offs]}")

print("\n== top-level 0x200 header vs aqda 80956104 (first 64) ==")
a = rd(0x200, 64); c = rd(80956104, 64)
print("identical64:", a == c)
print("0x200 :", a.hex())
print("80956104:", c.hex())

print("\n== usig data 512 B (613234319..613234831) ==")
u = hd(613234319, 512)
print("printable runs >=4 in usig data:")
cur = bytearray(); start = 0
for i, x in enumerate(u):
    if 32 <= x < 127:
        if not cur: start = i
        cur.append(x)
    else:
        if len(cur) >= 4:
            print(f"  +{start} (abs {613234319+start}): {cur.decode()}")
        cur = bytearray()

print("\n== usig descriptor header 60 B ==")
hd(613234259, 60)
print("flags/len:", struct.unpack("<II", rd(613234263, 8)))
print("const:", rd(613234271, 16).hex())
print("subhash:", rd(613234287, 32).hex())
print("first byte of data:", rd(613234319, 1).hex())

print("\n== 3rdw subhash present elsewhere? (search whole header region 80956104..80991124) ==")
sub = bytes.fromhex("9d7ee826b24168dcbc42775514503aae6fb3d38a3299e60c64a76b04ff78f3fc")
hdr = rd(80956104, 35020)
i = hdr.find(sub)
print("3rdw subhash offset in header:", i if i >= 0 else "NOT FOUND")
const = bytes.fromhex("afd212176b6d06a8b888fcf5f0198ece")
print("const occurrences in header:", hdr.count(const))

print("\n== 3rdw flags/len patterns in header ==")
print("bytes 01 01 00 00 count:", hdr.count(bytes.fromhex("01010000")))
print("len LE 70 55 36 14 count:", hdr.count(bytes.fromhex("70553614")))
f.close()
