#!/usr/bin/env python3
"""S4: outer aqda descriptor layout + digest identification (read-only)."""
import hashlib, struct
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

print("== aqda outer descriptor 80956032..80956112 ==")
hd(80956032, 80)
print("\nlayout read:")
ln = struct.unpack("<I", rd(80956051, 4))[0]
print(f"  @80956051 LE u32 = {ln}")
print(f"  @80956055 16B    = {rd(80956055,16).hex()}")
print(f"  @80956071 32B    = {rd(80956071,32).hex()}")
print(f"  @80956103 1B     = {rd(80956103,1).hex()}")

stored = rd(80956071, 32)
const = rd(80956055, 16)
print("\n== digest tests over aqda region ==")
region = rd(80956104, ln)
print(f"region len={len(region)} sha256={hashlib.sha256(region).hexdigest()}")
print(f"stored32              ={stored.hex()}")
print("stored==sha256(region):", stored == hashlib.sha256(region).digest())
print("const == md5(region)  :", const == hashlib.md5(region).digest())
print("const == md5(first 32):", const == hashlib.md5(region[:32]).digest())

for off in range(0, 9):
    for ln2 in (ln, ln - off, ln + 1, ln - 4, ln - 1):
        if ln2 <= 0: continue
        d = hashlib.sha256(rd(80956104 + off, ln2)).digest()
        if d == stored:
            print(f"MATCH sha256 start=+{off} len={ln2}")
for ln2 in (35016, 35020, 35019, 35024):
    d = hashlib.sha256(rd(80956104, ln2)).digest()
    print(f"  sha256 len={ln2}: {d.hex()[:16]}... match={d==stored}")

print("\n== 3rdw subhash vs SHA-256(data) ==")
D = 80991183; L = 339105136
h = hashlib.sha256(); f.seek(D)
left = L
while left:
    b = f.read(min(1 << 22, left))
    if not b: break
    h.update(b); left -= len(b)
print(f"sha256(3rdw data[{D},{D+L})) = {h.hexdigest()}")
print(f"stored 3rdw subhash           = {rd(80991151,32).hex()}")
print("match:", h.digest() == rd(80991151, 32))

print("\n== 32B hashes in descriptors ==")
for nm, off in (("3rdw", 80991123), ("3rdp", 420096319), ("rtfs", 568064443),
                ("kern", 608926263), ("usig", 613234259)):
    print(f"{nm}: flags={struct.unpack('<I',rd(off+4,4))[0]:#x} len={struct.unpack('<I',rd(off+8,4))[0]} "
          f"hash={rd(off+28,32).hex()}")
f.close()
