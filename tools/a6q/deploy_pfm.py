#!/usr/bin/env python3
"""Deploy a PFMCheck source to TV: live + backup + DebugPowerup, via CDP -> localhost:9009 bridge.
Usage: deploy_pfm.py <pfmcheck_file>"""
import json, os, sys, urllib.request, websocket
SRC = sys.argv[1]
CONTENT = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), SRC)).read()
targets = json.load(urllib.request.urlopen("http://<TV_IP>:9226/json/list"))
PAGE = targets[0]["id"]
EXPR = """
(async () => {
  const content = %s;
  const dbg = "1";
  const call = (api, args) => fetch("http://localhost:9009/service/hiutils",
    {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({api,args})})
    .then(r=>r.text()).then(t=>{try{return JSON.parse(t)}catch(e){return {raw:String(t).slice(0,150)}}});
  const fetchFile = (url, dir) => fetch("http://localhost:9009/service/basic/fetcher",
    {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({api:"fetchFile",args:{url:url,directory:dir,timeout:20}})})
    .then(r=>r.text()).then(t=>t.slice(0,150));
  const R = (p) => call("fileRead", {path:["../var/local/"+p], mode:6});
  const out = {};
  const targets = [["pfmParse/PFMCheck", content], [".a6q_PFMCheck_backup", content], ["DebugPowerup", dbg]];
  for (const [p, data] of targets) {
    const isPfm = p !== "DebugPowerup";
    let r = await call("fileWrite", {path:["../var/local/"+p], mode:6, writedata: data});
    out["write:"+p] = {ret: r && r.ret, code: r && r.code};
    const back = await R(p);
    const okTxt = back && back.ret && typeof back.msg === "string" &&
      (isPfm ? back.msg.indexOf("runSignal=PFM") !== -1 && back.msg === data : back.msg.trim() === data.trim());
    if (!okTxt) {
      const url = isPfm ? "http://<LAN_BOX>:8899/" + %s : "http://<LAN_BOX>:8899/debugpower_v10";
      out["write:"+p].fallback = await fetchFile(url, "/var/local/"+p);
      const back2 = await R(p);
      out["write:"+p].verified = !!(back2 && back2.ret && typeof back2.msg === "string" &&
        (isPfm ? back2.msg.indexOf("runSignal=PFM") !== -1 : true));
    } else {
      out["write:"+p].verified = true;
    }
  }
  return JSON.stringify(out);
})()
""" % (json.dumps(CONTENT), json.dumps(SRC))
ws = websocket.create_connection("ws://<TV_IP>:9226/devtools/page/" + PAGE, timeout=90)
ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                    "params": {"expression": EXPR, "returnByValue": True, "awaitPromise": True}}))
while True:
    m = json.loads(ws.recv())
    if m.get("id") == 1:
        r = m.get("result", {})
        if "exceptionDetails" in r:
            print("EXC:", json.dumps(r["exceptionDetails"])[:500]); sys.exit(1)
        print(r.get("result", {}).get("value"))
        break
