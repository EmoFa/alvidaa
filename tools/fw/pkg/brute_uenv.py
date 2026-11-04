#!/usr/bin/env python3
"""Exhaustive hash brute-force on the small uenv image (A).
Candidate = 53325fb02df00812cc8ac48245553c2276d44b8faf5f6280f9901fa4527e5046
"""
import hashlib, hmac, struct, os, mmap

A = "usb_EE5600FF.pkg"
uenv_mtk8 = 78875832   # MtK8
nxt = 78880080         # next MtK8 (adsp)
name_off = uenv_mtk8 - 61

f = open(A,'rb'); m = mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)

# candidate from A uenv descriptor
cand = bytes.fromhex("53325fb02df00812cc8ac48245553c2276d44b8faf5f6280f9901fa4527e5046")

# Extract a generous window around uenv image
win_start = name_off - 64
win_end = nxt + 64
win = m[win_start:win_end]

# Reference offsets within window
def rel(off): return off - win_start
mtk8_r = rel(uenv_mtk8)
name_r = rel(name_off)
nxt_r = rel(nxt)

print(f"window [{win_start}-{win_end}], mtk8@rel={mtk8_r}, name@rel={name_r}, nxt@rel={nxt_r}")

# The const/key
const16 = bytes.fromhex("afd212176b6d06a8b888fcf5f0198ece")

# Try many (start, end) candidates
starts = [name_r, name_r+4, name_r+8, name_r+12, name_r+16, name_r+28,
          mtk8_r, mtk8_r+4, mtk8_r+8, mtk8_r+11, mtk8_r+32, mtk8_r+63, mtk8_r+64]
ends = [nxt_r, nxt_r-1, nxt_r-61, nxt_r-64, nxt_r-33, mtk8_r+32+4188,
        mtk8_r+32+4155, mtk8_r+32+4124, name_r+61]

algos = {
    'sha256': lambda d: hashlib.sha256(d).digest(),
    'md5': lambda d: hashlib.md5(d).digest(),
    'sha1': lambda d: hashlib.sha1(d).digest(),
    'sha512': lambda d: hashlib.sha512(d).digest(),
}
found = False
for s in starts:
    for e in ends:
        if s >= e: continue
        data = win[s:e]
        for an, afn in algos.items():
            if afn(data) == cand:
                print(f"MATCH {an} window[{s}-{e}] abs=[{win_start+s}-{win_start+e}]")
                found = True
        # HMAC with const16 key
        for an in ('sha256','md5','sha1'):
            d = hmac.new(const16, data, an).digest()
            if d == cand:
                print(f"MATCH HMAC-{an}(const16) window[{s}-{e}] abs=[{win_start+s}-{win_start+e}]")
                found = True

# Also try: the 32-byte candidate might be a hash whose DIGEST hex we compare differently
# Check if cand equals sha256 of the ELF only (find ELF magic)
elf_r = win.find(b'\x7fELF')
print(f"ELF magic at rel={elf_r} abs={win_start+elf_r}")
if elf_r >= 0:
    for e in ends:
        if e > elf_r:
            if hashlib.sha256(win[elf_r:e]).digest() == cand:
                print(f"MATCH sha256(ELF)[elf_r-{e}]")
            if hashlib.md5(win[elf_r:e]).digest() == cand:
                print(f"MATCH md5(ELF)")

# Print the uenv descriptor raw for reference
print("\nuenv descriptor (61B from name):", m[name_off:name_off+61].hex())
print("content after MtK8 hdr (32B): first 64B:", m[uenv_mtk8+32:uenv_mtk8+96].hex())

if not found:
    print("\nNo simple hash match found. Trying HMAC with different keys...")
    keys = [const16, const16[:4], const16[:12], b'\x00'*16, const16 + const16]
    for s in starts:
        for e in ends:
            if s>=e: continue
            data = win[s:e]
            for k in keys:
                for an in ('sha256','sha1','md5'):
                    if hmac.new(k, data, an).digest() == cand:
                        print(f"MATCH HMAC-{an} key={k.hex()} window[{s}-{e}]")
                        found = True
    if not found:
        print("No HMAC match either.")

f.close(); m.close()
