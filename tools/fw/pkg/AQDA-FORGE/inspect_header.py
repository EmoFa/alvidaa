#!/usr/bin/env python3
"""S2: dump pkg header/partition table, locate 35020/35019, verify descriptor chain."""
import struct

P = "usb_EE5600FF.pkg"
f = open(P, "rb")

def hexdump(buf, base, width=16):
    for i in range(0, len(buf), width):
        c = buf[i:i+width]
        print(f"0x{base+i:09x}  " + " ".join(f"{b:02x}" for b in c).ljust(47) +
              "  |" + "".join(chr(b) if 32 <= b < 127 else "." for b in c) + "|")

def rd(o, n):
    f.seek(o); return f.read(n)

print("== header 0x000..0x200 ==")
hexdump(rd(0, 0x200), 0)

print("\n== partition table around 0xCC ==")
hexdump(rd(0xC0, 0x180), 0xC0)

# locate 0x88cc / 0x88cb (35020/35019) in first 1 MiB
head = rd(0, 1 << 20)
for val in (35020, 35019):
    pat = struct.pack("<I", val)
    offs = []
    i = head.find(pat)
    while i != -1 and len(offs) < 8:
        offs.append(i); i = head.find(pat, i + 1)
    print(f"LE u32 {val} (0x{val:x}) in first 1MiB at: {offs}")
    patb = struct.pack(">I", val)
    offs = []
    i = head.find(patb)
    while i != -1 and len(offs) < 8:
        offs.append(i); i = head.find(patb, i + 1)
    print(f"BE u32 {val} (0x{val:x}) in first 1MiB at: {offs}")

print("\n== bytes before aqda MtK8 (80956064..80956128) ==")
hexdump(rd(80956064, 64), 80956064)

# Walk the subpartition table inside aqda using claimed format
print("\n== descriptor walk from 80991123 (name/flags/len/const/subhash/marker) ==")
pos = 80991123
for k in range(6):
    hdr = rd(pos, 60)
    name = hdr[0:4]
    if not all(32 <= b < 127 for b in name):
        print(f"[{k}] @{pos}: non-ascii name {name.hex()} -> stop"); break
    flags, ln = struct.unpack("<II", hdr[4:12])
    const = hdr[12:28].hex()
    print(f"[{k}] name={name.decode()} @{pos} flags=0x{flags:08x} len={ln} data@{pos+60} "
          f"end={pos+60+ln} const={const}")
    pos = pos + 60 + ln

# investigate header fields of aqda / global for length semantics
print("\n== 'MtK8' occurrences in first 100MB region (first 32) ==")
pos = 0; hits = []
while True:
    f.seek(pos); b = f.read(1 << 20)
    if not b: break
    i = b.find(b"MtK8")
    while i != -1:
        hits.append(pos + i); i = b.find(b"MtK8", i + 1)
    pos += len(b)
    if pos > 90000000: break
for h in hits[:32]:
    print(f"  MtK8 @ {h} (0x{h:x}) next8={rd(h+4,8).hex()}")

print("\n== sanity: aqda hash region span ==")
print("aqda start 80956104, 3rdw desc 80991123, delta =", 80991123 - 80956104)
print("given hash len 35020 -> end", 80956104 + 35020, "given end 80991124")
print("last 8 bytes before end:", rd(80991116, 8).hex())
f.close()
