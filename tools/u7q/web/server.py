#!/usr/bin/env python3
"""LAN-only server for the VIDAA root-dropbear installer.

Serves the two pages and the artifacts they pull, and stores whatever the TV
POSTs back under captures/. No external domains, no TLS, no auth.

    python3 server.py [port]        # default 9000, binds 0.0.0.0
"""
import datetime
import http.server
import itertools
import os
import socketserver
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CAP = os.path.join(HERE, "captures")
os.makedirs(CAP, exist_ok=True)
SEQ = itertools.count()

PAGES = {
    "/": "install.html",
    "/install.html": "install.html",
    "/trigger.html": "trigger.html",
    "/probe.html": "probe.html",
    "/check.html": "check.html",
}


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path != "/favicon.ico":
            print("[GET] %s" % path, flush=True)

        if path.startswith("/pub/"):
            name = os.path.basename(path)
            p = os.path.join(HERE, "pub", name)
            if os.path.isfile(p):
                with open(p, "rb") as fh:
                    self._send(200, fh.read(), "application/octet-stream")
            else:
                self._send(404, "not found", "text/plain")
            return

        name = PAGES.get(path)
        if name:
            p = os.path.join(HERE, name)
            if os.path.isfile(p):
                self._send(200, open(p, "rb").read(), "text/html; charset=utf-8")
                return
        self._send(404, "not found", "text/plain")

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        n = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(n).decode("utf-8", "replace")
        if path != "/recon":
            self._send(404, "not found", "text/plain")
            return
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        p = os.path.join(CAP, "run-%s-%06d.txt" % (ts, next(SEQ)))
        with open(p, "w") as fh:
            fh.write(body)
        print("[+] captured %d bytes -> %s" % (len(body), p), flush=True)
        self._send(200, "ok", "text/plain")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("0.0.0.0", port), Handler) as httpd:
        print("[*] serving on http://0.0.0.0:%d/  (captures -> %s)" % (port, CAP), flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
