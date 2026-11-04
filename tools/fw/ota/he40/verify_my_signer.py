#!/usr/bin/env python3
"""Verify the OTA request signature scheme against a recorded sample.

    python3 verify_my_signer.py "<content>" "<signature-b64>"

or via environment:

    HISENSE_CONTENT=... HISENSE_EXPECTED=... python3 verify_my_signer.py

The public key is read from HISENSE_PUBKEY (default: pubkey.pem).
No request body, device id or signature is shipped with this repository.
"""
import base64
import hashlib
import os
import sys

from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization

PUBKEY_PATH = os.environ.get("HISENSE_PUBKEY", "pubkey.pem")
pub = serialization.load_pem_public_key(open(PUBKEY_PATH, "rb").read())

content = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("HISENSE_CONTENT", "")
expected = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("HISENSE_EXPECTED", "")

if not content or not expected:
    raise SystemExit("usage: verify_my_signer.py <content> <signature-b64>")

md5 = hashlib.md5(content.encode()).digest()
enc = pub.encrypt(md5, padding.PKCS1v15())
mine = base64.b64encode(enc).decode()

print("MATCH" if mine == expected else "MISMATCH")
print("mine    :", mine)
print("expected:", expected)
