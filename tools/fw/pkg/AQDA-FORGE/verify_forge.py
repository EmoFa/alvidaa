#!/usr/bin/env python3
"""S6: verify usb_EE5600FF.forge-test.pkg against original A.

- enumerate every 0x69+'MtK8' image payload and its 60B descriptor
- whole-file byte diff (outside / inside changed data window)
- region identity checks incl. both candidate aqda hash windows
- usig / trailer identity
Exit non-zero on any failed assertion.
"""
import hashlib, struct, sys

ORIG = "usb_EE5600FF.pkg"
OUT = "usb_EE5600FF.forge-test.pkg"
FSIZE = 613234831
AQ_START, AQ_LEN = 80956103, 35020
D3W, FLAGS, DATA = 80991123, 80991127, 80991183
DLEN = 339105136
END = DATA + DLEN
USIG = 613234259

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(1 << 22)
            if not b: break
            h.update(b)
    return h.hexdigest()

def find_mtk8(path):
    hits = []
    with open(path, "rb") as f:
        pos = 0
        while pos < FSIZE:
            f.seek(pos); b = f.read(1 << 22)
            if not b: break
            i = b.find(b"MtK8")
            while i != -1:
                hits.append(pos + i); i = b.find(b"MtK8", i + 1)
            pos += len(b)
    return hits

def desc_at(path, mk):
    """descriptor name at mk-61, data starts with 0x69 at mk-1."""
    pos = mk - 61
    with open(path, "rb") as f:
        f.seek(pos); hdr = f.read(60)
        f.seek(mk - 1); marker = f.read(1)
    name = hdr[0:4].split(b"\0")[0].decode("latin1")
    flags, ln = struct.unpack("<II", hdr[4:12])
    return name, pos, flags, ln, marker, hdr

print("orig sha256:", sha(ORIG))
print("test sha256:", sha(OUT))
print("sizes:", FSIZE, FSIZE)

print("\n== image payloads (0x69 + MtK8), descriptor at mtk8-61 ==")
hits_a = find_mtk8(ORIG); hits_b = find_mtk8(OUT)
print("MtK8 count orig/test:", len(hits_a), len(hits_b), "identical offsets:", hits_a == hits_b)
for mk in hits_a:
    na, pa, fa, la, ma, ha = desc_at(ORIG, mk)
    nb, pb, fb, lb, mb, hb = desc_at(OUT, mk)
    nxt = pa + 60 + la
    print(f"  {na:5s} desc@{pa} flags=0x{fa:08x} len={la} data@{mk-1}(0x{ma.hex()}) "
          f"next={nxt} | test flags=0x{fb:08x} hdr_same={ha==hb}")
    assert (na, pa, fa, la) == (nb, pb, fb, lb) or na == "3rdw"
    if na != "3rdw":
        assert ha == hb, f"descriptor changed for {na}"

print("\n== whole-file diff ==")
buf = 1 << 22
outside = []
inside_same = inside_diff = 0
pos = 0
with open(ORIG, "rb") as a, open(OUT, "rb") as b:
    while pos < FSIZE:
        n = min(buf, FSIZE - pos)
        ba = a.read(n); bb = b.read(n)
        assert len(ba) == len(bb) == n
        for i in range(n):
            if ba[i] == bb[i]:
                if DATA <= pos + i < END: inside_same += 1
            else:
                if DATA <= pos + i < END: inside_diff += 1
                else: outside.append(pos + i)
        pos += n
print("outside data window differing bytes:", len(outside))
if outside:
    s = prev = outside[0]
    ranges = []
    for x in outside[1:]:
        if x == prev + 1: prev = x; continue
        ranges.append((s, prev + 1)); s = prev = x
    ranges.append((s, prev + 1))
    print("ranges:", [(f"[{a},{b})", b - a) for a, b in ranges])
print(f"inside data window: same={inside_same} diff={inside_diff} total={DLEN}")

def eq(off, ln):
    with open(ORIG, "rb") as a, open(OUT, "rb") as b:
        a.seek(off); b.seek(off)
        return a.read(ln) == b.read(ln)

print("\n== identity checks ==")
checks = [
    ("pkg header+table [0,0x1C3)", 0, 0x1C3),
    ("spdt desc [0x1C3,0x1FF)", 0x1C3, 60),
    ("aqda derived hashwin [80956103,80991123)", AQ_START, AQ_LEN),
    ("aqda task hashwin    [80956104,80991124)", 80956104, 35020),
    ("3rdw name            [80991123,80991127)", D3W, 4),
    ("3rdw len+const+hash  [80991131,80991183)", 80991131, 52),
    ("3rdp..kern region    [420096319,613234259)", 420096319, 613234259 - 420096319),
    ("usig desc+data       [613234259,613234831)", USIG, FSIZE - USIG),
    ("usig 256B blob       [613234319,613234575)", 613234319, 256),
    ("trailer MTK+USIG     [613234575,613234831)", 613234575, 256),
]
allok = True
for label, off, ln in checks:
    r = eq(off, ln)
    allok &= r
    print(f"  {label}: {'IDENTICAL' if r else 'DIFF'}")

with open(OUT, "rb") as f:
    f.seek(FLAGS); fl = f.read(4)
    f.seek(D3W); nm = f.read(4)
    f.seek(80991131); lnb = f.read(4)
    f.seek(80991151); sh = f.read(32)
    f.seek(DATA); d0 = f.read(16)
print(f"\n3rdw flags @{FLAGS} = {fl.hex()} -> 0x{struct.unpack('<I', fl)[0]:08x}")
print("3rdw name:", nm, "len:", struct.unpack('<I', lnb)[0], "subhash:", sh.hex())
print("new data first16:", d0.hex())
print("ext4 superblock magic @1080:", end=" ")
with open(OUT, "rb") as f:
    f.seek(DATA + 1080); m = f.read(2)
print(m.hex(), "(expect 53ef)", m == b"\x53\xef")

assert outside == [80991127], outside
assert inside_diff > 0 and inside_same >= 0
assert allok
print("\nALL ASSERTIONS PASSED")
