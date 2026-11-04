#!/usr/bin/env python3
"""Examine MtK8 image boundaries + surrounding bytes (READ-ONLY)."""
import sys, hashlib, struct, os, mmap

def dump(path, mtk8_offs):
    size = os.path.getsize(path)
    with open(path,'rb') as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        for o in mtk8_offs:
            print(f"\n===== MtK8 @ 0x{o:X} ({o}) =====")
            # 64 bytes before
            pre = mm[o-64:o]
            print(f"-- 64B BEFORE (0x{o-64:X}) --")
            for i in range(0,64,16):
                c = pre[i:i+16]
                print(f"  {o-64+i:08x}: {c.hex(' ')}  {''.join(chr(x) if 32<=x<127 else '.' for x in c)}")
            # 64 bytes at header
            hdr = mm[o:o+64]
            print(f"-- 64B HEADER --")
            for i in range(0,64,16):
                c = hdr[i:i+16]
                print(f"  {o+i:08x}: {c.hex(' ')}  {''.join(chr(x) if 32<=x<127 else '.' for x in c)}")
        # trailer before MtK8 area (trailer is last 256)
        print(f"\n===== FILE TRAILER (last 256B @ 0x{size-256:X}) =====")
        tr = mm[size-256:size]
        for i in range(0,256,16):
            c = tr[i:i+16]
            print(f"  {size-256+i:08x}: {c.hex(' ')}  {''.join(chr(x) if 32<=x<127 else '.' for x in c)}")
        mm.close()

if __name__ == '__main__':
    dump(sys.argv[1], [512, 41943676, 77391665, 78875832, 78880080, 80956104])
