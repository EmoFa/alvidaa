#!/usr/bin/env python3
"""Hisense VIDAA OTA request signer (reconstructed from libhisdk.so).

hitvsign(content) = urlencode( base64( RSA_public_encrypt( MD5(content), PUBLIC_KEY, PKCS1v15 ) ) )
"""
import base64, hashlib, json, random, string, time, urllib.parse, urllib.request

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

# No vendor key is shipped. Export the public key from the firmware you are
# analysing and point HISENSE_PUBKEY at it (default: ./pubkey.pem).
import os

PUBKEY_PATH = os.environ.get("HISENSE_PUBKEY", "pubkey.pem")
PUBKEY_PEM = open(PUBKEY_PATH, "rb").read()

_pub = serialization.load_pem_public_key(PUBKEY_PEM)

def hitvsign(s: str) -> str:
    md5 = hashlib.md5(s.encode("utf-8")).digest()          # 16 bytes
    enc = _pub.encrypt(md5, padding.PKCS1v15())            # 64 bytes
    b64 = base64.b64encode(enc).decode("ascii")            # 88 chars
    return urllib.parse.quote(b64, safe="")                # URLEncode

def randstr(n=32) -> str:
    return "".join(random.choice(string.hexdigits) for _ in range(n)).lower()

API = "https://api.hismarttv.com"

def post(path, params_signed, sign_field=True, extra=""):
    sign = hitvsign(params_signed)
    body = params_signed + ("&sign=" + sign if sign_field else "") + extra
    req = urllib.request.Request(
        API + path,
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=iso-8859-1",
                 "User-Agent": "HisenseTV"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.read().decode("utf-8", "replace"), body

if __name__ == "__main__":
    # smoke test
    print("test sign:", hitvsign("hello")[:40], "...")
    print("length:", len(hitvsign("hello")))
