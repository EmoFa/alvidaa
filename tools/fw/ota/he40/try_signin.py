#!/usr/bin/env python3
"""Reconstruct and send a Hisense VIDAA /aaa/sign_in request.

Nothing device-specific is hardcoded. Provide your own values:

    export HISENSE_APP_KEY=...          # vendor app key
    export HISENSE_APP_SECRET=...       # vendor app secret (encrypted form)
    export HISENSE_PUBKEY=pubkey.pem    # public key exported from your firmware
    export HISENSE_DEV_SERIAL=...
    export HISENSE_DEVICE_ID=...

Then:  python3 try_signin.py
"""
import base64
import hashlib
import os
import random
import time
import urllib.parse
import urllib.request

from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization


def env(name, default=None):
    value = os.environ.get(name, default)
    if not value:
        raise SystemExit("missing environment variable: " + name)
    return value


PUBKEY_PATH = os.environ.get("HISENSE_PUBKEY", "pubkey.pem")
_pub = serialization.load_pem_public_key(open(PUBKEY_PATH, "rb").read())


def randstr(n=32):
    return "".join(random.choice("0123456789") for _ in range(n))


def hitvsign(s):
    md5 = hashlib.md5(s.encode()).digest()
    enc = _pub.encrypt(md5, padding.PKCS1v15())
    b64 = base64.b64encode(enc).decode()
    return urllib.parse.quote(b64, safe="")


def sign_in(devSerial, deviceId, appKey=None, appSecret=None):
    appKey = appKey or env("HISENSE_APP_KEY")  # sanitize:allow (env-backed)
    appSecret = appSecret or env("HISENSE_APP_SECRET")  # sanitize:allow (env-backed)
    ts = str(int(time.time()))
    rnd = randstr()
    signed = (f"appKey={appKey}&appSecret={appSecret}&devSerial={devSerial}"
              f"&deviceId={deviceId}&format=0&languageId=0&randStr={rnd}"
              f"&serviceType=9&sourceType=1&timeStamp={ts}&version=7.0")
    sign = hitvsign(signed)
    body = (f"appKey={appKey}&appSecret={appSecret}&devSerial={devSerial}"
            f"&deviceId={deviceId}&format=0&languageId=0&loginName=&qrCodeFlag="
            f"&randStr={rnd}&serviceType=9&signature=&sourceType=1&timeStamp={ts}"
            f"&version=7.0&webFlag=&sign={sign}")
    req = urllib.request.Request(
        "https://auth-eu.hismarttv.com/aaa/sign_in",
        data=body.encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=iso-8859-1",
                 "User-Agent": "HisenseTV"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace"), signed, body
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), signed, body
    except Exception as e:
        return "ERR", str(e), signed, body


if __name__ == "__main__":
    st, resp, signed, body = sign_in(
        devSerial=env("HISENSE_DEV_SERIAL"),
        deviceId=env("HISENSE_DEVICE_ID"),
    )
    print("status:", st)
    print("body:", body)
    print("resp:", resp[:800])
