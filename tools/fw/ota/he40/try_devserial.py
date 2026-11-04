#!/usr/bin/env python3
"""Attempt Hisense VIDAA get_dev_serial to obtain devSerial for a device.

Set your own values; nothing is hardcoded:
    export HISENSE_FEATURE_CODE=...
    export HISENSE_TOKEN=...          # optional access token
"""
import os
import time, urllib.request, urllib.parse, json
from ota_sign import hitvsign, randstr

API = "https://api.hismarttv.com"
FEATURE_CODE = os.environ.get("HISENSE_FEATURE_CODE", "")  # sanitize:allow (env-backed)

def get_dev_serial(dev_flag, featureCode=None, accessToken=None):
    featureCode = featureCode or FEATURE_CODE  # sanitize:allow (env-backed)
    accessToken = accessToken if accessToken is not None else os.environ.get("HISENSE_TOKEN", "")  # sanitize:allow (env-backed)
    if not featureCode:
        raise SystemExit("missing environment variable: HISENSE_FEATURE_CODE")
    ts = str(int(time.time()))
    rnd = randstr(32)
    base = (f"accessToken={accessToken}&dev_flag={dev_flag}&featureCode={featureCode}"
            f"&format=0&languageId=0&randStr={rnd}&timeStamp={ts}&version=7.0")
    sign = hitvsign(base)
    body = base + "&sign=" + sign
    req = urllib.request.Request(
        API + "/aaa/get_dev_serial",
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=iso-8859-1"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace"), base
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), base
    except Exception as e:
        return "ERR", str(e), base

if __name__ == "__main__":
    for flag in ["0", "1", "7", "1.0", "dev_flag"]:
        st, resp, base = get_dev_serial(flag)
        print(f"--- dev_flag={flag!r} status={st}")
        print("  body:", base[:120])
        print("  resp:", resp[:300])
        print()
