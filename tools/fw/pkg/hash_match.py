#!/usr/bin/env python3
"""Brute-force hash match: try to identify what the 80-byte block and
per-image descriptor hash fields cover (READ-ONLY)."""
import hashlib, zlib, struct, os, mmap

A = "usb_EE5600FF.pkg"
B = "usb_EE5600FF.pkg"

def compute(data):
    return {
        'md5': hashlib.md5(data).hexdigest(),
        'sha1': hashlib.sha1(data).hexdigest(),
        'sha256': hashlib.sha256(data).hexdigest(),
        'sha512': hashlib.sha512(data).hexdigest(),
        'crc32': f"{zlib.crc32(data)&0xFFFFFFFF:08x}",
    }

def compute_digest(data):
    return {
        'md5': hashlib.md5(data).digest(),
        'sha1': hashlib.sha1(data).digest(),
        'sha256': hashlib.sha256(data).digest(),
        'sha512': hashlib.sha512(data).digest(),
        'crc32': struct.pack('<I', zlib.crc32(data)&0xFFFFFFFF),
    }

MTK8 = [512, 41943676, 77391665, 78875832, 78880080, 80956104]

def analyze(path, tag):
    f = open(path,'rb')
    m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    size = os.path.getsize(path)

    b80 = m[0x40:0x90]
    b64 = m[0:0x40]

    # Regions
    regions = {}
    regions['whole'] = (0, size)
    regions['from_0x90'] = (0x90, size)
    regions['from_0x200'] = (0x200, size)
    regions['header_0_0x90'] = (0, 0x90)
    regions['cfig_0x90_0x200'] = (0x90, 0x200)
    regions['pt_0xCC_0x1C7'] = (0xCC, 0x1C7)
    regions['header_0_0x40'] = (0, 0x40)
    for i,o in enumerate(MTK8):
        end = MTK8[i+1] if i+1 < len(MTK8) else size-256
        regions[f'img{i}_full'] = (o, end)
        regions[f'img{i}_body'] = (o+32, end)

    # Extract per-image descriptors (61 bytes before each MtK8, name at -61)
    descriptors = {}
    for i,o in enumerate(MTK8):
        if o == 512:
            # first descriptor: name 'spdt' at 0x1C3
            name_off = 0x1C3
        else:
            name_off = o - 61
        desc = m[name_off:o]
        name = desc[0:4]
        flags = desc[4:8]
        length = desc[8:12]
        const16 = desc[12:28]  # af d2 12 17 + 6b 6d ...
        var = desc[28:61]      # 33 bytes variable
        descriptors[i] = dict(name=name, flags=flags, length=length,
                              const16=const16, var=var, name_off=name_off)
        print(f"[{tag}] image{i} name={name!r} flags={flags.hex()} "
              f"len_le=0x{struct.unpack('<I',length)[0]:08X} "
              f"const16={const16.hex()} var({len(var)}B)={var.hex()}")

    print(f"\n[{tag}] 64B block 0x00-0x3F: {b64.hex()}")
    print(f"[{tag}] 80B block 0x40-0x8F: {b80.hex()}")

    # Try to match each descriptor's variable bytes (33B) and the 80B block
    # against hashes of regions.
    print(f"\n[{tag}] === HASH MATCH TESTS ===")
    digests = {rname: compute_digest(m[s:e]) for rname,(s,e) in regions.items()}
    # also hex strings
    hexstrings = {rname: compute(m[s:e]) for rname,(s,e) in regions.items()}

    # Test 80B block: is it SHA512+MD5 concat? or contains any digest?
    print(f"[{tag}] 80B block decomposition tests:")
    for rname, dg in digests.items():
        sha512 = dg['sha512']  # 64B
        md5 = dg['md5']        # 16B
        if b80 == sha512 + md5:
            print(f"   80B == sha512+md5 of {rname}  <<< MATCH")
        if b80[:64] == sha512:
            print(f"   80B[0:64] == sha512 of {rname}  <<< MATCH")
        if b80[:32] == dg['sha256']:
            print(f"   80B[0:32] == sha256 of {rname}  <<< MATCH")
        if b80[:16] == md5:
            print(f"   80B[0:16] == md5 of {rname}  <<< MATCH")
        if b80[:20] == dg['sha1']:
            print(f"   80B[0:20] == sha1 of {rname}  <<< MATCH")
        if b80[:4] == dg['crc32']:
            print(f"   80B[0:4] == crc32 of {rname}  <<< MATCH")

    # Check descriptor variable bytes (33B) against hashes
    print(f"[{tag}] descriptor var-byte match tests:")
    for i, d in descriptors.items():
        var = d['var']
        # find which image body region it might cover
        for rname, dg in digests.items():
            for alg, db in dg.items():
                if db in var:
                    print(f"   img{i} var contains {alg} of {rname}  <<< MATCH")
                if var in db:
                    print(f"   img{i} var is SUBSTRING of {alg}({rname})")

    # Also: is the 64B block (fixed) a known constant? print raw
    f.close(); m.close()
    return descriptors

print("################ FILE A ################")
analyze(A, 'A')
print("\n################ FILE B ################")
analyze(B, 'B')
