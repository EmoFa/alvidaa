#!/usr/bin/env python3
"""S7: bounded AES candidate test on ORIGINAL 3rdw data (read-only).

48 candidates = 16 keys x {AES-ECB, AES-CBC/zero-IV, AES-CTR/zero-IV}.
Plaintext checks: 1 KiB ext4 boot block all zero, and/or ext4 superblock
signature at 1024+0x38 (abs 1080): magic 53ef + s_log_block_size==2.
"""
import hashlib, subprocess, sys

ORIG = "usb_EE5600FF.pkg"
DATA = 80991183
N = 2048
CT = "ct_head.bin"

def rd(off, n):
    with open(ORIG, "rb") as f:
        f.seek(off); return f.read(n)

with open(CT, "wb") as f:
    f.write(rd(DATA, N))
ct = open(CT, "rb").read()
usig = rd(613234319, 256)
h64 = rd(0, 64)
h80 = rd(0x40, 80)
const16 = rd(80956055, 16)

keys = []
def add(name, k):
    if len(k) in (16, 32):
        keys.append((name, k))
add("usig[0:16]", usig[:16])
add("usig[0:32]", usig[:32])
add("sha256(usig)[:16]", hashlib.sha256(usig).digest()[:16])
add("sha256(usig)", hashlib.sha256(usig).digest())
add("h64[0:16]", h64[:16])
add("h64[0:32]", h64[:32])
add("sha256(h64)[:16]", hashlib.sha256(h64).digest()[:16])
add("sha256(h64)", hashlib.sha256(h64).digest())
add("h80[0:16]", h80[:16])
add("h80[0:32]", h80[:32])
add("sha256(h80)[:16]", hashlib.sha256(h80).digest()[:16])
add("sha256(h80)", hashlib.sha256(h80).digest())
add("const16", const16)
add("sha256(const16)[:16]", hashlib.sha256(const16).digest()[:16])
add("sha256(usig+h64+h80)", hashlib.sha256(usig + h64 + h80).digest())
add("md5(usig)", hashlib.md5(usig).digest())

modes = [("ecb", []), ("cbc", ["-iv", "00" * 16]), ("ctr", ["-iv", "00" * 16])]
hits = []
count = 0
for name, key in keys:
    bits = "128" if len(key) == 16 else "256"
    for mode, extra in modes:
        count += 1
        cmd = ["openssl", "enc", "-d", f"-aes-{bits}-{mode}", "-K", key.hex(),
               "-nopad", "-in", CT] + extra
        r = subprocess.run(cmd, capture_output=True)
        pt = r.stdout
        if len(pt) != N:
            print(f"[ERR] {name} {mode}: rc={r.returncode} {r.stderr[:80]!r}")
            continue
        boot_zero = pt[:1024] == b"\0" * 1024
        magic1024 = pt[1024:1026] == b"\x53\xef"
        magic1080 = pt[1080:1082] == b"\x53\xef"
        logbs = pt[1048:1052] == b"\x02\x00\x00\x00"
        if boot_zero or magic1024 or (magic1080 and logbs):
            hits.append((name, mode, boot_zero, magic1024, magic1080, logbs))
            print(f"HIT {name} {mode} boot0={boot_zero} m1024={magic1024} "
                  f"m1080={magic1080} logbs2={logbs}")
print(f"candidates tested: {count}")
print("hits:", hits if hits else "NONE")
print("verdict:", "HIT" if hits else "NEGATIVE (no candidate produced ext4 signature)")
