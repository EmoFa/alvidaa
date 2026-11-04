#!/usr/bin/env python3
# AP-USIG-UENV / script 1: usig blob + trailer mapping (READ-ONLY, static)
import hashlib, math, mmap, struct, sys, os

A = "usb_EE5600FF.pkg"
B = "usb_EE5600FF.pkg"
CONST12 = bytes.fromhex("6b6d06a8b888fcf5f0198ece")

def entropy(b):
    if not b: return 0.0
    c = [0]*256
    for x in b: c[x]+=1
    n=len(b)
    return -sum((k/n)*math.log2(k/n) for k in c if k)

def hx(b):
    return b.hex()

def dump(b, base, width=16, maxrows=40):
    out=[]
    for i in range(0, min(len(b), width*maxrows), width):
        chunk=b[i:i+width]
        asc="".join(chr(x) if 32<=x<127 else "." for x in chunk)
        out.append(f"{base+i:12d} 0x{base+i:09X}  {chunk.hex(' '):<{width*3}} |{asc}|")
    if len(b) > width*maxrows:
        out.append(f"... ({len(b)-width*maxrows} more bytes)")
    return "\n".join(out)

for path, tag in ((A,"A/M0610"),(B,"B/E011_M0111")):
    size=os.path.getsize(path)
    with open(path,"rb") as f:
        mm=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
        # locate descriptor marker in last 4096 B
        win=mm[size-4096:size]
        idx=win.rfind(CONST12)
        d=size-4096+idx-16
        name=mm[d:d+4]; flags=struct.unpack("<I",mm[d+4:d+8])[0]
        ln=struct.unpack("<I",mm[d+8:d+12])[0]; h=mm[d+28:d+60]
        data=d+60
        blob=mm[data:data+256]
        trailer=mm[data+256:data+512]
        print(f"===== {tag} size={size} sha256(file)={hashlib.sha256(mm).hexdigest()}")
        print(f"descriptor @ {d} (0x{d:X}) name={name!r} flags={flags:#x} len={ln}")
        print(f"descriptor hash32={hx(h)}")
        print(f"usig data @ {data} (0x{data:X}) .. {data+ln} (0x{data+ln:X}); blob256 @ {data}; trailer256 @ {data+256}")
        print(f"file end @ {size}; 'MTK' positions in blob+trailer: {[data+i for i in range(len(blob)+len(trailer)-2) if mm[data+i:data+i+3]==b'MTK']}")
        print(f"entropy blob={entropy(blob):.4f} trailer={entropy(trailer):.4f} blob_first_byte={blob[0]:#04x} blob_last_byte={blob[-1]:#04x}")
        print(f"blob as 8x32: " + " ".join(hx(blob[i:i+32]) for i in range(0,256,32)))
        print(f"blob parity: last_byte={blob[-1]:#04x} even={blob[-1]%2==0} top_bit={blob[0]>>7}")
        print(f"blob 128B halves: [{hx(blob[:16])}..][{hx(blob[128:144])}..]")
        print(f"trailer nonzero byte offsets (rel to trailer): {[(i,trailer[i]) for i in range(256) if trailer[i]]}")
        print(f"trailer hex: {hx(trailer)}")
        print(f"trailer ascii: {''.join(chr(x) if 32<=x<127 else '.' for x in trailer)}")
        print("--- blob 256 B hexdump ---")
        print(dump(blob,data,16,16))
        print("--- trailer 256 B hexdump ---")
        print(dump(trailer,data+256,16,16))
        # 32B chunk set for hash matching
        chunks={blob[i:i+32]:f"blob[{i}:{i+32}]" for i in range(0,256,32)}
        mv=memoryview(mm)
        # candidate region hashes (memoryview -> no 613MB copies)
        cands={
          "file[0:end]": (0,size),
          "file[0:usig_desc]": (0,d),
          "file[0:usig_data]": (0,data),
          "file[0:blob_end]": (0,data+256),
          "file[0x00:end-256]": (0,size-256),
          "file[0x40:end-256]": (0x40,size-256),
          "file[0x90:end-256]": (0x90,size-256),
          "file[0x200:end-256]": (0x200,size-256),
          "file[0x00:blob_start]": (0,data),
          "trailer256": (data+256,data+512),
          "hdr[0x00:0x40]": (0,0x40),
          "hdr[0x40:0x90]": (0x40,0x90),
          "hdr[0x00:0x90]": (0,0x90),
          "hdr[0x00:0x200]": (0,0x200),
          "hdr[0x90:0x200]": (0x90,0x200),
          "desc60": (d,d+60),
        }
        for nm,(s,e) in cands.items():
            dh=hashlib.sha256(mv[s:e]).digest()
            hit=chunks.get(dh)
            print(f"SHA256 {nm:<24} = {dh.hex()[:32]}... {'MATCH '+hit if hit else 'no-match'}")
        # 64-byte-quantum test (SHA-512 / 4x64 layout)
        q64={blob[i:i+64]:f"blob[{i}:{i+64}]" for i in range(0,256,64)}
        for nm in ("hdr[0x00:0x40]","hdr[0x00:0x90]","hdr[0x00:0x200]"):
            s,e=cands[nm]
            hit=q64.get(hashlib.sha512(mv[s:e]).digest())
            print(f"SHA512 {nm:<24} {'MATCH '+hit if hit else 'no-match'}")
        print(f"blob[0:64]==blob[64:128]? {blob[:64]==blob[64:128]}")
        # also compare descriptor hash to any blob chunk and to sha256 candidates
        print(f"descriptor-hash in blob chunks: {chunks.get(h,'no')}")
        del mv
        mm.close()
