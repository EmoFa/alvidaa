#!/usr/bin/env python3
"""Minimal CDP driver: evaluate JS in a TV browser page."""
import json, sys, websocket
TARGET = sys.argv[1] if len(sys.argv) > 1 else "369AE7CFC7DBD02E41263A0D3D9A0596"
ws = websocket.create_connection("ws://<TV_IP>:9226/devtools/page/" + TARGET, timeout=15)
def ev(expr, i=1):
    ws.send(json.dumps({"id": i, "method": "Runtime.evaluate",
                        "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == i:
            r = m.get("result", {})
            if "exceptionDetails" in r: return "EXC: " + json.dumps(r["exceptionDetails"])[:300]
            v = r.get("result", {}).get("value")
            return v if v is not None else r.get("result", {}).get("description", "")
if __name__ == "__main__":
    expr = sys.stdin.read()
    print(ev(expr))
