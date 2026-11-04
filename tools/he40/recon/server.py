#!/usr/bin/env python3
# Authorized use only: your own device. Rooting can brick the TV. No warranty.
# Purpose: serve recon.html to the TV and capture what the root browser POSTs back.
# Requires: python3 (stdlib only). Default bind is 127.0.0.1; --bind 0.0.0.0 is opt-in.
"""Local recon server for the TV browser.

The TV opens http://<host>:<port>/recon.html. The page can read files through the
browser's file API, POST results to /recon, poll /cmd for one JS command, and
upload chunks to /dump.

There is deliberately NO authentication: the command channel is part of the
design. Bind to 127.0.0.1 by default and use --bind 0.0.0.0 only on a trusted
LAN. Anyone who can reach the port can feed JavaScript to a browser that runs as
root on the TV. Never expose it to the internet.
"""

from __future__ import annotations

import argparse
import datetime
import itertools
import os
import socket
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY = 4 * 1024 * 1024  # larger POSTs are rejected
STATIC_FILES = {
    "/": "recon.html",
    "/recon.html": "recon.html",
    "/index.html": "recon.html",
    "/phase.js": "phase.js",  # optional; absent is fine
}
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".png": "image/png",
    ".txt": "text/plain; charset=utf-8",
}


def die(message):
    sys.exit("error: " + message)


def detect_lan_ip():
    """Best-effort local IPv4 address without contacting a remote host."""
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        infos = []
    for info in infos:
        addr = info[4][0]
        if addr and not addr.startswith("127.") and addr != "0.0.0.0":
            return addr
    return "127.0.0.1"


class ReconServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler, root, pub_dir, capture_dir, dump_dir):
        super().__init__(address, handler)
        self.root = root
        self.pub_dir = pub_dir
        self.capture_dir = capture_dir
        self.dump_dir = dump_dir
        self.live_cmd = os.path.join(root, "live_cmd.txt")
        self.sequence = itertools.count()


class Handler(BaseHTTPRequestHandler):
    server_version = "vidaa-recon/1.0"

    def log_message(self, fmt, *args):
        return

    def _send(self, code, body, ctype="text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body_length(self):
        raw = self.headers.get("Content-Length")
        if raw is None:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    def do_GET(self):
        parts = urllib.parse.urlsplit(self.path)
        path = parts.path

        if path == "/cmd":
            try:
                with open(self.server.live_cmd, "rb") as handle:
                    body = handle.read()
            except FileNotFoundError:
                self._send(204, b"")
                return
            except OSError as exc:
                self._send(500, str(exc).encode("utf-8", "replace"))
                return
            try:
                os.remove(self.server.live_cmd)
            except OSError:
                pass
            self._send(200, body)
            return

        if path.startswith("/pub/"):
            name = os.path.basename(urllib.parse.unquote(path[len("/pub/"):]))
            if not name or name in (".", ".."):
                self._send(400, b"bad name")
                return
            full = os.path.join(self.server.pub_dir, name)
            if not os.path.isfile(full):
                self._send(404, b"not found")
                return
            with open(full, "rb") as handle:
                body = handle.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", 'attachment; filename="%s"' % name)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        name = STATIC_FILES.get(path)
        if name is None:
            self._send(404, b"not found")
            return
        full = os.path.join(self.server.root, name)
        if not os.path.isfile(full):
            self._send(404, b"not found")
            return
        ext = os.path.splitext(full)[1].lower()
        ctype = CONTENT_TYPES.get(ext, "application/octet-stream")
        with open(full, "rb") as handle:
            body = handle.read()
        self._send(200, body, ctype)

    def do_POST(self):
        parts = urllib.parse.urlsplit(self.path)
        path = parts.path
        length = self._body_length()
        if length is None:
            self._send(411, b"length required")
            return
        if length < 0 or length > MAX_BODY:
            self._send(413, b"body too large")
            return
        body = self.rfile.read(length)

        if path == "/dump":
            query = urllib.parse.parse_qs(parts.query)
            try:
                offset = int(query.get("off", ["0"])[0])
            except ValueError:
                self._send(400, b"bad off")
                return
            if offset < 0:
                self._send(400, b"bad off")
                return
            name = os.path.basename(query.get("name", ["dump.bin"])[0])
            if not name or name in (".", ".."):
                self._send(400, b"bad name")
                return
            os.makedirs(self.server.dump_dir, exist_ok=True)
            target = os.path.join(self.server.dump_dir, name)
            try:
                with open(target, "wb" if offset == 0 else "r+b") as handle:
                    handle.seek(offset)
                    handle.write(body)
            except OSError as exc:
                self._send(500, str(exc).encode("utf-8", "replace"))
                return
            print("[+] dump off=%d len=%d -> %s" % (offset, len(body), target), flush=True)
            self._send(200, b"ok")
            return

        if path != "/recon":
            self._send(404, b"not found")
            return

        os.makedirs(self.server.capture_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        seq = next(self.server.sequence)
        target = os.path.join(
            self.server.capture_dir, "recon-%s-%06d.txt" % (stamp, seq)
        )
        with open(target, "wb") as handle:
            handle.write(body)
        print("[+] captured %d bytes -> %s" % (len(body), target), flush=True)
        self._send(200, b"ok")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Serve the VIDAA recon page and capture TV responses.",
        epilog="Anyone who can reach this port can feed JavaScript to a root "
        "browser on the TV. Keep the default loopback bind unless you need "
        "the TV to connect, and never expose it to the internet.",
    )
    parser.add_argument(
        "--bind",
        default="127.0.0.1",
        help="listen address (default: %(default)s; use 0.0.0.0 for the TV)",
    )
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument(
        "--root",
        default=os.path.dirname(os.path.abspath(__file__)),
        help="directory containing recon.html (default: script directory)",
    )
    parser.add_argument("--pub-dir", default=None, help="payload directory (default: <root>/pub)")
    parser.add_argument(
        "--capture-dir", default=None, help="capture directory (default: <root>/captures)"
    )
    parser.add_argument(
        "--dump-dir", default=None, help="chunk dump directory (default: <root>/.re/dumps/tv)"
    )
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.isfile(os.path.join(root, "recon.html")):
        die("recon.html not found in %s" % root)
    if not 1 <= args.port <= 65535:
        die("port out of range: %d" % args.port)
    if not args.bind:
        die("empty --bind")

    pub_dir = os.path.abspath(args.pub_dir or os.path.join(root, "pub"))
    capture_dir = os.path.abspath(args.capture_dir or os.path.join(root, "captures"))
    dump_dir = os.path.abspath(args.dump_dir or os.path.join(root, ".re", "dumps", "tv"))
    os.makedirs(capture_dir, exist_ok=True)
    os.makedirs(dump_dir, exist_ok=True)

    try:
        httpd = ReconServer(
            (args.bind, args.port), Handler, root, pub_dir, capture_dir, dump_dir
        )
    except OSError as exc:
        die("cannot bind %s:%d: %s" % (args.bind, args.port, exc))

    lan_ip = detect_lan_ip()
    print("[*] root:    %s" % root)
    print("[*] pub:     %s" % pub_dir)
    print("[*] capture: %s" % capture_dir)
    print("[*] local:   http://127.0.0.1:%d/recon.html" % args.port)
    print("[*] LAN:     http://%s:%d/recon.html" % (lan_ip, args.port))
    if args.bind in ("127.0.0.1", "localhost", "::1"):
        print(
            "[!] bound to loopback: the TV cannot connect. Re-run with "
            "--bind 0.0.0.0 on a trusted LAN.",
            flush=True,
        )
    else:
        print(
            "[!] reachable from the LAN: anyone who can reach this port can feed "
            "JavaScript to a root browser on the TV. Never expose it to the internet.",
            flush=True,
        )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] stopped")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
