#!/usr/bin/env python3
"""Definitive SHA-256 match test for descriptor hash fields and 80B block."""
import hashlib, struct, os, mmap, itertools

A = "usb_EE5600FF.pkg"
B = "usb_EE5600FF.pkg"
MTK8 = [512, 41943676, 77391665, 78875832, 78880080, 80956104]

def analyze(path, tag):
    f = open(path,'rb'); m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    size = os.path.getsize(path)
    results = []

    # per-image descriptor var (32-byte sha256 candidate + 0x69)
    for i,o in enumerate(MTK8):
        name_off = 0x1C3 if o==512 else o-61
        var = m[name_off+28: name_off+61]
        sha_cand = var[0:32]
        tail = var[32:33]
        results.append((i, sha_cand, tail, name_off))
        print(f"[{tag}] img{i} sha256_cand={sha_cand.hex()} tail={tail.hex()}")

    # Build candidate content regions for each image
    print(f"\n[{tag}] === SHA256 content-region match ===")
    for i,o in enumerate(MTK8):
        nxt = MTK8[i+1] if i+1 < len(MTK8) else (size-256)
        sha_cand = results[i][1]
        # candidate content boundaries
        bounds = []
        for hdr in (0, 32, 63, 64):
            for ft in (0, 61, 64, 61+3, 64+3):
                s = o + hdr
                e = nxt - ft
                if 0 < s < e <= size:
                    bounds.append((s,e,f'hdr={hdr} foot={ft}'))
        # also full span including next MtK8 header
        for (s,e,desc) in bounds:
            h = hashlib.sha256(m[s:e]).digest()
            if h == sha_cand:
                print(f"   img{i} SHA256[{s}-{e}] ({desc}) == candidate  <<< MATCH")
            # also try sha256 over name+region etc
        # try sha256 of name+content, length+content
        name = m[results[i][3]:results[i][3]+4]
        for (s,e,desc) in bounds:
            for prefix in (b'', name, name + b'\x00\x00\x00\x00'):
                h = hashlib.sha256(prefix + m[s:e]).digest()
                if h == sha_cand:
                    print(f"   img{i} SHA256(prefix+[{s}-{e}]) ({desc}) == candidate <<< MATCH")

    # 80B block analysis
    b80 = m[0x40:0x90]
    b64 = m[0:0x40]
    print(f"\n[{tag}] === 80B block analysis ===")
    print(f"  80B[0:32]  = {b80[0:32].hex()}")
    print(f"  80B[32:64] = {b80[32:64].hex()}")
    print(f"  80B[64:80] = {b80[64:80].hex()}")
    print(f"  64B block  = {b64.hex()}")

    # candidate regions for the 80B/64B block
    regs = {
        'whole': (0,size),
        'from_0x90': (0x90,size),
        'cfig_0x90_0x200': (0x90,0x200),
        'pt_0xCC_0x1C7': (0xCC,0x1C7),
        'header_0_0x90': (0,0x90),
        'from_0x200': (0x200,size),
    }
    print(f"[{tag}] searching if 80B or 64B block contains SHA256/MD5/SHA1 of regions:")
    for rname,(s,e) in regs.items():
        data = m[s:e]
        d = {
            'sha256': hashlib.sha256(data).digest(),
            'md5': hashlib.md5(data).digest(),
            'sha1': hashlib.sha1(data).digest(),
            'sha512': hashlib.sha512(data).digest(),
        }
        for alg, dg in d.items():
            if dg in b80:
                print(f"   {alg}({rname}) FOUND in 80B block at {b80.find(dg)}")
            if dg in b64:
                print(f"   {alg}({rname}) FOUND in 64B block")
    # is 80B[0:64] a sha512? or 80B == sha512+md5?
    for rname,(s,e) in regs.items():
        data = m[s:e]
        sha512 = hashlib.sha512(data).digest()
        md5 = hashlib.md5(data).digest()
        if b80 == sha512+md5:
            print(f"   80B == sha512+md5({rname})  <<< MATCH")
        if b80[0:64] == sha512:
            print(f"   80B[0:64] == sha512({rname})  <<< MATCH")
        if b80[64:80] == md5:
            print(f"   80B[64:80] == md5({rname})  <<< MATCH")
    f.close(); m.close()
    return results

print("########## A ##########")
analyze(A, 'A')
print("\n########## B ##########")
analyze(B, 'B')
