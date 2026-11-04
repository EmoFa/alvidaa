#!/usr/bin/env python3
# AP-USIG-UENV / script 3: descriptor bytes, cross-build equality, uenv .data (READ-ONLY)
import hashlib, mmap, struct, os

A="usb_EE5600FF.pkg"
B="usb_EE5600FF.pkg"
OUT="USIG-UENV"
F={}
for tag,p in (("A",A),("B",B)):
    f=open(p,"rb"); F[tag]=(f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ))

def desc(tag,pos):
    m=F[tag][1]
    name=m[pos:pos+4]; flags,ln=struct.unpack("<II",m[pos+4:pos+12])
    c=m[pos+12:pos+28]; h=m[pos+28:pos+60]
    print(f"{tag} descriptor @ {pos}: name={name!r} flags={flags:#x} len={ln}")
    print(f"   const16={c.hex()} hash32={h.hex()}")
    return name,flags,ln,h

for tag in ("A","B"):
    m=F[tag][1]; size=len(m)
    print(f"--- {tag} size={size}")
    d=size-572
    desc(tag,d)
    print(f"   usig 512B region sha256={hashlib.sha256(m[d+60:d+572]).hexdigest()}")
    # uenv descriptor = 61 B before MtK8 78875832? try 60/61
    for back in (60,61):
        p=78875832-back
        nm=m[p:p+4]
        if nm==b"uenv":
            desc(tag,p); break
    print(f"   usig blob sha256={hashlib.sha256(m[d+60:d+316]).hexdigest()}")

a=F["A"][1]; b=F["B"][1]
print(f"usig 512B A==B? {a[len(a)-512:]==b[len(b)-512:]}")
print(f"header 0x00:0x40 A==B? {a[:0x40]==b[:0x40]}   0x40:0x90 A==B? {a[0x40:0x90]==b[0x40:0x90]}")
blob=a[len(a)-572+60:len(a)-572+60+256]
print(f"blob == 512B-region[:256]? {blob==a[len(a)-512:len(a)-512+256]}")
print(f"header64 first16={a[:16].hex()}  blob contains header64 first16? {a[:16] in blob}")
print(f"blob first32 appears elsewhere in A? pos={a.find(blob[:32])} (blob at {len(a)-512})")
print(f"blob first32 appears elsewhere in B? pos={b.find(blob[:32])} (blob at {len(b)-512})")
# uenv ELF .data bytes: ELF at MtK8+63, .data off 0x34 len 0x1c
for tag in ("A","B"):
    m=F[tag][1]; base=78875832+63
    data=m[base+0x34:base+0x34+0x1c]
    print(f"{tag} uenv .data 28B @ abs {base+0x34}: {data.hex(' ')}")
    print(f"   as 7 u32 LE: {[hex(x) for x in struct.unpack('<7I',data)]}")
    for off in (1293,2197,2289,3724):
        if off < 4188:
            s=m[78875832+off-20:78875832+off+30]
            print(f"   '+env' context rel {off}: {s!r}")
for f,m in F.values(): m.close(); f.close()
