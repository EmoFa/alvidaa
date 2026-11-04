#!/usr/bin/env python3
"""Static analysis of MediaTek .pkg files (READ-ONLY)."""
import sys, hashlib, struct, os

def find_all(data, needle):
    offs = []
    start = 0
    while True:
        i = data.find(needle, start)
        if i < 0:
            break
        offs.append(i)
        start = i + 1
    return offs

def crc32(data):
    import zlib
    return zlib.crc32(data) & 0xFFFFFFFF

def fmt_hash(name, data, region=None):
    h = hashlib.new(name, data).hexdigest()
    return h

def main(path):
    size = os.path.getsize(path)
    print(f"FILE={path}")
    print(f"SIZE={size} (0x{size:X})")
    with open(path, 'rb') as f:
        import mmap
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

        # Magic offsets
        magics = [b'MtK8', b'cfig', b'START', b'END\n', b'USB_UPG_VERSION', b'iPAd', b'MTK', b'USIG', b'STAR', b'spdt']
        print("\n=== MAGIC OFFSETS ===")
        for m in magics:
            offs = find_all(mm, m)
            print(f"{m!r}: {len(offs)} hits -> {offs[:40]}")

        # Trailer
        print("\n=== TRAILER (last 256) ===")
        tr = mm[size-256:size]
        print("trailer hex:")
        for i in range(0, 256, 16):
            chunk = tr[i:i+16]
            print(f"  {size-256+i:08x}: {chunk.hex(' ')}  {''.join(chr(c) if 32<=c<127 else '.' for c in chunk)}")

        # Header 0x00-0x200
        print("\n=== HEADER 0x00-0x200 ===")
        hd = mm[0:0x200]
        for i in range(0, 0x200, 16):
            chunk = hd[i:i+16]
            print(f"  {i:08x}: {chunk.hex(' ')}  {''.join(chr(c) if 32<=c<127 else '.' for c in chunk)}")

        # 64-byte and 80-byte blocks
        print("\n=== BLOCKS ===")
        b64 = mm[0:0x40]
        b80 = mm[0x40:0x90]
        print(f"0x00-0x3F (64B) sha256={hashlib.sha256(b64).hexdigest()}")
        print(f"0x40-0x8F (80B) sha256={hashlib.sha256(b80).hexdigest()}")

        # Parse partition table from 0xCC
        print("\n=== PARTITION TABLE TEXT (from START magic) ===")
        start = mm.find(b'START\n')
        end = mm.find(b'END\n', start)
        ptext = mm[start:end+4].decode('latin1', 'replace')
        print(repr(ptext))

        # Parse cfig length field at 0x98
        print("\n=== cfig chunk parse ===")
        print(f"0x90 'cfig' magic + 0x94 u32(0) + 0x98 u32={struct.unpack('<I', mm[0x98:0x9C])[0]} (0x{struct.unpack('<I', mm[0x98:0x9C])[0]:X})")
        print(f"0x9C 4B: {mm[0x9C:0xA0].hex(' ')}")
        print(f"0xA0 16B: {mm[0xA0:0xB0].hex(' ')}")
        print(f"0xB0 16B: {mm[0xB0:0xC0].hex(' ')}")
        print(f"0xC0 12B: {mm[0xC0:0xCC].hex(' ')}")

        mm.close()

if __name__ == '__main__':
    main(sys.argv[1])
