#!/usr/bin/env python3
"""Efficient SHA-256 match (cached, streaming for big regions)."""
import hashlib, os, mmap

A = "usb_EE5600FF.pkg"
B = "usb_EE5600FF.pkg"
MTK8 = [512, 41943676, 77391665, 78875832, 78880080, 80956104]

def sha256_file_range(path, s, e):
    with open(path,'rb') as f:
        f.seek(s)
        h = hashlib.sha256()
        remaining = e - s
        while remaining > 0:
            chunk = f.read(min(1<<20, remaining))
            if not chunk: break
            h.update(chunk)
            remaining -= len(chunk)
        return h.hexdigest()

def analyze(path, tag):
    size = os.path.getsize(path)
    f = open(path,'rb'); m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

    for i,o in enumerate(MTK8):
        name_off = 0x1C3 if o==512 else o-61
        var = m[name_off+28: name_off+61]
        sha_cand = var[0:32].hex()
        nxt = MTK8[i+1] if i+1 < len(MTK8) else (size-256)
        # candidate content regions
        cands = {}
        cands['h32_f61'] = (o+32, nxt-61)      # MtK8 hdr 32, footer 61
        cands['h63_f61'] = (o+63, nxt-61)      # +31 pad, footer 61
        cands['h32_f64'] = (o+32, nxt-64)
        cands['h63_f64'] = (o+63, nxt-64)
        cands['h32_f0']  = (o+32, nxt)
        cands['h63_f0']  = (o+63, nxt)
        cands['h32_len'] = (o+32, o+32+struct_len(i,o,m))
        hit = None
        for cname,(s,e) in cands.items():
            if not (0 < s < e <= size): continue
            if sha256_file_range(path,s,e) == sha_cand:
                hit = cname
                print(f"[{tag}] img{i} ({m[name_off:name_off+4].decode('latin1')}) SHA256[{s}-{e}] len={e-s} ({cname}) == candidate  <<< MATCH")
        if not hit:
            print(f"[{tag}] img{i} ({m[name_off:name_off+4].decode('latin1')}) NO match. candidate={sha_cand}")
            # print lengths for reference
            for cname,(s,e) in cands.items():
                if 0<s<e<=size:
                    print(f"       {cname}: [{s}-{e}] len={e-s}")
    f.close(); m.close()

def struct_len(i,o,m):
    name_off = 0x1C3 if o==512 else o-61
    import struct
    return struct.unpack('<I', m[name_off+8:name_off+12])[0]

print("########## A ##########")
analyze(A,'A')
print("\n########## B ##########")
analyze(B,'B')
