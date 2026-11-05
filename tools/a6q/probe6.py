#!/usr/bin/env python3
import json, sys, websocket
PAGE = sys.argv[1] if len(sys.argv) > 1 else "DF3C9F489556AF4B7ECB7DD23B8A2C17"
EXPR = r"""
(async () => {
  const call = (api, args) => fetch("http://localhost:9009/service/hiutils", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({api,args})}).then(r=>r.text()).then(t=>{try{return JSON.parse(t)}catch(e){return {raw:String(t).slice(0,150)}}});
  const R = async (p) => { const r = await call("fileRead", {path:["../"+p], mode:6}); return (r && r.ret && typeof r.msg === "string") ? r.msg : null; };
  const out = {};
  const tcp6 = await R("proc/net/tcp6");
  out.tcp6_2222 = tcp6 ? tcp6.split("\n").filter(l => l.indexOf(":08AE") !== -1).slice(0,3) : "READ-FAIL";
  const if6 = await R("proc/net/if_inet6");
  out.if_inet6 = if6 ? if6.split("\n").slice(0,10) : "READ-FAIL";
  return JSON.stringify(out);
})()
"""
ws = websocket.create_connection("ws://<TV_IP>:9226/devtools/page/" + PAGE, timeout=40)
ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":EXPR,"returnByValue":True,"awaitPromise":True}}))
while True:
    m = json.loads(ws.recv())
    if m.get("id") == 1:
        r = m.get("result", {})
        if "exceptionDetails" in r: print("EXC:", json.dumps(r["exceptionDetails"])[:300])
        else: print(r.get("result", {}).get("value"))
        break
