#!/usr/bin/env python3
import json, sys, websocket
PAGE = sys.argv[1] if len(sys.argv) > 1 else "DF3C9F489556AF4B7ECB7DD23B8A2C17"
EXPR = r"""
(async () => {
  const call = (api, args) => fetch("http://localhost:9009/service/hiutils", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({api,args})}).then(r=>r.text()).then(t=>{try{return JSON.parse(t)}catch(e){return {raw:String(t).slice(0,150)}}});
  const out = {};
  const tcp = await call("fileRead", {path:["../proc/net/tcp"], mode:6});
  const lines = (tcp && tcp.ret && typeof tcp.msg === "string") ? tcp.msg.split("\n") : ["READ-FAIL:" + JSON.stringify(tcp).slice(0,100)];
  out.nlines = lines.length;
  out.tcp_2222 = lines.filter(l => l.indexOf(":08AE") !== -1).slice(0,5);
  out.tcp_2323 = lines.filter(l => l.indexOf(":0913") !== -1).slice(0,5);
  out.tcp_9226 = lines.filter(l => l.indexOf(":240A") !== -1).slice(0,5);
  async function probe(url) {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), 4000);
    const t0 = Date.now();
    try { await fetch(url, {mode:"no-cors", signal: ctl.signal}); clearTimeout(t); return "no-error(" + (Date.now()-t0) + "ms)"; }
    catch (e) { clearTimeout(t); return String(e && e.name || e) + "(" + (Date.now()-t0) + "ms)"; }
  }
  out.probe_127_2222 = await probe("http://127.0.0.1:2222/");
  out.probe_lan_2222 = await probe("http://<TV_IP>:2222/");
  out.probe_127_2323 = await probe("http://127.0.0.1:2323/");
  return JSON.stringify(out);
})()
"""
ws = websocket.create_connection("ws://<TV_IP>:9226/devtools/page/" + PAGE, timeout=60)
ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":EXPR,"returnByValue":True,"awaitPromise":True}}))
while True:
    m = json.loads(ws.recv())
    if m.get("id") == 1:
        r = m.get("result", {})
        if "exceptionDetails" in r:
            print("EXC:", json.dumps(r["exceptionDetails"])[:400])
        else:
            print(r.get("result", {}).get("value"))
        break
