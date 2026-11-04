#!/usr/bin/env python3
"""S5: build usb_EE5600FF.forge-test.pkg (copy of A) and verify structure.

Changes ONLY: 4 flag bytes @80991127, data window @80991183..420096319.
Original is opened read-only.
"""
import hashlib, os, shutil, struct, sys

ORIG = "usb_EE5600FF.pkg"
OUT = "usb_EE5600FF.forge-test.pkg"
IMG = "3rdw_ext4.img"
AQ_START, AQ_LEN = 80956103, 35020     # structurally derived: data start + len
D3W = 80991123
FLAGS = 80991127
DATA = 80991183
DLEN = 339105136
END = DATA + DLEN                       # 420096319
USIG = 613234259
FSIZE = 613234831

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(1 << 22)
            if not b: break
            h.update(b)
    return h.hexdigest()

def walk(path):
    out = []
    pos = 0x1C3
    with open(path, "rb") as f:
        while pos + 60 <= FSIZE:
            f.seek(pos); hdr = f.read(60)
            name = hdr[0:4].split(b"\0")[0]
            if not name or not all(32 <= b < 127 for b in name):
                break
            flags, ln = struct.unpack("<II", hdr[4:12])
            out.append((name.decode(), pos, flags, ln, hdr))
            pos = pos + 60 + ln
    return out, pos

print("orig sha256:", sha(ORIG), "size:", os.path.getsize(ORIG))
chain, endpos = walk(ORIG)
print("descriptor chain (60B hdr, data=name+60, len includes data):")
for name, pos, flags, ln, hdr in chain:
    print(f"  {name} @{pos} flags=0x{flags:08x} len={ln} data@{pos+60} end={pos+60+ln}")
print("chain end:", endpos, "(file size", FSIZE, ")")
assert chain[0][0] == "spdt"

# verify data windows of original before copy
with open(ORIG, "rb") as f:
    f.seek(AQ_START); aq_orig = f.read(AQ_LEN)
    f.seek(D3W); d3w_hdr_orig = f.read(60)
    f.seek(USIG); usig_orig = f.read(FSIZE - USIG)
    f.seek(0x1C3); spdt_hdr = f.read(60)
    f.seek(0x1FF); spdt_data0 = f.read(1)
    f.seek(DATA); d3w_data0 = f.read(16)
print("aqda marker byte @80956103:", aq_orig[0:1].hex(), " MtK8 @80956104:", aq_orig[1:5])
print("spdt marker byte @0x1FF:", spdt_data0.hex(), " MtK8 @0x200:", open(ORIG,'rb').read(0x204)[0x200:0x204])
print("3rdw hdr:", d3w_hdr_orig.hex())
print("3rdw data first16:", d3w_data0.hex())

# copy
if os.path.exists(OUT):
    os.unlink(OUT)
shutil.copyfile(ORIG, OUT)
print("\ncopied ->", OUT, os.path.getsize(OUT))

with open(OUT, "r+b") as f:
    f.seek(FLAGS); f.write(b"\x00\x01\x00\x00")
    f.seek(DATA)                      # <-- critical: write image at DATA, not after flags
    with open(IMG, "rb") as g:
        left = DLEN
        while left:
            b = g.read(min(1 << 22, left))
            if not b: sys.exit("short image")
            f.write(b); left -= len(b)
    f.flush(); os.fsync(f.fileno())

print("patched. new size:", os.path.getsize(OUT))
print("test sha256:", sha(OUT))

# ---- verification ----
print("\n== descriptor chain on test pkg ==")
chain2, endpos2 = walk(OUT)
ok = True
for (n1, p1, f1, l1, h1), (n2, p2, f2, l2, h2) in zip(chain, chain2):
    same_hdr = (h1 == h2)
    print(f"  {n2} @{p2} flags=0x{f2:08x} len={l2} hdr_identical={same_hdr}")
    if p1 != p2 or l1 != l2 or n1 != n2:
        ok = False
    if n2 != "3rdw" and h1 != h2:
        ok = False
print("chain count:", len(chain), len(chain2), "end:", endpos2)
assert len(chain) == len(chain2) and endpos2 == FSIZE and endpos == FSIZE
print("all descriptors except 3rdw header identical:", ok)

# byte-level diff outside the data window
print("\n== byte diff original vs test, outside [80991183,420096319) ==")
diffs = []
buf = 1 << 22
pos = 0
with open(ORIG, "rb") as a, open(OUT, "rb") as b:
    while pos < FSIZE:
        n = min(buf, FSIZE - pos)
        ba = a.read(n); bb = b.read(n)
        if pos < END and pos + n > DATA:
            # skip data window, but check flags region separately
            pass
        else:
            if ba != bb:
                for i in range(n):
                    if ba[i] != bb[i]:
                        diffs.append(pos + i)
        pos += n
print("differing byte count outside data window:", len(diffs))
print("ranges:", end=" ")
if diffs:
    s = prev = diffs[0]
    for x in diffs[1:]:
        if x == prev + 1:
            prev = x; continue
        print(f"[{s},{prev+1})", end=" "); s = prev = x
    print(f"[{s},{prev+1})")
else:
    print("none")

# count diffs inside data window
n_same = n_diff = 0
with open(ORIG, "rb") as a, open(OUT, "rb") as b:
    a.seek(DATA); b.seek(DATA); left = DLEN
    while left:
        n = min(buf, left)
        ba = a.read(n); bb = b.read(n)
        for i in range(n):
            if ba[i] == bb[i]: n_same += 1
            else: n_diff += 1
        left -= n
print(f"inside data window: identical={n_same} differing={n_diff} of {DLEN}")

# region identity checks
def region_equal(off, ln):
    with open(ORIG, "rb") as a, open(OUT, "rb") as b:
        a.seek(off); b.seek(off)
        return a.read(ln) == b.read(ln)
checks = [
    ("aqda derived [80956103,80991123)", AQ_START, AQ_LEN),
    ("aqda task    [80956104,80991124)", 80956104, 35019 + 1),
    ("3rdw hdr except flags [80991123,80991127)", D3W, 4),
    ("3rdw hdr tail [80991131,80991183)", 80991131, 52),
    ("usig desc+data [613234259,613234831)", USIG, FSIZE - USIG),
    ("usig blob [613234319,613234575)", 613234319, 256),
    ("trailer MTK+USIG [613234575,613234831)", 613234575, 256),
    ("spdt hdr [0x1C3,0x1FF)", 0x1C3, 60),
    ("pkg header [0,0x1C3)", 0, 0x1C3),
]
for label, off, ln in checks:
    print(f"  {label}: {'IDENTICAL' if region_equal(off, ln) else 'DIFF'}")

# flags proof
with open(OUT, "rb") as f:
    f.seek(FLAGS); fl = f.read(4)
    f.seek(D3W); nm = f.read(4)
    f.seek(80991131); lnb = f.read(4)
    f.seek(80991151); sh = f.read(32)
    f.seek(DATA); first16 = f.read(16)
print(f"\nnew flags @{FLAGS}: {fl.hex()} = 0x{struct.unpack('<I',fl)[0]:08x}")
print("name:", nm, "len field:", lnb.hex(), "=", struct.unpack('<I',lnb)[0])
print("subhash unchanged:", sh.hex())
print("new data first16:", first16.hex())
