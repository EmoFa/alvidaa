#!/usr/bin/env python3
"""Final checks: OID scan, image5 magic, precise payload hash."""
import hashlib, mmap, struct

A = "usb_EE5600FF.pkg"
B = "usb_EE5600FF.pkg"

# 1) Scan whole file for RSA/ECDSA OIDs and common signature markers
OIDS = {
 'RSA': bytes.fromhex('2a864886f70d010101'),
 'RSA_alt': bytes.fromhex('06092a864886f70d010101'),
 'ECDSA_P256': bytes.fromhex('2a8648ce3d030107'),
 'ECDSA_any': bytes.fromhex('2a8648ce3d'),
 'sha256WithRSA': bytes.fromhex('2a864886f70d01010b'),
}
for path, tag in [(A,'A'),(B,'B')]:
    f=open(path,'rb'); m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
    print(f"=== {tag} whole-file OID scan (chunked) ===")
    CH=1<<24
    for name, oid in OIDS.items():
        cnt=0; first=[]
        for off in range(0, len(m), CH):
            blk = m[off:off+CH+len(oid)]
            i = blk.find(oid)
            if i>=0:
                cnt+=1
                if len(first)<5: first.append(off+i)
        print(f"  {name}: {cnt} hits {first}")
    f.close(); m.close()

# 2) image5 magic scan
print("\n=== image5 (aqda) magic scan ===")
f=open(A,'rb'); m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
start=80956104; end=613234575
magics = {b'\x68\x73\x71\x73':'squashfs', b'UBI#':'ubi', b'\x53\xef':'ext4',
          b'\x1f\x8b\x08':'gzip', b'BZh':'bzip2', b'\xfd7zXZ':'xz',
          b'\x28\xb5\x2f\xfd':'zstd', b'uImage':'uImage', b'\x27\x05\x19\x56':'u-boot',
          b'ANDROID!':'android', b'AVB0':'avb', b'\x30\x82':'DER-seq'}
for mg, name in magics.items():
    # scan in chunks
    cnt=0; first=[]
    for off in range(start, end, 1<<24):
        blk = m[off:min(off+(1<<24)+len(mg), end)]
        i = blk.find(mg)
        if i>=0:
            cnt+=1
            if len(first)<5: first.append(off+i)
    print(f"  {name}: {cnt} hits {first}")
f.close(); m.close()

# 3) precise uenv payload hash
print("\n=== uenv payload precise hash ===")
f=open(A,'rb'); m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
cand = bytes.fromhex("53325fb02df00812cc8ac48245553c2276d44b8faf5f6280f9901fa4527e5046")
elf = 78875895
# ELF header fields
eh = m[elf:elf+52]
# shoff at offset 32 (4 bytes), shentsize at 46 (2), shnum at 48 (2)
shoff = struct.unpack('<I', m[elf+32:elf+36])[0]
shentsize = struct.unpack('<H', m[elf+46:elf+48])[0]
shnum = struct.unpack('<H', m[elf+48:elf+50])[0]
elf_end = shoff + shentsize*shnum
print(f"ELF shoff={shoff} shentsize={shentsize} shnum={shnum} -> elf_size={elf_end}")
for L in (elf_end, 4188, 4124, 4216, 3420):
    data = m[elf:elf+L]
    if hashlib.sha256(data).digest()==cand: print(f"  SHA256 MATCH len={L}")
    if hashlib.md5(data).digest()==cand: print(f"  MD5 MATCH len={L}")
# try hashing from MtK8+63 to MtK8+63+4188
for L in (4188,):
    data = m[elf:elf+L]
    print(f"  sha256([{elf},{elf+L}])={hashlib.sha256(data).hexdigest()[:32]}...")
print(f"  candidate={cand.hex()}")
f.close(); m.close()
