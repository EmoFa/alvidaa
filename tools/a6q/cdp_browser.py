#!/usr/bin/env python3
"""Browser-level CDP: create a file:// target, attach, read content."""
import json, sys, time, websocket
BV = json.loads(__import__("urllib.request", fromlist=["urlopen"]).urlopen("http://<TV_IP>:9226/json/version", timeout=8).read())["webSocketDebuggerUrl"]
url = sys.argv[1]
bws = websocket.create_connection(BV, timeout=15)
_id = [0]
def bsend(method, params=None):
    _id[0] += 1
    bws.send(json.dumps({"id": _id[0], "method": method, "params": params or {}}))
    while True:
        m = json.loads(bws.recv())
        if m.get("id") == _id[0]:
            return m.get("result", {})
r = bsend("Target.createTarget", {"url": url})
print("createTarget:", r)
tid = r.get("targetId")
if not tid: sys.exit(1)
time.sleep(2.5)
# attach to the new target
aws = websocket.create_connection("ws://<TV_IP>:9226/devtools/page/" + tid, timeout=15)
def ev(expr):
    aws.send(json.dumps({"id": 99, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True}}))
    while True:
        m = json.loads(aws.recv())
        if m.get("id") == 99:
            res = m.get("result", {})
            if "exceptionDetails" in res: return "EXC: " + json.dumps(res["exceptionDetails"])[:200]
            return res.get("result", {}).get("value")
print("href:", ev("location.href"))
print("content:", str(ev("document.body ? document.body.innerText.slice(0, 1200) : '(no body)'")))
