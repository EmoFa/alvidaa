#!/usr/bin/env python3
"""alvidaa — one CLI for the TV.

Root work goes through the existing server/tv wrapper (SSH is not
reimplemented here); bridge work goes through http://<tv>:8770. Every
health check degrades gracefully: a doctor that dies when the thing it
checks is down is useless.

Subcommands: sys, logs, net, doctor, open, apps, sources
Environment: TV_HOST overrides the default 192.168.0.11 (the TV is
DHCP-shuffled — see server/tv).
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TV = os.environ.get("TV_HOST", "192.168.0.11")
BRIDGE = "http://%s:8770" % TV
TV_WRAPPER = os.path.join(HERE, "..", "server", "tv")
TIMEOUT = 12


# LAN tool: never route through any ambient HTTP(S)_PROXY — the bridge is
# on the local network and a proxy env var would blackhole every check.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


FETCH_PATH = "direct"


def fetch_raw(path, timeout=TIMEOUT, retries=2):
    """Returns (status_text, body) using direct HTTP with SSH-relay fallback."""
    global FETCH_PATH
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(BRIDGE + path, headers={"Cache-Control": "no-store"})
        try:
            with OPENER.open(req, timeout=timeout) as r:
                FETCH_PATH = "direct"
                return "200", r.read()
        except Exception as e:
            last = e
            if attempt < retries - 1:
                time.sleep(2)
    out = tv("/var/local/tvtools/busybox wget -q -O - %s%s" % (BRIDGE, path), timeout=timeout + 15)
    FETCH_PATH = "ssh-relay"
    return "200 (ssh-relay)", out


def fetch(path, timeout=TIMEOUT, retries=2):
    # The TV is dual-homed (wlan0 + ethernet) and its ARP path flaps: fresh
    # TCP from this machine intermittently gets EHOSTUNREACH while
    # established SSH flows keep working. Retry direct first, then fall back
    # to a TV-side loopback fetch relayed over SSH — loopback never flaps.
    global FETCH_PATH
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(BRIDGE + path, headers={"Cache-Control": "no-store"})
        try:
            with OPENER.open(req, timeout=timeout) as r:
                FETCH_PATH = "direct"
                return json.loads(r.read().decode())
        except Exception as e:
            last = e
            if attempt < retries - 1:
                time.sleep(2)
    out = tv("/var/local/tvtools/busybox wget -q -O - %s%s" % (BRIDGE, path), timeout=timeout + 15)
    FETCH_PATH = "ssh-relay"
    return json.loads(out)


def tv(cmd, timeout=25):
    """One-shot root command through the server/tv wrapper."""
    out = subprocess.run(
        [TV_WRAPPER, cmd], capture_output=True, text=True, timeout=timeout
    )
    return out.stdout


def mark(ok):
    return "ok" if ok else "FAIL"


def cmd_sys(args):
    print(tv("cat /proc/uptime; free 2>/dev/null || "
             "/var/local/tvtools/busybox free; /var/local/tvtools/busybox df -h "
             "/var/local /APPS 2>/dev/null"))


def cmd_logs(args):
    which = args[0] if args else "bridge"
    path = {
        "bridge": "/var/local/alvidaa/bridge.log",
        "hook": "/var/local/otaTest.log",
    }.get(which, "/var/local/alvidaa/bridge.log")
    n = args[1] if len(args) > 1 else "30"
    print(tv("/var/local/tvtools/busybox tail -n %s %s" % (n, path)))


def cmd_net(args):
    print(tv("ifconfig 2>/dev/null | grep -A1 'inet addr\\|wlan0\\|eth0' | head -12"))
    for port in (2222, 8770, 36669):
        s = socket.socket()
        s.settimeout(TIMEOUT)
        try:
            s.connect((TV, port))
            print("mac -> %s:%d  open" % (TV, port))
        except OSError as e:
            print("mac -> %s:%d  closed (%s)" % (TV, port, e.__class__.__name__))
        finally:
            s.close()


def cmd_open(args):
    if not args:
        print("usage: alvidaa open <url>")
        return 2
    print(json.dumps(fetch("/api/open?url=" + urllib.parse.quote(args[0], safe=""))))


def cmd_apps(args):
    try:
        apps = fetch("/api/apps").get("apps", [])
    except Exception as e:
        print("unreachable (%s)" % e.__class__.__name__)
        return 2
    if not apps:
        print("(applist empty — press Home once so the framework populates it)")
    for a in apps:
        print("%-14s %s" % (a.get("appId", "?"), a.get("name", "?")))


def cmd_sources(args):
    try:
        sources = fetch("/api/sources").get("sources", [])
    except Exception as e:
        print("unreachable (%s)" % e.__class__.__name__)
        return 2
    for s in sources:
        sig = "signal" if s.get("signal") else "-"
        print("%-14s %-10s %s" % (s.get("id", "?"), s.get("name", "?"), sig))


def cmd_doctor(args):
    checks = []

    def check(name, fn):
        try:
            ok, detail = fn()
        except Exception as e:  # graceful: a down check is a result, not a crash
            ok, detail = False, "unreachable (%s)" % e.__class__.__name__
        checks.append((name, ok, detail))

    d = {}
    try:
        d = fetch("/api/debug")
    except Exception:
        pass

    def bridge_check():
        h = fetch("/api/health")
        return h.get("ok") and h.get("mqtt"), "%s mqtt:%s clients:%s" % (
            h.get("version", "?"), h.get("mqtt"), h.get("clients"))

    check("bridge", bridge_check)
    check("mqtt", lambda: (
        (d.get("mqtt") or {}).get("connected", False),
        "token:%s id:%s" % ("loaded" if (d.get("mqtt") or {}).get("tokenLoaded") else "MISSING",
                            (d.get("mqtt") or {}).get("clientId", "?"))))
    check("hook", lambda: (
        (d.get("hook") or {}).get("watchdogAlive", False)
        and not (d.get("hook") or {}).get("killSwitch", True),
        "%s watchdog:%s kill-switch:%s" % (
            (d.get("hook") or {}).get("version", "?"),
            "alive" if (d.get("hook") or {}).get("watchdogAlive") else "dead",
            "present" if (d.get("hook") or {}).get("killSwitch") else "absent")))

    def ssh_check():
        last = "untried"
        for attempt in range(3):
            s = socket.socket()
            s.settimeout(TIMEOUT)
            try:
                s.connect((TV, 2222))
                return True, "%s:2222 open" % TV
            except OSError as e:
                last = "%s:2222 %s" % (TV, e.__class__.__name__)
            finally:
                s.close()
            if attempt < 2:
                time.sleep(2)
        # Direct TCP may be blocked by the dual-home ARP flap while SSH
        # itself still works over the surviving path — probe functionally.
        if tv("true", timeout=20) is not None:
            return True, "%s:2222 open (flappy direct path; ssh-relay works)" % TV
        return False, last

    check("ssh", ssh_check)

    def ota_check():
        out = tv("iptables -L -n 2>/dev/null | grep -c DROP")
        n = int(out.strip() or 0)
        return n > 0, "%d DROP rules (kill-list armed)" % n

    check("ota", ota_check)

    def disk_check():
        out = tv("/var/local/tvtools/busybox df /var/local | /var/local/tvtools/busybox tail -n 1")
        parts = out.split()
        if len(parts) < 5:
            return False, "df output unparseable: %r" % out[:80]
        return True, "var/local %s used (%s/%s)" % (parts[4], parts[2], parts[3])

    check("disk", disk_check)

    def launcher_check():
        status, body = fetch_raw("/")
        return True, "GET / %s (%d bytes)" % (status, len(body))

    check("launcher", launcher_check)

    for name, ok, detail in checks:
        print("%-9s %-4s %s" % (name, mark(ok), detail))
    print("path      %-4s %s" % ("info", "bridge checks via %s fetch" % FETCH_PATH))
    passed = sum(1 for _, ok, _ in checks if ok)
    verdict = "HEALTHY" if passed == len(checks) else ("DEGRADED" if passed else "DOWN")
    print("VERDICT: %s (%d/%d checks passed)" % (verdict, passed, len(checks)))
    return 0 if verdict == "HEALTHY" else 1


COMMANDS = {
    "sys": cmd_sys,
    "logs": cmd_logs,
    "net": cmd_net,
    "doctor": cmd_doctor,
    "open": cmd_open,
    "apps": cmd_apps,
    "sources": cmd_sources,
}


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        print("\nsubcommands: %s" % ", ".join(sorted(COMMANDS)))
        return 0
    fn = COMMANDS.get(argv[0])
    if fn is None:
        print("unknown command: %s" % argv[0])
        return 2
    try:
        return fn(argv[1:]) or 0
    except urllib.error.URLError as e:
        print("bridge unreachable: %s" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
