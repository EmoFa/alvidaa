#!/usr/bin/env python3
"""Signature/checksum analysis for MediaTek .pkg (READ-ONLY)."""
import sys, os, hashlib, zlib, struct, mmap, binascii

A = "usb_EE5600FF.pkg"
B = "usb_EE5600FF.pkg"

def mm(path):
    f = open(path, 'rb')
    m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    return f, m

def hashes(data):
    return {
        'md5': hashlib.md5(data).digest(),
        'sha1': hashlib.sha1(data).digest(),
        'sha256': hashlib.sha256(data).digest(),
        'sha512': hashlib.sha512(data).digest(),
        'crc32': struct.pack('<I', zlib.crc32(data) & 0xFFFFFFFF),
    }

fa, ma = mm(A)
fb, mb = mm(B)

print("=== HEADER DIFF (0x00-0x200) A vs B ===")
diffs = []
for i in range(0x200):
    if ma[i] != mb[i]:
        diffs.append(i)
# group into ranges
print(f"total diff bytes in first 0x200: {len(diffs)}")
ranges = []
for d in diffs:
    if ranges and d == ranges[-1][1]+1:
        ranges[-1][1] = d
    else:
        ranges.append([d,d])
print("diff ranges:")
for r in ranges:
    print(f"  0x{r[0]:03X}-0x{r[1]:03X} ({r[1]-r[0]+1} bytes)")

print("\n=== 64B block 0x00-0x3F ===")
b64a, b64b = ma[0:0x40], mb[0:0x40]
print("A:", b64a.hex())
print("B:", b64b.hex())
print("identical:", b64a == b64b)

print("\n=== 80B block 0x40-0x8F ===")
b80a, b80b = ma[0x40:0x90], mb[0x40:0x90]
print("A:", b80a.hex())
print("B:", b80b.hex())
print("identical:", b80a == b80b)

# Candidate regions and their hashes
print("\n=== HASH CANDIDATE REGIONS (A) ===")
size_a = os.path.getsize(A)
mtk8_offs = [512, 41943676, 77391665, 78875832, 78880080, 80956104]
regions = {
    'whole_file': (0, size_a),
    'from_0x200': (512, size_a),
    'from_0x90': (0x90, size_a),
    'header_0x00_0x90': (0, 0x90),
    'header_0x00_0x40': (0, 0x40),
    'cfig_0x90_0x200': (0x90, 0x200),
    'parttable_0xCC_0x1C7': (0xCC, 0x1C7),
    'parttable_text': (0xCC, 0x1C7),
    'img1': (512, 41943676),
}
# add per-image regions (from MtK8 header start to next MtK8)
for i, o in enumerate(mtk8_offs):
    end = mtk8_offs[i+1] if i+1 < len(mtk8_offs) else (size_a - 256)  # up to trailer
    regions[f'image{i}_mtk8_{o}'] = (o, end)

# also image body = after 32-byte MtK8 header
for i, o in enumerate(mtk8_offs):
    end = mtk8_offs[i+1] if i+1 < len(mtk8_offs) else (size_a - 256)
    regions[f'image{i}_body'] = (o+32, end)

results = {}
for name, (s, e) in regions.items():
    data = ma[s:e]
    h = hashes(data)
    results[name] = (s, e, e-s, h)
    print(f"{name:28s} [{s:>10}-{e:>10}] len={e-s:>10} md5={h['md5'].hex()} crc32={h['crc32'].hex()}")

# Now search: do any hash digests appear in header (0x00-0x200)?
print("\n=== SEARCH: does any hash digest byte sequence appear in header 0x00-0x200? ===")
header_a = ma[0:0x200]
header_b = mb[0:0x200]
def search_digests(header, header_name):
    found = []
    for name, (s,e,ln,h) in results.items():
        for alg, dg in h.items():
            if dg in header:
                off = header.find(dg)
                found.append((name, alg, len(dg), off))
    return found

fa_ = search_digests(header_a, 'A')
print("matches in A header:")
for x in fa_: print("  ", x)

# Also check the 'af d2 12 17' constant vs crc32 of things
print("\n=== 'af d2 12 17' constant investigation ===")
const = bytes.fromhex('af d2 12 17')
print("constant af d2 12 17 appears at offsets in A:", [i for i in [0x9C,0x1CF] if ma[i:i+4]==const])
# find all occurrences of const in whole A file (first 100)
occ = []
start = 0
while True:
    i = ma.find(const, start)
    if i < 0: break
    occ.append(i)
    start = i+1
    if len(occ) > 200: break
print(f"occurrences of af d2 12 17 in A (first {len(occ)}): {occ[:60]}")

# CRC32 of partition table text?
pt = ma[0xCC:0x1C7]
print(f"crc32(partition_table_text 0xCC-0x1C7) = {zlib.crc32(pt)&0xFFFFFFFF:08X}")
print(f"crc32('START..END\\nspdt') whole incl nulls = {zlib.crc32(ma[0xCC:0x1CB])&0xFFFFFFFF:08X}")

# What region has crc32 == af d2 12 17 (0x1712D2AF)?
target_crc = 0x1712D2AF
print(f"\ntarget crc32 0x{target_crc:08X} - testing regions:")
for name,(s,e) in regions.items():
    c = zlib.crc32(ma[s:e]) & 0xFFFFFFFF
    mark = "  <<< MATCH" if c == target_crc else ""
    print(f"  crc32({name}) = 0x{c:08X}{mark}")

fa.close(); ma.close()
fb.close(); mb.close()
