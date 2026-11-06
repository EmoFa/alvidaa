#!/usr/bin/env python3
"""Pair with a VIDAA TV and capture long-lived tokens.

Modern VIDAA firmware (2024+, transport_protocol 3290+) rejects the old static
MQTT login (`Not authorized` + an on-screen "app outdated" popup per attempt).
This tool walks the app-style handshake:

  dynamic credentials -> vidaa_app_connect -> TV shows 4-digit PIN
  -> authenticationcode -> gettoken -> tokenissuance -> tokens.json

Usage: venv/bin/python pair.py [tv-ip] [pin]
  tv-ip  required unless $HISENSE_HOST is set (there is no built-in default —
         the TV's address is DHCP-assigned and moves)
  pin    the 4-digit code shown on the TV; prompts on stdin if omitted

Certificates: keys/vidaa_cert.pem + keys/vidaa_key.pem (from the official
app's El.p12 keystore) if present, else the 2018 RemoteNOW pair.
"""
import hashlib
import json
import os
import queue
import select
import ssl
import sys
import time

import paho.mqtt.client as mqtt

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = os.path.join(HERE, "keys")
TOKENS_FILE = os.path.join(KEYS, "tokens.json")
HOST = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("HISENSE_HOST", "")
PIN_ARG = sys.argv[2] if len(sys.argv) > 2 else None

# --- credential derivation (VIDAA dynamic auth) ------------------------------
CLIENT_ID_PATTERN = "38D65DC30F45109A369A86FCE866A85B"
MODERN_SALT = "h!i@s#$v%i^d&a*a"
STANDARD_SALT = "h*i&s%e!r^v0i1c9"
XOR_MASK = 6239759785777146216
TV_MAC = os.environ.get("TV_MAC", "")  # TV WiFi MAC — from its SSDP descriptor (see docs/models/50A51HUV/09.01O.P0813/findings/01-mqtt-bridge.md)


def format_colon_mac(mac):
    """Convert a 12-hex-char SSDP MAC (e.g. 'e85177e4d412') to 'E8:51:77:E4:D4:12'."""
    clean = mac.replace(":", "").replace("-", "").strip().upper()
    if len(clean) == 12 and all(c in "0123456789ABCDEF" for c in clean):
        return ":".join(clean[i:i + 2] for i in range(0, 12, 2))
    return mac


def creds(profile, mac=None):
    mac = TV_MAC if mac is None else mac
    if ":" in mac:
        mac = mac.upper()
    ts = int(time.time())
    digest = hashlib.md5(f"{CLIENT_ID_PATTERN}${mac}".encode()).hexdigest().upper()
    client_id = f"{mac}$his${digest[:6]}_vidaacommon_001"
    if profile == "legacy":
        return client_id, "hisenseservice", "multimqttservice"
    if profile == "modern":
        salt, username = MODERN_SALT, f"his${ts ^ XOR_MASK}"
    elif profile == "middle":
        salt, username = STANDARD_SALT, f"his${ts ^ XOR_MASK}"
    else:  # standard / remotenow
        salt, username = STANDARD_SALT, f"his${ts}"
    digit_sum = sum(int(c) for c in str(ts)) % 10
    salt_hash = hashlib.md5(f"his{digit_sum}{salt}".encode()).hexdigest().upper()
    password = hashlib.md5(f"{ts}${salt_hash[:6]}".encode()).hexdigest().upper()
    return client_id, username, password

def cert_paths():
    modern = (os.path.join(KEYS, "vidaa_cert.pem"), os.path.join(KEYS, "vidaa_key.pem"))
    if all(os.path.isfile(p) for p in modern):
        return modern
    return (os.path.join(KEYS, "rcm_certchain_pem.cer"), os.path.join(KEYS, "rcm_pem_privkey.pkcs8"))

PROFILES = ["modern", "middle", "standard", "legacy"]

class Pairer:
    def __init__(self, profile, host=None, mac=None):
        self.profile = profile
        self.host = host or HOST
        self.mac = TV_MAC if mac is None else mac
        self.client_id, self.username, self.password = creds(profile, mac=self.mac)
        self.rc = None
        self.pushes = queue.Queue()
        cert, key = cert_paths()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.load_cert_chain(certfile=cert, keyfile=key)
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id,
                        clean_session=True, protocol=mqtt.MQTTv311)
        c.username_pw_set(username=self.username, password=self.password)
        c.tls_set_context(ctx)
        c.on_connect = self._on_connect
        c.on_message = self._on_message
        self.c = c

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        self.rc = int(getattr(reason_code, "value", reason_code))

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except Exception:
            payload = {"_raw": msg.payload.decode(errors="replace")}
        self.pushes.put((msg.topic.rsplit("/", 1)[-1], payload))

    def connect(self, timeout=6):
        self.c.connect(self.host, 36669, 30)
        self.c.loop_start()
        deadline = time.time() + timeout
        while time.time() < deadline and self.rc is None:
            time.sleep(0.1)
        return self.rc == 0

    def subscribe_pairing_topics(self):
        # some firmware denies wildcard subscriptions — use exact topics
        base = f"/remoteapp/mobile/{self.client_id}/"
        self.c.on_subscribe = lambda c, u, mid, grants, *a: print(
            f"  suback grants: {grants}", flush=True)
        self.c.subscribe([
            (base + "ui_service/data/authentication", 0),
            (base + "ui_service/data/authenticationcode", 0),
            (base + "ui_service/data/authenticationcodeclose", 0),
            (base + "ui_service/data/authenticationcodetoast", 0),
            (base + "ui_service/data/vidaa_app_connect", 0),
            (base + "platform_service/data/tokenissuance", 0),
            (base + "platform_service/data/gettoken", 0),
        ])

    def stop(self):
        try:
            self.c.loop_stop()
            self.c.disconnect()
        except Exception:
            pass

def wait_for(q, want_topic, timeout):
    return wait_for_any(q, (want_topic,), timeout)

def wait_for_any(q, want_topics, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            topic, payload = q.get(timeout=max(0.1, deadline - time.time()))
        except queue.Empty:
            break
        if topic in want_topics:
            return payload
    return None

def pair(host=None, pin_arg=None):
    host = host or HOST
    if not host:
        sys.exit("usage: pair.py <tv-ip> [pin]   (or set HISENSE_HOST)")
    pin_arg = pin_arg if pin_arg is not None else PIN_ARG

    print(f"TV: {host}, cert: {'vidaa (2024)' if 'vidaa_cert' in str(cert_paths()) else 'RemoteNOW (2018)'}")
    tokens = None
    active_mac = TV_MAC
    for profile in PROFILES:
        p = Pairer(profile, host=host, mac=active_mac)
        print(f"[{profile}] connecting as {p.username} (client_id={p.client_id}) ...", flush=True)
        if not p.connect():
            # U6 / transport_protocol=3160 (e.g. 65U8HAU V0000.06.29X.P0813) rejects
            # unformatted 12-hex-char SSDP MACs with rc=133 (Client Identifier not valid)
            # and requires uppercase colon-separated XX:XX:XX:XX:XX:XX.
            colon_mac = format_colon_mac(active_mac)
            if p.rc == 133 and colon_mac != active_mac:
                p.stop()
                active_mac = colon_mac
                print(f"[{profile}] rc=133 (Client Identifier not valid) — retrying with colon-formatted TV_MAC={active_mac}", flush=True)
                p = Pairer(profile, host=host, mac=active_mac)
                if not p.connect():
                    print(f"[{profile}] rejected (rc={p.rc}); next profile", flush=True)
                    p.stop()
                    continue
            else:
                print(f"[{profile}] rejected (rc={p.rc}) — TV shows the 'outdated app' popup; next profile")
                p.stop()
                continue
        print(f"[{profile}] MQTT session established", flush=True)
        p.subscribe_pairing_topics()
        time.sleep(0.5)
        # trigger the PIN dialog ONCE (re-triggering rotates the code)
        p.c.publish(f"/remoteapp/tv/ui_service/{p.client_id}/actions/vidaa_app_connect",
                    '{"app_version":2,"connect_result":0,"device_type":"Mobile App"}')
        dialog = wait_for_any(p.pushes, ("authentication", "authenticationcode"), 6)
        print(f"[{profile}] PIN dialog push: {dialog}", flush=True)
        print(f"\n>>> LOOK AT THE TV — enter the 4-digit code shown there (stdin or {os.path.join(KEYS, '.pin')}) <<<", flush=True)
        pin = pin_arg
        pin_file = os.path.join(KEYS, ".pin")
        deadline = time.time() + 240
        while not (pin and len(pin) == 4 and pin.isdigit()):
            # surface whatever the TV pushes while we wait (no re-trigger: it rotates the PIN)
            try:
                topic, payload = p.pushes.get(timeout=0.3)
                print(f"  push {topic}: {str(payload)[:140]}", flush=True)
                if topic == "authenticationcodeclose":
                    print("TV closed the PIN dialog (~30s window expired); rerun and submit within 30s")
                    p.stop()
                    sys.exit(2)
                continue  # pushes during wait are informational; keep looping for pin
            except queue.Empty:
                pass
            if sys.stdin and sys.stdin.isatty():
                r, _, _ = select.select([sys.stdin], [], [], 0.1)
                if r:
                    line = sys.stdin.readline().strip()
                    if len(line) == 4 and line.isdigit():
                        pin = line
                        break
            try:
                pin = open(pin_file).read().strip()
            except OSError:
                pin = None
            if pin and len(pin) == 4 and pin.isdigit():
                os.remove(pin_file)
                break
            if time.time() > deadline:
                print("timed out waiting for PIN; rerun")
                p.stop()
                sys.exit(2)
        if not (pin and len(pin) == 4 and pin.isdigit()):
            pin = pin_arg
        p.c.publish(f"/remoteapp/tv/ui_service/{p.client_id}/actions/authenticationcode",
                    json.dumps({"authNum": int(pin)}))
        print(f"[{profile}] PIN submitted — waiting for validation", flush=True)
        result = None
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                topic, payload = p.pushes.get(timeout=max(0.1, deadline - time.time()))
            except queue.Empty:
                break
            print(f"  push {topic}: {str(payload)[:140]}", flush=True)
            if topic == "authenticationcode" and isinstance(payload, dict):
                result = payload
                break
        if not isinstance(result, dict) or int(result.get("result", 0)) != 1:
            print(f"[{profile}] PIN rejected: {result}")
            p.stop()
            sys.exit(3)
        print(f"[{profile}] PIN accepted — requesting tokens")
        p.c.publish(f"/remoteapp/tv/platform_service/{p.client_id}/data/gettoken", '{"refreshtoken": ""}')
        # NOTE: only publish authenticationcodeclose AFTER result == 1; sending it
        # on an unverified PIN popup on V0000.06.29X.P0813 hides the dialog without
        # releasing hisenseUI's modal input grab.
        p.c.publish(f"/remoteapp/tv/ui_service/{p.client_id}/actions/authenticationcodeclose")
        tok = wait_for(p.pushes, "tokenissuance", 15) or wait_for(p.pushes, "gettoken", 5)
        p.stop()
        if isinstance(tok, dict) and tok.get("accesstoken"):
            tokens = tok
            tokens["_profile"] = profile
            tokens["_username"] = p.username
            tokens["_client_id"] = p.client_id
            break
        print(f"[{profile}] no token issuance; trying next profile")

    if not tokens:
        print("FAILED: no profile produced tokens. See tv/vidaa/README (cert requirements).")
        sys.exit(4)

    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    os.chmod(TOKENS_FILE, 0o600)
    print(f"PAIRED — tokens.json written (profile={tokens['_profile']}, "
          f"access valid {tokens.get('accesstoken_duration_day', '?')} days)")
    return True

def main():
    host = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("HISENSE_HOST", "")
    pin = sys.argv[2] if len(sys.argv) > 2 else None
    pair(host, pin)

if __name__ == "__main__":
    main()
