#!/usr/bin/env python3
"""Navigate the target to a URL and read the rendered content."""
import json, sys, time, websocket
TID = "369AE7CFC7DBD02E41263A0D3D9A0596"
url = sys.argv[1]
ws = websocket.create_connection("ws://<TV_IP>:9226/devtools/page/" + TID, timeout=15)
_id = [0]
def send(method, params=None):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": method, "params": params or {}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == _id[0]:
            return m.get("result", {})
def ev(expr):
    r = send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    res = r.get("result", {})
    if "exceptionDetails" in res:
        return "EXC: " + json.dumps(res["exceptionDetails"])[:200]
    return res.get("result", {}).get("value")
print("nav:", send("Page.navigate", {"url": url}))
time.sleep(2.5)
print("href:", ev("location.href"))
print("content:", str(ev("document.body ? document.body.innerText.slice(0, 1500) : '(no body)'")))
