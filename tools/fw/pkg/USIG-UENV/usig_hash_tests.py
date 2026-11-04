#!/usr/bin/env python3
# AP-USIG-UENV / script 4: usig vs SHA-256/512 of per-image regions and hash lists
import hashlib, mmap, struct

A="usb_EE5600FF.pkg"
f=open(A,"rb"); m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
size=len(m)
blob=m[size-512:size-256]
chunks32={blob[i:i+32]:f"blob[{i}:{i+32}]" for i in range(0,256,32)}
chunks64={blob[i:i+64]:f"blob[{i}:{i+64}]" for i in range(0,256,64)}
IMGS=[("spdt",512,41943104),("logo",41943676,35185725),("ddb",77391665,10771),
      ("uenv",78875832,4188),("adsp",78880080,2075964),("aqda",80956104,35020)]
hashes=[]
for nm,off,ln in IMGS:
    d=m[off:off+ln]
    hs=hashlib.sha256(d).digest(); hashes.append(hs)
    print(f"img {nm:<5} sha256(data)={hs.hex()}  match={chunks32.get(hs,'no')}")
    desc=m[off-60:off]
    hd=hashlib.sha256(desc).digest()
    print(f"      sha256(desc60)={hd.hex()}  match={chunks32.get(hd,'no')}")
    h5=hashlib.sha512(d).digest()
    print(f"      sha512(data) match={chunks64.get(h5,'no')}")
def dhash(off):
    return m[off-33:off-1] if m[off-1]==0x69 else m[off-32:off]
descs=[dhash(o) for _,o,_ in IMGS]
for nm,off,_ in IMGS:
    d=dhash(off)
    print(f"proprietary desc-hash {nm:<5} = {d.hex()}  match={chunks32.get(d,'no')}")
cat=b"".join(hashes)
for nm,val in (("sha256(concat 6 sha256(data))",hashlib.sha256(cat).digest()),
               ("sha256(concat 6 descriptor-hash)",hashlib.sha256(b"".join(descs)).digest()),
               ("sha256(usig descriptor 60B)",hashlib.sha256(m[size-572:size-512]).digest()),
               ("sha256(trailer256)",hashlib.sha256(m[size-256:]).digest())):
    print(f"{nm:<34} = {val.hex()} match={chunks32.get(val,'no')}")
print(f"blob chunks unique={len(chunks32)}; any zero chunk? {any(set(c)=={0} for c in chunks32)}")
print(f"blob ASCII printable bytes={sum(1 for x in blob if 32<=x<127)}/256")
m.close(); f.close()
