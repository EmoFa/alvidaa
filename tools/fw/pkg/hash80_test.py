import mmap, hashlib, struct

A="usb_EE5600FF.pkg"
B="usb_EE5600FF.pkg"

def load(p):
    f=open(p,"rb"); mm=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ); return mm

ma=load(A); mb=load(B)
blkA = ma[0x40:0x90]
blkB = mb[0x40:0x90]

# All 16/20/32/48/64-byte windows of the 80-byte block (as candidate hash values)
def windows(blk, sizes=(16,20,32,48,64)):
    out={}
    for s in sizes:
        for off in range(0, 80-s+1):
            out[(s,off)] = blk[off:off+s]
    return out

def find_match(blk, digest):
    for s in (16,20,32,48,64):
        for off in range(0, 80-s+1):
            if blk[off:off+s] == digest[:s]:
                return (s, off)
    return None

# Regions to hash. Use build A primarily (block A should match A's regions).
# Region = (name, start, end) in bytes (absolute).
fsizeA = len(ma)
MTK8s = [512, 41943676, 77391665, 78875832, 78880080, 80956104]
names = ['spdt','logo','ddb','uenv','adsp','aqda']
regions = []
# full file variants
regions.append(('full_file', 0, fsizeA))
regions.append(('file_from_0x40', 0x40, fsizeA))
regions.append(('file_from_0x90', 0x90, fsizeA))
regions.append(('file_from_0x200', 0x200, fsizeA))
regions.append(('file_with_blk80_zeroed_parts', None, None))  # special
# cfig chunk and partition table
regions.append(('cfig_chunk_0x90_0x1C3', 0x90, 0x1C3))
regions.append(('parttable_0xCC_0x1C3', 0xCC, 0x1C3))
# each image
for i,(off,nm) in enumerate(zip(MTK8s,names)):
    nxt = MTK8s[i+1] if i+1 < len(MTK8s) else (fsizeA-256)
    regions.append((f'img_{nm}_MtK8_span', off, nxt))
    regions.append((f'img_{nm}_MtK8_data', off+63, nxt))
# aqda sub-partitions (data regions)
subs=[("3rdw",35019+60,35019+60+0x14365570),("3rdp",339140215+60,339140215+60+0x8d1d040),
      ("rtfs",487108339+60,487108339+60+0x26f8040),("kern",527970159+60,527970159+60+0x41bbe0)]
for nm,s,e in subs:
    regions.append((f'aqda_{nm}_data', 80956104+s, 80956104+e))

def hash_region(mm, s, e):
    data = mm[s:e]
    return {
        'MD5': hashlib.md5(data).digest(),
        'SHA1': hashlib.sha1(data).digest(),
        'SHA256': hashlib.sha256(data).digest(),
        'SHA384': hashlib.sha384(data).digest(),
        'SHA512': hashlib.sha512(data).digest(),
    }

print("=== Hash correlation test: 80B block vs region hashes (build A) ===")
for name, s, e in regions:
    if name == 'file_with_blk80_zeroed_parts':
        # hash full file with 0x40-0x8F zeroed
        for algo, fn in [('MD5',hashlib.md5),('SHA256',hashlib.sha256),('SHA512',hashlib.sha512)]:
            h=fn(); 
            h.update(ma[0:0x40]); h.update(b'\x00'*80); h.update(ma[0x90:])
            m = find_match(blkA, h.digest())
            if m: print(f"  MATCH {algo}(file_with_blk80_zeroed) at window {m}")
            else: print(f"  no-match {algo}(file_with_blk80_zeroed)")
        continue
    h = hash_region(ma, s, e)
    for algo, d in h.items():
        m = find_match(blkA, d)
        if m:
            print(f"  MATCH {algo}({name}) -> window(offset {m[1]}, size {m[0]})")
    # also print a few for the aqda head (interesting region)
print("done (only matches printed above)")

# Also: check if 80B block == hash of the OTHER build's regions (cross-check not needed)

# Truncation test: maybe the 80B block is SHA512 (64B) + 16B of something else
print("\n=== 80B block structure hypothesis ===")
print("A first 32B:", blkA[:32].hex())
print("A next 32B :", blkA[32:64].hex())
print("A last 16B :", blkA[64:80].hex())
