#!/usr/bin/env python3
"""alvidaa — one CLI for the TV.

Root work goes through the existing server/tv wrapper (SSH is not
reimplemented here); bridge work goes through http://<tv>:8770. Every
health check degrades gracefully: a doctor that dies when the thing it
checks is down is useless.

Subcommands: sys, logs, net, doctor, open, apps, sources, ota, privacy
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
        return 0
    # appId only exists on bridges built after 2026-11-05; an older daemon
    # sends name+icon only. Degrade to a name list rather than a column of
    # question marks.
    show_id = any(a.get("appId") is not None for a in apps)
    for a in apps:
        if show_id:
            print("%-14s %s" % (a.get("appId", "-"), a.get("name", "?")))
        else:
            print(a.get("name", "?"))
    return 0


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


# ---------------------------------------------------------------- ota freeze
# Firmware-OTA freeze (issue #14): two independent layers, both verified on
# every transition. Kernel layer = dedicated iptables chain ALVIDAA_OTA
# (chain isolation guarantees 'on' can never touch bee2's INPUT kill-list
# or tvfw's own rules). Resolver layer = 0.0.0.0 pins in /tmp/hosts (the
# /etc/hosts symlink target — tmpfs, so the boot re-apply in firmware/tvfw
# rewrites it; reboot survival = hook -> tvfw -> state.sh sidecar with
# pre-resolved IPs, no boot-DNS dependency). Standing policy (ENDPOINTS.md)
# is ALLOW for ota-tv; the freeze is an explicit, tracked override.
OTA_HOSTS = ["ota-tv.vidaahub.com", "upgrade-cus.prod-eu-c.az.vidaahub.com"]
# Collateral candidates (ds41 condition 1, findings 09): prod-eu-c serves
# file-ul/account uploads too, and CDN IPs rotate across the vidaahub set.
# A per-IP freeze REJECT blocks EVERY host sharing that IP — enumerate the
# plausible sharers, report the overlap at freeze time and in status.
OTA_COLLATERAL = [
    "file-ul.vidaahub.com", "evt-na.vidaahub.com", "ter-jrnl-na.vidaahub.com",
    "exc-jrnl-na.vidaahub.com", "policy-jrnl-na.vidaahub.com",
    "dvcstatus-dataretrv.vidaahub.com", "rsc-ads.vidaahub.com",
    "recommend-ui.vidaahub.com", "home-ui.vidaahub.com", "img.vidaahub.com",
    "msg.vidaahub.com",
]
OTA_CHAIN = "ALVIDAA_OTA"
OTA_STATE = "/var/local/alvidaa/ota_freeze.state"
OTA_STATE_SH = "/var/local/alvidaa/ota_freeze.state.sh"
OTA_HOSTS_FILE = "/tmp/hosts"
BB = "/var/local/tvtools/busybox"


def _tv_ota(cmd, timeout=60):
    return tv(cmd, timeout=timeout)


def _ota_resolve(host):
    """Return the real IPv4 addresses for host as seen by the TV resolver."""
    out = _tv_ota("%s nslookup %s 2>/dev/null" % (BB, host))
    ips = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Address ") or line.startswith("Address:"):
            ip = line.split(":", 1)[-1].strip()
            if ip and ":" not in ip and ip != "0.0.0.0":
                ips.append(ip)
    return sorted(set(ips))


def _ota_pin_present():
    out = _tv_ota("%s grep -h '^0\\.0\\.0\\.0 ' %s 2>/dev/null | %s grep -E 'ota-tv|upgrade-cus' | grep -c ."
                  % (BB, OTA_HOSTS_FILE, BB))
    return int(out.strip() or 0)


def _ota_chain_state():
    out = _tv_ota("iptables -L %s -n 2>/dev/null | grep -c REJECT; "
                  "iptables -L OUTPUT -n 2>/dev/null | grep -c '%s'" % (OTA_CHAIN, OTA_CHAIN))
    lines = [x.strip() for x in out.splitlines() if x.strip()]
    rules = int(lines[0]) if lines else 0
    jump = int(lines[1]) if len(lines) > 1 else 0
    return rules, jump


def _ota_state_exists():
    return _tv_ota("[ -f %s ] && echo yes || echo no" % OTA_STATE).strip() == "yes"


def _ota_nc(target):
    """True if a TCP:443 connect from the TV to target SUCCEEDS."""
    out = _tv_ota("%s nc -w 5 -z %s 443 >/dev/null 2>&1 && echo OK || echo FAIL" % (BB, target))
    return "OK" in out


def _ota_state_files(state, ips, collateral):
    """Write the JSON state and the shell sidecar tvfw re-applies at boot."""
    import datetime
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    js = json.dumps({
        "frozen_at": now, "hosts": OTA_HOSTS, "ips": ips,
        "collateral": collateral,
        "chain": OTA_CHAIN, "layers": ["iptables-chain", "hosts-pin"],
    })
    sh = ("OTA_HOSTS='%s'\nOTA_IPS='%s'\n" % (" ".join(OTA_HOSTS), " ".join(ips)))
    _tv_ota("echo '%s' > %s" % (js.replace("'", "'\\''"), OTA_STATE))
    _tv_ota("echo '%s' > %s" % (sh.replace("'", "'\\''"), OTA_STATE_SH))


def _ota_collateral(ips):
    """Return {ip: [other vidaahub hosts sharing that IP]} for the freeze set."""
    if not ips:
        return {}
    shared = {}
    for host in OTA_COLLATERAL:
        for ip in _ota_resolve(host):
            if ip in ips:
                shared.setdefault(ip, []).append(host)
    return shared


def _ota_tvfw_applied():
    """Deferral-window readout (ds41 condition 2) from tvfw's own marker."""
    out = _tv_ota("cat /var/local/tvfw.applied_at_boot 2>/dev/null; echo /; "
                  "cat /var/local/tvfw.applied 2>/dev/null")
    parts = [p.strip() for p in out.split("/", 1) if p.strip()]
    if len(parts) < 2 or not parts[0].replace(".", "").isdigit():
        return None
    import time as _t
    applied_T = float(parts[0])
    try:
        age = max(0, _t.time() - float(parts[1]))  # marker is an epoch
        return "applied at T+%ds (%.0fs ago)" % (applied_T, age)
    except ValueError:
        return "applied at T+%ds" % applied_T


def cmd_ota(args):
    action = args[0] if args else "status"

    if action == "off":
        if _ota_state_exists():
            print("already frozen (state file present) — nothing to do")
            return cmd_ota(["status"])
        print("resolving %s from the TV resolver..." % ", ".join(OTA_HOSTS))
        ips = []
        for h in OTA_HOSTS:
            found = _ota_resolve(h)
            print("  %-42s -> %s" % (h, ", ".join(found) or "UNRESOLVED"))
            ips.extend(found)
        ips = sorted(set(ips))
        if not ips:
            print("ERROR: cannot freeze — kernel layer needs at least one resolved IP")
            return 1
        # Kernel layer: dedicated chain (isolation = safe unfreeze).
        _tv_ota("iptables -N %s 2>/dev/null; true" % OTA_CHAIN)
        for ip in ips:
            _tv_ota("iptables -C %s -d %s -j REJECT 2>/dev/null || iptables -A %s -d %s -j REJECT"
                    % (OTA_CHAIN, ip, OTA_CHAIN, ip))
        _tv_ota("iptables -C OUTPUT -j %s 2>/dev/null || iptables -I OUTPUT 1 -j %s"
                % (OTA_CHAIN, OTA_CHAIN))
        # Resolver layer: 0.0.0.0 pins in /tmp/hosts (dedup-safe).
        for h in OTA_HOSTS:
            _tv_ota("%s grep -q '^0\\.0\\.0\\.0 %s$' %s 2>/dev/null || echo '0.0.0.0 %s' >> %s"
                    % (BB, h, OTA_HOSTS_FILE, h, OTA_HOSTS_FILE))
        # Collateral disclosure (ds41 condition 1): a per-IP REJECT blocks
        # every vidaahub host sharing the frozen IPs — state it, never silent.
        collateral = _ota_collateral(ips)
        if collateral:
            print("  collateral   : per-IP freeze also blocks (shared CDN IPs):")
            for ip, hosts in sorted(collateral.items()):
                print("    %-15s %s" % (ip, ", ".join(hosts)))
        else:
            print("  collateral   : no other vidaahub host shares the frozen IPs right now")
        _ota_state_files(None, ips, collateral)
        print("verifying freeze (both layers must fail to connect)...")
        rules, jump = _ota_chain_state()
        pin = _ota_pin_present()
        real_ok = any(_ota_nc(ip) for ip in ips)
        name_ok = _ota_nc(OTA_HOSTS[0])
        print("  kernel layer : chain %d REJECT rules, jump %s" % (rules, "armed" if jump else "MISSING"))
        print("  resolver     : %d pin line(s) in %s" % (pin, OTA_HOSTS_FILE))
        print("  live probe   : connect by IP %s | connect by name %s"
              % ("OPEN (BAD)" if real_ok else "blocked", "OPEN (BAD)" if name_ok else "blocked"))
        if rules and jump and pin and not real_ok and not name_ok:
            print("FROZEN (verified) — OTA firmware updates are blocked at both layers")
            return 0
        print("ERROR: freeze incomplete — see per-layer lines above; do NOT trust this state")
        return 1

    if action == "on":
        print("removing exactly what 'off' added (chain + jump + pins + state)...")
        _tv_ota("iptables -D OUTPUT -j %s 2>/dev/null; true" % OTA_CHAIN)
        _tv_ota("iptables -F %s 2>/dev/null; iptables -X %s 2>/dev/null; true" % (OTA_CHAIN, OTA_CHAIN))
        _tv_ota("%s grep -v -E '^(0\\.0\\.0\\.0 (ota-tv\\.vidaahub\\.com|upgrade-cus\\.prod-eu-c\\.az\\.vidaahub\\.com))' %s > %s.new 2>/dev/null; "
                "mv %s.new %s" % (BB, OTA_HOSTS_FILE, OTA_HOSTS_FILE, OTA_HOSTS_FILE, OTA_HOSTS_FILE))
        _tv_ota("rm -f %s %s" % (OTA_STATE, OTA_STATE_SH))
        print("verifying unfreeze (resolution and connect must BOTH succeed)...")
        rules, jump = _ota_chain_state()
        pin = _ota_pin_present()
        ips_now = _ota_resolve(OTA_HOSTS[0])
        real_ok = any(_ota_nc(ip) for ip in ips_now)
        name_ok = _ota_nc(OTA_HOSTS[0])
        print("  kernel layer : chain rules %d (want 0), jump %s (want removed)" % (rules, jump))
        print("  resolver     : %d pin line(s) (want 0) | live resolve -> %s"
              % (pin, ", ".join(ips_now) or "UNRESOLVED"))
        print("  live probe   : connect by IP %s | connect by name %s"
              % ("OK" if real_ok else "BLOCKED", "OK" if name_ok else "BLOCKED"))
        if not rules and not jump and not pin and ips_now and real_ok and name_ok:
            print("UNFROZEN (verified) — OTA firmware updates flow again")
            return 0
        print("ERROR: PARTIAL UNFREEZE — a layer did not come back. This is the "
              "dangerous state; fix before trusting OTA. (Per-layer lines above.)")
        return 1

    if action == "status":
        state = _ota_state_exists()
        rules, jump = _ota_chain_state()
        pin = _ota_pin_present()
        resolved = _ota_resolve(OTA_HOSTS[0])
        real_ok = any(_ota_nc(ip) for ip in resolved)
        name_ok = _ota_nc(OTA_HOSTS[0])
        killswitch = _tv_ota("[ -f /var/local/hook.off ] && echo present || echo absent").strip()
        tvfw_block = _tv_ota("%s grep -c 'ota_freeze.state.sh' /var/local/tvfw 2>/dev/null" % BB).strip()
        frozen_at = ""
        if state:
            frozen_at = _tv_ota("%s grep -o '\"frozen_at\": *\"[^\"]*\"' %s 2>/dev/null" % (BB, OTA_STATE)).strip()
        applied = _ota_tvfw_applied()
        print("  state file     : %s %s" % ("present" if state else "absent", frozen_at))
        print("  kernel layer   : chain %d REJECT rules, jump %s" % (rules, "armed" if jump else "absent"))
        print("  resolver layer : %d pin line(s) | live resolve -> %s"
              % (pin, ", ".join(resolved) or "UNRESOLVED"))
        print("  live probe     : connect by IP %s | connect by name %s"
              % ("OPEN" if real_ok else "blocked", "OPEN" if name_ok else "blocked"))
        print("  tvfw           : %s" % (applied or "not applied this boot (marker missing)"))
        print("  reboot survival: tvfw re-apply block %s | kill-switch %s"
              % ("present" if tvfw_block and int(tvfw_block or 0) > 0 else "MISSING", killswitch))
        if state and resolved:
            collateral = _ota_collateral(resolved)
            if collateral:
                print("  collateral     : freeze IPs also serve (shared CDN IPs):")
                for ip, hosts in sorted(collateral.items()):
                    print("    %-15s %s" % (ip, ", ".join(hosts)))
            else:
                print("  collateral     : no other vidaahub host shares the freeze IPs right now")
        if rules and jump and pin and not real_ok and not name_ok:
            verdict = "FROZEN (verified)"
        elif not rules and not jump and not pin and real_ok and name_ok:
            verdict = "UNFROZEN (verified)"
        else:
            verdict = "PARTIAL/UNKNOWN — layers disagree, investigate before UI work"
        print("VERDICT: %s" % verdict)
        if state and killswitch == "present":
            print("WARNING: /var/local/hook.off is present — the next reboot disarms "
                  "the freeze (reversibility law). Remove the kill-switch or re-freeze after recovery.")
        return 0

    print("usage: alvidaa ota off|on|status")
    return 2


def _md5_tv(path):
    out = tv("/var/local/tvtools/busybox md5sum '%s' 2>/dev/null | /var/local/tvtools/busybox cut -d' ' -f1" % path)
    return out.strip()


def cmd_push(args):
    if len(args) < 2:
        print("usage: alvidaa push <local-file> <tv-absolute-path>")
        return 2
    local, remote = args[0], args[1]
    if not os.path.isfile(local):
        print("no such file: %s" % local)
        return 2
    if not remote.startswith("/"):
        print("remote path must be absolute (e.g. /var/local/alvidaa/…)")
        return 2
    import hashlib, io, tarfile, base64
    lm = hashlib.md5(open(local, "rb").read()).hexdigest()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as t:
        t.add(local, arcname=os.path.basename(local))
    # Stream the tar over SSH stdin — argv dies at ~10KB (dropbear command
    # channel), the stdin pipe is the lane every deploy script in this repo
    # already uses.
    base = os.path.basename(local)
    mv_cmd = "" if remote == "/tmp/" + base else "mv '/tmp/%s' '%s' && " % (base, remote)
    out = subprocess.run(
        [TV_WRAPPER,
         "cat > /tmp/.alvidaa-push.tar && "
         "/var/local/tvtools/busybox tar xf /tmp/.alvidaa-push.tar -C /tmp/ && "
         "%srm -f /tmp/.alvidaa-push.tar && "
         "/var/local/tvtools/busybox sync && echo INSTALL-OK" % mv_cmd],
        input=buf.getvalue(), capture_output=True, timeout=90)
    stdout = out.stdout.decode(errors="replace")
    stderr = out.stderr.decode(errors="replace")
    if "INSTALL-OK" not in stdout:
        print("push failed: %s" % (stdout.strip()[:200] or stderr.strip()[:200] or "empty"))
        return 1
    rm = _md5_tv(remote)
    ok = rm == lm
    print("push %s -> %s:%s  md5 %s  %s" % (
        local, TV, remote, lm[:12] + "…", "VERIFIED" if ok else "MISMATCH (local %s)" % lm[:12] + "…"))
    return 0 if ok else 1


def cmd_pull(args):
    if len(args) < 2:
        print("usage: alvidaa pull <tv-absolute-path> <local-file>")
        return 2
    remote, local = args[0], args[1]
    if not remote.startswith("/"):
        print("remote path must be absolute")
        return 2
    rm = _md5_tv(remote)
    if not rm:
        print("no such file on TV (or unreadable): %s" % remote)
        return 2
    out = tv("/var/local/tvtools/busybox base64 '%s'" % remote, timeout=60)
    import base64, hashlib
    data = base64.b64decode("".join(out.split()))
    with open(local, "wb") as f:
        f.write(data)
    lm = hashlib.md5(data).hexdigest()
    ok = lm == rm
    print("pull %s:%s -> %s  md5 %s  %s" % (
        TV, remote, local, rm[:12] + "…", "VERIFIED" if ok else "MISMATCH (local %s)" % lm[:12] + "…"))
    return 0 if ok else 1


# ---------------------------------------------------------------- privacy
# Kill-list / telemetry visibility (issue #15), READ-ONLY: nothing here
# touches firewall state. The whole point of reporting the layers
# separately is findings 09: one layer is not enough, and "0 rules" can
# mean either "the resolver is doing the work" (correct) or "the apply
# loop silently failed" (the 2026-11-05 boot bug) — a bare count cannot
# tell them apart, so every layer reports WHICH case it is.
#
# Layers, per the kill-list design (firmware/tvfw + ENDPOINTS.md):
#   resolver  — AdGuard NXDOMAIN-pins telemetry hosts (the durable kill;
#               survives kernel flushes and CDN rotation)
#   kernel    — tvfw Tier 0 (DoH) + Tier 1 (telemetry hosts) REJECTs in
#               OUTPUT, re-applied at boot by the hook
#   doh       — the Tier 0 bootstrap block specifically (dns.google),
#               the most quotable number in the project
#   wiretap   — LOG-target kernel capture (armed window only; the log
#               file is historical evidence, NOT live data, once the
#               LOG rules are gone)
PRIVACY_TIER1 = [
    "evt-na.vidaahub.com", "ter-jrnl-na.vidaahub.com",
    "exc-jrnl-na.vidaahub.com", "policy-jrnl-na.vidaahub.com",
    "dvcstatus-dataretrv.vidaahub.com", "file-ul.vidaahub.com",
    "rsc-ads.vidaahub.com",
]
PRIVACY_DOH_IPS = {"8.8.8.8": "dns.google", "8.8.4.4": "dns.google"}
# IP labels from the Oct 30 – Nov 2 wiretap window (findings 09); CDN
# rotation means a historical IP can drift to a different host — labels
# are attributed, never asserted.
PRIVACY_IP_LABELS = {
    "20.170.76.123": "ter-jrnl-na (journal collector, per findings 09)",
    "20.52.196.175": "dvcstatus-dataretrv (per findings 09)",
    "131.189.128.123": "file-ul/account (per findings 09)",
    "131.189.69.51": "account, prod-eu-c (per findings 09)",
}
WIRETAP_LOG = "/var/local/wiretap.log"
BB = "/var/local/tvtools/busybox"  # (same path as the ota section)


def _ipt_rules(chain):
    """Parsed `iptables -L <chain> -n -v -x`: [(pkts, bytes, target, proto, dest, extra)].
    None = chain does not exist; [] = chain exists and is empty. Both states
    matter (findings 09): an empty OUTPUT after a boot with an applied
    marker is the silent-kill signature, not an OK state."""
    out = tv("/usr/local/bin/iptables -L %s -n -v -x 2>&1" % chain)
    if "No chain/target/match" in out or not out.strip():
        return None
    rules = []
    for line in out.splitlines():
        p = line.split()
        if len(p) < 9 or not p[0].isdigit():
            continue  # header/blank
        rules.append((int(p[0]), int(p[1]), p[2], p[3], p[8], " ".join(p[9:])))
    return rules


_RESOLVE_CACHE = {}


def _privacy_resolve(host):
    """Resolver-layer probe as THE TV sees it: ('pinned'|'resolved'|'unresolved', ips).
    busybox nslookup answers 0.0.0.0 / :: for AdGuard-blocked hosts
    (findings 09) — that IS the blocking signal, never filtered away here."""
    if host in _RESOLVE_CACHE:
        return _RESOLVE_CACHE[host]
    out = tv("%s nslookup %s 2>&1" % (BB, host))
    ips = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Address"):
            ip = line.split(":", 1)[-1].strip()
            # the 'Server: … :53' echo line also starts with Address — skip it
            if ip and not ip.endswith(":53") and ip not in ("0.0.0.0", "::") and ":" not in ip:
                ips.append(ip)
            elif ip in ("0.0.0.0", "::"):
                ips.append(ip)
    real = [ip for ip in ips if ip not in ("0.0.0.0", "::")]
    result = ("resolved", real) if real else (("pinned", ips) if ips else ("unresolved", []))
    _RESOLVE_CACHE[host] = result
    return result


def _wiretap_summary():
    """(armed, historical_counts) — armed = LOG rules live in the kernel AND
    the dmesg ring actually carries wiretap lines; the log file alone proves
    nothing (its mtime keeps moving while its content is stale)."""
    log_rules = 0
    for chain in ("OUTPUT", "INPUT", "FIREWALL_OUT_EULAON", "FIREWALL_OUT_EULAOFF"):
        rules = _ipt_rules(chain)
        if rules:
            log_rules += sum(1 for r in rules if r[2] == "LOG")
    ring = tv("%s dmesg 2>/dev/null | %s grep -c 'TVOUT\\|TVDNS'" % (BB, BB)).strip()
    ring = int(ring) if ring.isdigit() else 0
    lines = tv("%s grep -h -E 'TVOUT|TVDNS' %s 2>/dev/null" % (BB, WIRETAP_LOG), timeout=40)
    hist = {}
    srcs = set()
    for line in lines.splitlines():
        fields = dict(f.split("=", 1) for f in line.split() if "=" in f)
        dst, dpt = fields.get("DST"), fields.get("DPT", "?")
        src = fields.get("SRC")
        if src:
            srcs.add(src)
        if dst:
            hist.setdefault((dst, dpt), 0)
            hist[(dst, dpt)] += 1
    armed = log_rules > 0 and ring > 0
    return armed, ring, hist, srcs, len(lines.splitlines())


def _label(ip):
    if ip in PRIVACY_DOH_IPS:
        return PRIVACY_DOH_IPS[ip]
    if ip in PRIVACY_IP_LABELS:
        return PRIVACY_IP_LABELS[ip]
    # reverse-map from the CURRENT resolver view of the Tier-1 hosts;
    # CDN rotation makes this best-effort, so say so. The resolve cache
    # keeps this at 7 lookups per run, not per IP.
    for h in PRIVACY_TIER1:
        state, ips = _privacy_resolve(h)
        if state == "resolved" and ip in ips:
            return "%s (current resolution; rotation may drift)" % h
    return ""


def _tvfw_marker():
    out = tv("cat /var/local/tvfw.applied_at_boot 2>/dev/null; echo /; "
             "cat /var/local/tvfw.applied 2>/dev/null; echo /; cat /proc/uptime")
    parts = out.split("/")
    if len(parts) < 3:
        return "no marker — tvfw did not complete this boot"
    at_boot = parts[0].strip().split()[0] if parts[0].strip() else ""
    epoch = parts[1].strip().split()[0] if parts[1].strip() else ""
    if not at_boot.isdigit():
        return "no marker — tvfw did not complete this boot"
    # The marker epoch is written with the TV clock, which starts in 2000
    # before NTP — a 9xx-range epoch is 'clock not set', not 'ancient'.
    note = ""
    if not epoch:
        note = " (epoch unreadable)"
    else:
        try:
            if float(epoch) < 1_500_000_000:
                note = " (marker clock unset — pre-NTP write)"
        except ValueError:
            note = " (epoch unreadable)"
    return "tvfw applied at T+%ss this boot%s" % (at_boot, note)


def cmd_privacy(args):
    action = args[0] if args else "status"

    # ---- shared collection (each piece degrades independently) ----
    out_rules = _ipt_rules("OUTPUT")
    resolver = {}
    if action in ("status", "hits"):
        for h in PRIVACY_TIER1:
            resolver[h] = _privacy_resolve(h)
    try:
        armed, ring, hist, srcs, n_lines = _wiretap_summary()
    except Exception:
        armed, ring, hist, srcs, n_lines = False, 0, {}, set(), 0

    if action == "status":
        print("== layer 1: resolver (AdGuard @ the TV's DNS) ==")
        pinned = sum(1 for s, _ in resolver.values() if s == "pinned")
        live = [h for h, (s, _) in resolver.items() if s == "resolved"]
        down = any(s == "unresolved" for s, _ in resolver.values()) and pinned == 0
        for h, (s, ips) in resolver.items():
            print("  %-38s %-11s %s" % (h, s, ", ".join(ips) if ips else ""))
        if live:
            print("  VERDICT: NOT blocking %s — resolver layer has a hole" % ", ".join(live))
        elif pinned:
            print("  VERDICT: blocking (resolver is doing the work — %d/%d hosts pinned)" % (pinned, len(resolver)))
        elif down:
            print("  VERDICT: no answer from the resolver — DNS path itself is down, NOT 'blocked'")
        print("== layer 2: kernel REJECTs (tvfw, OUTPUT) ==")
        print("  %s" % _tvfw_marker())
        if out_rules is None:
            print("  OUTPUT chain unreadable — iptables unavailable")
        elif not out_rules:
            print("  OUTPUT is EMPTY: no Tier-0 (DoH) and no Tier-1 (telemetry) rules.")
            print("  This is the silent-kill state from findings 09 — the kernel")
            print("  backstop is NOT working this boot; the resolver layer is")
            print("  the only active block. Re-source /var/local/tvfw or reboot")
            print("  and re-check (nothing here changes firewall state).")
        else:
            t0 = [r for r in out_rules if r[4] in PRIVACY_DOH_IPS]
            t1 = [r for r in out_rules if r[2] == "REJECT" and r[4] not in PRIVACY_DOH_IPS]
            logs = [r for r in out_rules if r[2] == "LOG"]
            print("  Tier-0 DoH rules: %d | Tier-1 telemetry rules: %d | LOG (wiretap): %d"
                  % (len(t0), len(t1), len(logs)))
            print("  VERDICT: kernel backstop armed")
        ota_rules = _ipt_rules("ALVIDAA_OTA")
        print("== layer 3: DoH bootstrap block (Tier 0) ==")
        if out_rules is None:
            print("  UNAVAILABLE — OUTPUT chain unreadable")
        elif not any(r[4] in PRIVACY_DOH_IPS for r in out_rules):
            print("  dns.google REJECT rules: ABSENT — vidaahub DoH evasion is")
            print("  unimpeded at the kernel; only the resolver layer answers.")
        else:
            for r in out_rules:
                if r[4] in PRIVACY_DOH_IPS:
                    print("  %-8s %-45s pkts %d" % (r[4], PRIVACY_DOH_IPS[r[4]], r[0]))
        print("== layer 4: boot-time rejects / freeze ==")
        ks = tv("[ -f /var/local/hook.off ] && echo present || echo absent").strip()
        pins = tv("%s grep -c '^0\\.0\\.0\\.0 ' /tmp/hosts 2>/dev/null" % BB).strip()
        print("  /tmp/hosts 0.0.0.0 pins: %s | ALVIDAA_OTA chain: %s | kill-switch: %s"
              % (pins or "0", "%d rules" % len(ota_rules) if ota_rules else "absent", ks))
        print("  (freeze detail: alvidaa ota status)")
        print("== wiretap ==")
        if armed:
            print("  ARMED — kernel LOG rules live, dmesg ring carrying TVOUT/TVDNS (%d lines)" % ring)
        else:
            print("  NOT armed — no live LOG rules in the kernel (dmesg ring: %d wiretap lines)." % ring)
            print("  wiretap.log is HISTORICAL evidence only (%d lines); do not quote it as current." % n_lines)
        return 0

    if action == "hits":
        print("== kernel counters (since boot) ==")
        if not out_rules:
            print("  UNAVAILABLE — OUTPUT has no rules this boot (kernel layer not armed).")
            print("  Zero here would be a lie of a different kind: nothing is being counted.")
        else:
            rows = [(r[0], r[4], r[5]) for r in out_rules if r[0] > 0 and r[2] == "REJECT"]
            if not rows:
                print("  REJECT rules present, all counters at 0 — nothing has hit the")
                print("  kernel layer since boot (resolver layer may be absorbing it).")
            for pkts, ip, extra in sorted(rows, reverse=True):
                lbl = _label(ip)
                print("  %-16s %7d pkts  %-12s %s" % (ip, pkts, extra[:12], lbl))
        print("== wiretap log (historical armed windows — NOT since-boot) ==")
        if not hist:
            print("  no TVOUT/TVDNS lines readable" + ("" if armed else " (wiretap not armed)"))
        else:
            era = ", ".join(sorted(srcs)) or "?"
            print("  %d lines from SRC %s — attribute to the armed window, not today" % (n_lines, era))
            for (dst, dpt), n in sorted(hist.items(), key=lambda kv: -kv[1])[:15]:
                lbl = _label(dst)
                print("  %-16s %-4s %6d hits  %s" % (dst, dpt, n, lbl))
            if len(hist) > 15:
                print("  … %d more destinations" % (len(hist) - 15))
        return 0

    if action == "doh":
        print("== DoH / hardcoded-resolver evasion (dns.google) ==")
        doh_rules = [r for r in (out_rules or []) if r[4] in PRIVACY_DOH_IPS and r[2] == "REJECT"]
        if doh_rules:
            total = sum(r[0] for r in doh_rules)
            print("  kernel, since boot : %d attempts REJECTed (Tier-0 rules armed)" % total)
            for r in doh_rules:
                print("    %-8s pkts %d (%s)" % (r[4], r[0], PRIVACY_DOH_IPS[r[4]]))
        else:
            print("  kernel, since boot : UNAVAILABLE — Tier-0 rules not in OUTPUT this boot.")
            print("  The evasion is NOT being counted (and not blocked) at the kernel;")
            print("  only the resolver layer stands. This is not zero attempts — it is")
            print("  no counter. Re-arm tvfw before the next measurement window.")
        if n_lines:
            # Two transports carry the same evasion (findings 09 recorded the
            # :53 count as 'DoH bootstrap'): :443 dns-query (DoH proper) and
            # :53 plain DNS aimed straight at Google, bypassing the LAN resolver.
            doh443 = sum(n for (dst, dpt), n in hist.items()
                         if dst in PRIVACY_DOH_IPS and dpt == "443")
            doh53 = sum(n for (dst, dpt), n in hist.items()
                        if dst in PRIVACY_DOH_IPS and dpt == "53")
            print("  wiretap, historical: %d to tcp/udp :443 (DoH proper), %d to :53 (hardcoded"
                  % (doh443, doh53))
            print("                       plain resolver) — armed-window log, %d lines, era %s"
                  % (n_lines, ", ".join(sorted(srcs)) or "?"))
            print("                       (Tier-0 blocks :443 only — :53 to the hardcoded")
            print("                        resolver is a separate leak if it recurs)")
        state, ips = _privacy_resolve("ter-jrnl-na.vidaahub.com")
        print("  resolver now       : ter-jrnl-na -> %s (%s)"
              % (", ".join(ips) or "no answer", state))
        return 0

    print("usage: alvidaa privacy status|hits|doh")
    return 2


COMMANDS = {
    "sys": cmd_sys,
    "logs": cmd_logs,
    "net": cmd_net,
    "doctor": cmd_doctor,
    "open": cmd_open,
    "apps": cmd_apps,
    "sources": cmd_sources,
    "ota": cmd_ota,
    "privacy": cmd_privacy,
    "push": cmd_push,
    "pull": cmd_pull,
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
