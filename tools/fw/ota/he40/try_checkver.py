#!/usr/bin/env python3
"""Reconstruct and send a Hisense VIDAA /upgrade/check_version request.

Provide your own values; nothing is hardcoded:

    export HISENSE_TOKEN=...        # device access token
    export HISENSE_MAC=...          # MAC the request should use
    export HISENSE_DVC_RSV=...      # model / dvcRsv string

Optional:
    HISENSE_CURRENT_VERSION, HISENSE_STAT_CODE, HISENSE_POST_CODE,
    HISENSE_BRAND_CODE, HISENSE_LANG_ID, HISENSE_HOST
"""
import os
import urllib.error
import urllib.request


def env(name, default=None):
    value = os.environ.get(name, default)
    if value is None:
        raise SystemExit("missing environment variable: " + name)
    return value


def check_version(token, currentVersion, dvcRsv, statCode, postCode,
                  brandCode, mac, langId, host="api.hismarttv.com"):
    body = "msgVersion=513&msgType=256&msgId=66"
    body += f"&currentVersion={currentVersion}&dvcRsv={dvcRsv}"
    if statCode is not None:
        body += f"&statCode={statCode}"
    if postCode is not None:
        body += f"&postCode={postCode}"
    if brandCode is not None:
        body += f"&brandCode={brandCode}"
    if mac is not None:
        body += f"&MAC={mac}"
    body += f"&accessToken={token}&version=7.0&format=0&sourceType=1&languageId={langId}"
    url = f"https://{host}/upgrade/check_version"
    req = urllib.request.Request(
        url, data=body.encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=iso-8859-1",
                 "User-Agent": "HisenseTV"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace"), body, url
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), body, url
    except Exception as e:
        return "ERR", str(e), body, url


if __name__ == "__main__":
    st, resp, body, url = check_version(
        token=env("HISENSE_TOKEN"),
        currentVersion=os.environ.get("HISENSE_CURRENT_VERSION", ""),
        dvcRsv=env("HISENSE_DVC_RSV"),
        statCode=os.environ.get("HISENSE_STAT_CODE"),
        postCode=os.environ.get("HISENSE_POST_CODE", ""),
        brandCode=os.environ.get("HISENSE_BRAND_CODE"),
        mac=env("HISENSE_MAC"),
        langId=os.environ.get("HISENSE_LANG_ID", "0"),
        host=os.environ.get("HISENSE_HOST", "api.hismarttv.com"),
    )
    print("URL:", url)
    print("status:", st)
    print("body:", body)
    print("resp:", resp[:1500])
