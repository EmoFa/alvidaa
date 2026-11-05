#!/usr/bin/env python3
"""alvidaa control server: serves the TV page, bridges it to the TV.

One MQTT/TLS connection to the TV (RemoteNow, port 36669) + one HTTP server
(port 8765) that serves launcher/ and upgrades GET /ws to WebSocket. The page
is stateless: everything it renders is pushed over the WS as JSON.

Auth: tokens.json from pairing (pair.py) — dynamic username + access token,
refreshed automatically from the refresh token. Falls back to the legacy
static login on old firmware when no tokens exist.

Also runs the home watcher (config.watcher): relaunches the launcher whenever
the TV lands on VIDAA's own home screen — the closest VIDAA gets to a default
launcher, since VIDAA has no default-launcher setting.

Usage: venv/bin/python server/vidaa_server.py [tv-ip] [port]
Config: server/config.json (hidden apps, renames, watcher toggle)
"""
import base64
import hashlib
import json
import os
import queue
import socket
import ssl
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import paho.mqtt.client as mqtt

HERE = os.path.dirname(os.path.abspath(__file__))
ICONCACHE = os.path.join(HERE, "iconcache")
ROOT = os.path.join(HERE, "..", "launcher")
KEYS = os.path.join(HERE, "keys")
TOKENS_FILE = os.path.join(KEYS, "tokens.json")
CONFIG_FILE = os.path.join(HERE, "config.json")
RECON_FILE = os.path.join(HERE, "recon-report.json")
HOST = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("HISENSE_HOST", "")
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
MQTT_PORT = 36669
LEGACY_DEVICE = "VIDAALAUNCHER$normal"

# paho 2.x reports MQTT 3.1.1 CONNACK codes as v5 reason codes, so the familiar
# "rc 5" (Not authorized) surfaces as 135 and a bad password as 134. Name them
# on the way out — these are identity rejections, not network failures.
CONNACK_MEANING = {
    134: "bad username or password",
    135: "not authorized",
    136: "server unavailable",
    137: "server busy",
    138: "banned",
}

# ---- doom: the game tile (spawned over SSH from this host, drawn on fb0)

DOOM_KEY = os.path.join(KEYS, "tv_root_ed25519")
DOOM_DIR = "/var/local/doom"

def doom_ssh(cmd, timeout=15):
    """Run a command on the TV over the root SSH channel."""
    return subprocess.run(
        ["ssh", "-p", "2222", "-i", DOOM_KEY,
         "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes",
         f"root@{HOST}", cmd],
        capture_output=True, text=True, timeout=timeout)

def doom_running():
    r = doom_ssh("pidof doom_fb", timeout=10)
    return r.returncode == 0 and r.stdout.strip()

def doom_start():
    if doom_running():
        return {"ok": True, "already": True}
    # auto-kill after an hour in case the exit path is lost; the watcher
    # also stops doom the moment the home watcher bounces back to alvidaa
    r = doom_ssh(f"(cd {DOOM_DIR} && HOME={DOOM_DIR} "
                 "/var/local/busybox setsid /var/local/busybox timeout 3600 "
                 "./doom_fb -iwad doom1.wad > doom.log 2>&1 &); sleep 1; pidof doom_fb")
    pid = r.stdout.strip()
    if r.returncode == 0 and pid:
        return {"ok": True, "pid": pid}
    return {"ok": False, "error": ((r.stderr or r.stdout or "spawn failed")[-200:])}

def doom_stop():
    r = doom_ssh("kill $(pidof doom_fb) 2>/dev/null; sleep 1; pidof doom_fb")
    return {"ok": r.returncode == 0 and not r.stdout.strip()}

DOOM_PAGE = (b"<!doctype html><html><head><meta charset=utf-8><title>DOOM</title></head>"
             b"<body style=\"margin:0;background:#000;color:#333;"
             b"font:16px monospace;padding:8px\">"
             b"<div id=s>DOOM</div>"
             b"<script>fetch('/api/doom/start').then(function(r){return r.json()}).then("
             b"function(j){document.getElementById('s').textContent="
             b"j.ok?'DOOM - press HOME to return':'DOOM failed: '+(j.error||'?')});"
             b"setTimeout(function(){document.body.style.background='#000';"
             b"document.getElementById('s').textContent=''},4000);</script>"
             b"</body></html>")

def cert_paths():
    modern = (os.path.join(KEYS, "vidaa_cert.pem"), os.path.join(KEYS, "vidaa_key.pem"))
    if all(os.path.isfile(p) for p in modern):
        return modern
    return (os.path.join(KEYS, "rcm_certchain_pem.cer"), os.path.join(KEYS, "rcm_pem_privkey.pkcs8"))

def load_tokens():
    try:
        with open(TOKENS_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None

def save_tokens(t):
    with open(TOKENS_FILE, "w") as f:
        json.dump(t, f, indent=2)
    os.chmod(TOKENS_FILE, 0o600)

def load_config():
    cfg = {"hidden": [], "rename": {}, "inputs": {}, "only": [], "shortcuts": [],
           "autoSwitch": False,
           "watcher": {"enabled": True, "app": "Home", "interval": 3, "cooldown": 6}}
    try:
        with open(CONFIG_FILE) as f:
            user = json.load(f)
        if isinstance(user.get("hidden"), list):
            cfg["hidden"] = user["hidden"]
        if isinstance(user.get("rename"), dict):
            cfg["rename"] = user["rename"]
        if isinstance(user.get("inputs"), dict):
            cfg["inputs"] = user["inputs"]
        if isinstance(user.get("watcher"), dict):
            cfg["watcher"].update(user["watcher"])
        if isinstance(user.get("shortcuts"), list):
            cfg["shortcuts"] = user["shortcuts"]
        if isinstance(user.get("only"), list):
            cfg["only"] = user["only"]
        if "autoSwitch" in user:
            cfg["autoSwitch"] = bool(user.get("autoSwitch"))
    except (OSError, ValueError):
        pass
    return cfg

def tls_context():
    cert, key = cert_paths()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.load_cert_chain(certfile=cert, keyfile=key)
    return ctx

def icon_url(app):
    """httpIcon fields look like 'data:image/png;base64,iconDownloadhttps://…'."""
    raw = app.get("httpIcon") or ""
    marker = "iconDownload"
    if raw.startswith("data:image") and marker in raw:
        return raw.split(marker, 1)[1]
    return raw if raw.startswith("http") else None

_icon_locks = {}
_icon_locks_guard = threading.Lock()

def icon_bytes(app_id, url):
    """Fetch (and disk-cache) an app icon; returns (bytes, content_type) or None."""
    os.makedirs(ICONCACHE, exist_ok=True)
    safe = "".join(c for c in app_id if c.isalnum()) or "x"
    data_path = os.path.join(ICONCACHE, safe + ".img")
    type_path = os.path.join(ICONCACHE, safe + ".type")
    try:
        with open(data_path, "rb") as f:
            with open(type_path) as tf:
                return f.read(), tf.read().strip()
    except OSError:
        pass
    with _icon_locks_guard:
        lock = _icon_locks.setdefault(safe, threading.Lock())
    with lock:
        try:  # re-check cache after acquiring the lock
            with open(data_path, "rb") as f:
                with open(type_path) as tf:
                    return f.read(), tf.read().strip()
        except OSError:
            pass
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "alvidaa/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = r.read()
                ctype = (r.headers.get("Content-Type") or "image/png").split(";")[0]
            with open(data_path, "wb") as f:
                f.write(data)
            with open(type_path, "w") as f:
                f.write(ctype)
            return data, ctype
        except Exception:
            return None

def refresh_tokens():
    """Synchronous token refresh using the stored refresh token. Returns new dict or None."""
    t = load_tokens()
    if not t or not t.get("refreshtoken"):
        return None
    out = {}
    done = threading.Event()

    def on_connect(client, userdata, flags, reason_code, properties=None):
        rc = int(getattr(reason_code, "value", reason_code))
        if rc != 0:
            done.set()
            return
        client.subscribe([
            (f"/remoteapp/mobile/{t['_client_id']}/platform_service/data/tokenissuance", 0),
            (f"/remoteapp/mobile/{t['_client_id']}/platform_service/data/gettoken", 0),
        ])
        client.publish(f"/remoteapp/tv/platform_service/{t['_client_id']}/data/gettoken",
                       json.dumps({"refreshtoken": t["refreshtoken"]}))

    def on_message(client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
        except Exception:
            return
        if isinstance(data, dict) and data.get("accesstoken"):
            out.update(data)
            done.set()

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=t["_client_id"],
                    clean_session=True, protocol=mqtt.MQTTv311)
    c.username_pw_set(username=t["_username"], password=t["refreshtoken"])
    c.tls_set_context(tls_context())
    c.on_connect = on_connect
    c.on_message = on_message
    try:
        c.connect(HOST, MQTT_PORT, 30)
        c.loop_start()
        done.wait(10)
    except Exception:
        pass
    finally:
        try:
            c.loop_stop()
            c.disconnect()
        except Exception:
            pass
    if out.get("accesstoken"):
        out["_profile"] = t["_profile"]
        out["_username"] = t["_username"]
        out["_client_id"] = t["_client_id"]
        save_tokens(out)
        print("token refreshed", flush=True)
        return out
    return None

# ---------------------------------------------------------------- MQTT bridge

class TVBridge:
    """One shared MQTT connection; publishes actions, records state pushes."""

    def __init__(self, host):
        self.host = host
        self.q = queue.Queue()
        self.listeners = []
        self.connected = threading.Event()
        self.state = None
        self.apps = None
        self.sources = None
        self.session = load_tokens()
        if self.session:
            self.device = self.session["_client_id"]
            username, password = self.session["_username"], self.session.get("accesstoken", "")
        else:
            self.device = LEGACY_DEVICE
            username, password = "hisenseservice", "multimqttservice"
            print("no tokens.json — using the legacy static login; 2024+ firmware "
                  "rejects this with rc=135 (Not authorized). Run pair.py first.",
                  flush=True)
        self.username = username
        self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                             client_id=self.device, clean_session=True, protocol=mqtt.MQTTv311)
        self.c.username_pw_set(username=username, password=password)
        self.c.tls_set_context(tls_context())
        self.c.on_connect = self._on_connect
        self.c.on_message = self._on_message
        self.last_launch = 0.0
        self.apps_at = 0.0
        self._recovering = False

    def _identity(self):
        """Who the broker thinks we are — the first thing to check on a reject."""
        if not self.session:
            return (f"legacy static login (client_id={self.device}, "
                    f"username={self.username}, no tokens.json)")
        return (f"profile={self.session.get('_profile', '?')} "
                f"client_id={self.device} "
                f"username={self.session.get('_username', '?')} "
                f"accesstoken={'set' if self.session.get('accesstoken') else 'MISSING'}")

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        rc = int(getattr(reason_code, "value", reason_code))
        if rc != 0:
            why = CONNACK_MEANING.get(rc, "rejected")
            print(f"MQTT rejected (rc={rc} — {why}) as {self._identity()}", flush=True)
            if self.session and not self._recovering:
                threading.Thread(target=self._recover_auth, daemon=True).start()
            return
        # exact topics only — this firmware denies wildcard subscriptions
        base = f"/remoteapp/mobile/{self.device}/"
        client.subscribe([
            (base + "ui_service/data/state", 0),
            (base + "ui_service/data/gettvstate", 0),
            (base + "ui_service/data/sourcelist", 0),
            (base + "ui_service/data/applist", 0),
            (base + "ui_service/data/launchapp", 0),
            (base + "platform_service/data/tokenissuance", 0),
            (base + "platform_service/data/gettoken", 0),
            ("/remoteapp/mobile/broadcast/ui_service/state", 0),
        ])
        self.connected.set()

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8")) if msg.payload else None
        except (ValueError, UnicodeDecodeError):
            payload = msg.payload
        self.q.put((msg.topic.rsplit("/", 1)[-1], payload))
        if isinstance(payload, dict):
            topic = msg.topic.rsplit("/", 1)[-1]
            if topic in ("state", "gettvstate") and "statetype" in payload:
                self.state = payload
                st = payload.get("statetype")
                self._emit({"t": "tvstate", "state": st})
                if st == "remote_launcher":
                    threading.Thread(target=self._maybe_bounce_home, daemon=True).start()

    def _emit(self, event):
        for fn in list(self.listeners):
            try:
                fn(event)
            except Exception:
                pass

    def connect(self, timeout=10):
        self.c.connect(self.host, MQTT_PORT)
        self.c.loop_start()
        if not self.connected.wait(timeout):
            # try one token refresh before giving up
            if self.session and refresh_tokens():
                self.session = load_tokens()
                self.c.username_pw_set(username=self.session["_username"],
                                       password=self.session["accesstoken"])
                self.c.connect(self.host, MQTT_PORT)
                if self.connected.wait(timeout):
                    return
            raise TimeoutError(f"MQTT connect to {self.host} failed")
        with open(os.path.join(HERE, ".host"), "w") as f:
            f.write(self.host)

    def _recover_auth(self):
        """Access token expired mid-run: refresh and reconnect the shared client."""
        if self._recovering:
            return
        self._recovering = True
        try:
            if refresh_tokens():
                t = load_tokens()
                self.session = t
                self.c.username_pw_set(username=t["_username"], password=t["accesstoken"])
                self.c.reconnect()
                print("recovered auth after token refresh", flush=True)
            else:
                print("token refresh failed — TV offline? will retry on next reject", flush=True)
        except Exception as e:
            print(f"auth recovery failed: {e}", flush=True)
        finally:
            self._recovering = False

    def disconnect(self):
        try:
            self.c.disconnect()
        finally:
            self.c.loop_stop()

    def call(self, service, action, payload=None):
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        self.c.publish(f"/remoteapp/tv/{service}/{self.device}/actions/{action}", payload or "").wait_for_publish()

    def ask(self, service, action, payload=None, want=list, timeout=6.0):
        self.q.queue.clear()
        self.call(service, action, payload)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                _, p = self.q.get(timeout=max(0.1, deadline - time.time()))
            except queue.Empty:
                break
            if isinstance(p, want):
                return p
        raise TimeoutError(f"no answer for {service}/{action}")

    def apps_list(self):
        # TTL cache: TV-side app installs/uninstalls propagate within a minute.
        # Guard against transient empty lists during boot/pm churn.
        if self.apps is None or time.time() - self.apps_at > 60:
            fresh = self.ask("ui_service", "applist")
            if fresh or not self.apps:
                self.apps = fresh
                self.apps_at = time.time()
        return self.apps or []

    def sources_list(self):
        fresh = self.ask("ui_service", "sourcelist")
        if fresh or not self.sources:
            self.sources = fresh
        return self.sources or []

    def visible_apps(self):
        """applist with config.json filtering applied ("only" allowlist wins)."""
        cfg = load_config()
        only = [o.strip().lower() for o in cfg.get("only", []) if o.strip()]
        hidden = {h.strip().lower() for h in cfg.get("hidden", [])}
        renames = {k.lower(): v for k, v in cfg.get("rename", {}).items()}
        out = []
        for a in self.apps_list():
            name = a.get("name", "")
            if not name:
                continue
            key = name.strip().lower()
            if only and key not in only:
                continue
            if not only and key in hidden:
                continue
            entry = {"name": renames.get(key, name)}
            if icon_url(a):
                entry["icon"] = f"/icon/{a.get('appId')}"
            out.append(entry)
        return out

    def visible_sources(self):
        """sourcelist with config.json input renames/glyphs applied."""
        cfg = load_config()
        inputs = {k.lower(): v for k, v in cfg.get("inputs", {}).items()}
        out = []
        for s in self.sources_list():
            key = (s.get("sourcename") or "").lower()
            over = inputs.get(key, {})
            out.append({"id": s.get("sourceid"),
                        "name": over.get("name") or s.get("displayname") or s.get("sourcename"),
                        "glyph": over.get("glyph", ""),
                        "signal": s.get("is_signal") == "1" or s.get("has_signal") == "1"})
        return out

    def launch(self, name):
        want = name.strip().lower()
        app = next((a for a in self.apps_list() if a.get("name", "").lower() == want), None)
        if app is None:
            app = next((a for a in self.apps_list() if want in a.get("name", "").lower()), None)
        if app is None:
            return {"ok": False, "error": f"app not found: {name}"}
        self.call("ui_service", "launchapp", {k: app[k] for k in ("appId", "name", "url", "urlType", "storeType") if k in app})
        return {"ok": True, "launched": app.get("name")}

    def source(self, sid):
        for s in self.sources_list():
            if str(s.get("sourceid")) == str(sid) or (s.get("sourcename") or "").lower() == str(sid).lower():
                self.call("ui_service", "changesource", s)
                return {"ok": True, "switched": s.get("displayname") or s.get("sourcename")}
        return {"ok": False, "error": f"source not found: {sid}"}

    def snapshot(self):
        cfg = load_config()
        out = {"t": "hello", "state": (self.state or {}).get("statetype"),
               "autoSwitch": bool(cfg.get("autoSwitch", False)),
               "shortcuts": [sc for sc in cfg.get("shortcuts", [])
                             if sc.get("name") and sc.get("url")]}
        try:
            apps_raw = self.apps_list()
            out["installed"] = any(a.get("appId") == "vidaa-home" for a in apps_raw)
        except Exception as e:
            out["installed"], out["apps"], out["apps_error"] = False, None, str(e)
        try:
            out["apps"] = self.visible_apps()
        except Exception as e:
            out["apps"], out["apps_error"] = None, str(e)
        try:
            out["sources"] = self.visible_sources()
        except Exception as e:
            out["sources"], out["sources_error"] = None, str(e)
        return out

    def _maybe_bounce_home(self):
        cfg = load_config()
        w = cfg.get("watcher", {})
        st = (self.state or {}).get("statetype")
        if w.get("enabled", True) and st == "remote_launcher" \
                and time.time() - self.last_launch > w.get("cooldown", 6):
            self.last_launch = time.time()
            threading.Thread(target=doom_stop, daemon=True).start()
            r = self.launch_home(w.get("app", "Home"))
            print(f"watcher: VIDAA home detected -> {r}", flush=True)

    def launch_home(self, name="Home"):
        """Launch our launcher entry — match by content, not name-first:
        stale duplicates of 'Home' (e.g. pointing at an old host) otherwise win."""
        apps = self.apps_list()
        app = next((a for a in apps if f":{PORT}/" in (a.get("url") or "")), None)
        if app is None:
            app = next((a for a in apps if a.get("appId") == "vidaa-home"), None)
        if app is None:
            app = next((a for a in apps if a.get("name", "").lower() == name.lower()), None)
        if app is None:
            return {"ok": False, "error": "launcher app not found in applist"}
        self.call("ui_service", "launchapp", {k: app[k] for k in ("appId", "name", "url", "urlType", "storeType") if k in app})
        return {"ok": True, "launched": app.get("name"), "url": app.get("url")}

    # ---- home watcher: the de-facto default launcher

    def watcher_loop(self):
        cycle = 0
        last_sources_json = ""
        last_apps_json = ""
        while True:
            try:
                cfg = load_config()
                w = cfg.get("watcher", {})
                if self.connected.is_set():
                    # poll gettvstate as fallback; _on_message handles instant bounce on reply/push
                    self.call("ui_service", "gettvstate")
                    self._maybe_bounce_home()
                    # live source signal refresh every ~9s
                    if cycle % 3 == 0:
                        try:
                            srcs = self.visible_sources()
                            sj = json.dumps(srcs, sort_keys=True)
                            if sj != last_sources_json:
                                last_sources_json = sj
                                self._emit({"t": "sources", "sources": srcs})
                        except Exception:
                            pass
                    # app list / shortcuts refresh every ~60s (config edits propagate)
                    if cycle % 20 == 19:
                        try:
                            payload = {"apps": self.visible_apps(),
                                       "shortcuts": [sc for sc in cfg.get("shortcuts", [])
                                                     if sc.get("name") and sc.get("url")]}
                            aj = json.dumps(payload, sort_keys=True)
                            if aj != last_apps_json:
                                last_apps_json = aj
                                self._emit({"t": "apps", **payload})
                        except Exception:
                            pass
                cycle += 1
                time.sleep(w.get("interval", 3))
            except Exception as e:
                print(f"watcher: {e.__class__.__name__}: {e}", flush=True)
                time.sleep(5)

# ------------------------------------------------------------------ WebSocket

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

class WS:
    def __init__(self, rfile, wfile):
        self.rfile, self.wfile = rfile, wfile
        self.open = True
        self.lock = threading.Lock()  # pushes (mqtt thread) vs replies (handler)

    @staticmethod
    def accept_key(key):
        return base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()

    def recv_text(self):
        hdr = self.rfile.read(2)
        if len(hdr) < 2:
            self.open = False
            return None
        opcode, length = hdr[0] & 0x0F, hdr[1] & 0x7F
        if length == 126:
            length = struct.unpack(">H", self.rfile.read(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self.rfile.read(8))[0]
        mask = self.rfile.read(4) if hdr[1] & 0x80 else b"\x00\x00\x00\x00"
        data = self.rfile.read(length)
        if hdr[1] & 0x80:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        if opcode == 8:
            self.open = False
            return None
        return data.decode("utf-8", "replace")

    def send_text(self, text):
        data = text.encode()
        n = len(data)
        header = bytes([0x81])
        if n < 126:
            header += bytes([n])
        elif n < 65536:
            header += bytes([126]) + struct.pack(">H", n)
        else:
            header += bytes([127]) + struct.pack(">Q", n)
        with self.lock:
            self.wfile.write(header + data)
            self.wfile.flush()

# ---------------------------------------------------------------- HTTP server

class Handler(SimpleHTTPRequestHandler):
    bridge = None
    protocol_version = "HTTP/1.1"

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        # access log to the journal: client, Host header, request line
        print(f"{self.client_address[0]} host={self.headers.get('Host')} "
              f"{fmt % args}", flush=True)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        # CORS preflight — Cobalt sends it for cross-origin POSTs from file://
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}

        if u.path == "/ws":
            key = self.headers.get("Sec-WebSocket-Key")
            if not key or "websocket" not in (self.headers.get("Upgrade") or "").lower():
                self.send_error(400, "websocket upgrade required")
                return
            self.send_response(101, "Switching Protocols")
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", WS.accept_key(key))
            self.end_headers()
            # NOTE: no settimeout here — a timed-out read poisons the buffered
            # rfile and kills the connection ~1s later. select() instead.
            self.connection.settimeout(None)
            ws = WS(self.rfile, self.wfile)
            ws.send_text(json.dumps(self.bridge.snapshot()))
            def push(event):
                try:
                    ws.send_text(json.dumps(event))
                except Exception:
                    try: self.bridge.listeners.remove(push)
                    except ValueError: pass
            self.bridge.listeners.append(push)
            import select
            while ws.open:
                r, _, _ = select.select([self.connection], [], [], 0.5)
                if not r:
                    continue  # idle; keep the connection open
                try:
                    text = ws.recv_text()
                except Exception:
                    break
                if text is None:
                    break
                try:
                    m = json.loads(text)
                except ValueError:
                    continue
                if m.get("t") == "launch":
                    ws.send_text(json.dumps(self.bridge.launch(m.get("name", ""))))
                elif m.get("t") == "source":
                    ws.send_text(json.dumps(self.bridge.source(m.get("id", ""))))
            try:
                self.bridge.listeners.remove(push)
            except ValueError:
                pass
            self.close_connection = True
            return

        if u.path.startswith("/icon/"):
            app_id = u.path[len("/icon/"):]
            url = None
            for a in self.bridge.apps_list():
                if str(a.get("appId")) == app_id and icon_url(a):
                    url = icon_url(a)
                    break
            if not url:
                self.send_error(404)
                return
            got = icon_bytes(app_id, url)
            if not got:
                self.send_error(404)
                return
            body, ctype = got
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "max-age=604800")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if u.path == "/api/state":
            return self._json({"ok": True, "state": (self.bridge.state or {}).get("statetype")})
        if u.path == "/api/launch":
            return self._json(self.bridge.launch(q.get("name", "")))
        if u.path == "/api/source":
            return self._json(self.bridge.source(q.get("id", "")))
        if u.path == "/api/recon":
            try:
                with open(RECON_FILE) as f:
                    return self._json(json.load(f))
            except (OSError, ValueError):
                return self._json({"ok": False,
                                   "error": "no recon report yet — open /recon.html on the TV"})
        if u.path == "/api/open":
            url = q.get("url", "")
            if not url.startswith("http"):
                return self._json({"ok": False, "error": "http url required"})
            self.bridge.call("ui_service", "launchapp",
                             {"appId": "vidaa-recon", "name": "Recon",
                              "url": url, "urlType": "1", "storeType": "custom"})
            return self._json({"ok": True, "opened": url})
        if u.path == "/doom":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(DOOM_PAGE)))
            self.end_headers()
            self.wfile.write(DOOM_PAGE)
            return
        if u.path == "/api/doom/start":
            threading.Thread(target=lambda: doom_start(), daemon=True).start()
            return self._json({"ok": True, "spawning": True})
        if u.path == "/api/doom/stop":
            return self._json(doom_stop())
        return super().do_GET()

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/probe":
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                data = {"raw": raw.decode("utf-8", "replace")}
            try:
                with open(os.path.join(HERE, "probe-report.json"), "a") as f:
                    f.write(json.dumps(data) + "\n")
                self._json({"ok": True})
            except OSError as e:
                self._json({"ok": False, "error": str(e)})
            return
        if u.path == "/api/recon":
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                data = {"raw": raw.decode("utf-8", "replace")}
            try:
                with open(RECON_FILE, "w") as f:
                    json.dump(data, f, indent=2)
                return self._json({"ok": True, "bytes": len(raw)})
            except OSError as e:
                return self._json({"ok": False, "error": str(e)})
        self.send_error(404)

def main():
    if not HOST:
        sys.exit("usage: vidaa_server.py <tv-ip> [port]   (or set HISENSE_HOST)")
    bridge = TVBridge(HOST)
    try:
        bridge.connect()
        print(f"connected to TV at {HOST}:{MQTT_PORT} "
              f"({'token auth' if bridge.session else 'legacy auth'})", flush=True)
    except Exception as e:
        print(f"TV not reachable ({e}); serving page in offline mode", flush=True)
    Handler.bridge = bridge
    threading.Thread(target=bridge.watcher_loop, daemon=True).start()
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"launcher at http://<this-host>:{PORT}/  (WS at /ws) — watcher running", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        bridge.disconnect()

if __name__ == "__main__":
    main()
