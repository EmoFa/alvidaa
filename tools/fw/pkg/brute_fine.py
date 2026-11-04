#!/usr/bin/env python3
"""Fine-grid brute force over uenv window for the 32-byte candidate."""
import hashlib, hmac, mmap

A = "usb_EE5600FF.pkg"
uenv_mtk8 = 78875832
nxt = 78880080
name_off = uenv_mtk8 - 61
cand = bytes.fromhex("53325fb02df00812cc8ac48245553c2276d44b8faf5f6280f9901fa4527e5046")

f = open(A,'rb'); m = mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
win_start = name_off
win_end = nxt
win = m[win_start:win_end]

mtk8_r = uenv_mtk8 - win_start   # 61
nxt_r = win_end - win_start      # = nxt - name_off = 61 + 4248 = 4309

print(f"window size={len(win)}, mtk8_r={mtk8_r}, nxt_r={nxt_r}")

const16 = bytes.fromhex("afd212176b6d06a8b888fcf5f0198ece")

def check(d, label):
    if hashlib.sha256(d).digest() == cand: print("SHA256 MATCH:", label); return True
    if hashlib.md5(d).digest() == cand: print("MD5 MATCH:", label); return True
    if hashlib.sha1(d).digest() == cand: print("SHA1 MATCH:", label); return True
    return False

found = False
# fine grid over starts and ends
for s in range(0, mtk8_r+80):
    for e in range(mtk8_r+1, nxt_r+1):
        if e - s < 1: continue
        data = win[s:e]
        if check(data, f"plain [{win_start+s}-{win_start+e}]"):
            found = True; break
    if found: break

if not found:
    print("No plain hash match on fine grid.")
    # HMAC with const16 key on fine grid
    for s in range(0, mtk8_r+80):
        for e in range(mtk8_r+1, nxt_r+1):
            data = win[s:e]
            for an in ('sha256','md5','sha1'):
                if hmac.new(const16, data, an).digest() == cand:
                    print(f"HMAC-{an}(const16) MATCH [{win_start+s}-{win_start+e}]"); found=True; break
            if found: break
        if found: break

if not found:
    print("No HMAC-const16 match either.")
    # Try double-hash
    for s in range(0, mtk8_r+80):
        for e in range(mtk8_r+1, nxt_r+1):
            data = win[s:e]
            if hashlib.sha256(hashlib.sha256(data).digest()).digest() == cand:
                print(f"sha256(sha256) MATCH [{win_start+s}-{win_start+e}]"); found=True; break
            if hashlib.md5(hashlib.md5(data).digest()).digest() == cand:
                print(f"md5(md5) MATCH [{win_start+s}-{win_start+e}]"); found=True; break
        if found: break

if not found:
    print("No double-hash match.")

f.close(); m.close()
