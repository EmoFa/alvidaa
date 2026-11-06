#!/bin/bash
# SSDP M-SEARCH + UPnP description fetch for a Hisense VIDAA TV.
#
# Run from the Pi (or any LAN host that can see the TV). Sends an SSDP
# M-SEARCH, collects LOCATION headers from responders, curls each one, and
# extracts the fields the onboarding ladder (AGENTS.md step 1) wants:
#
#   - transport_protocol=   (the field that gates the pair.py credential
#                           cascade; 3290+ selects the 2024 app-style path)
#   - modelName / friendlyName / modelNumber
#   - UDN (device UUID)
#   - serviceList (so we can see what UPnP/DIAL endpoints are live)
#
# Read-only: sends UDP M-SEARCHes and does HTTP GETs. Writes nothing on the
# TV. Serial numbers printed are device-identifying; redact them before
# pasting into a finding note.
#
# Usage:
#   tools/ssdp-descriptor.sh                      # auto-discover on LAN
#   tools/ssdp-descriptor.sh <tv-ip>              # hit that TV directly
#   tools/ssdp-descriptor.sh <tv-ip> <port>       # ... on a specific port
#
# Requires: python3 (stdlib only) + curl.
set -euo pipefail

TV="${1:-}"
PORT="${2:-}"

discover() {
  # Send three SSDP M-SEARCHes (one per common UPnP target), collect
  # LOCATION headers, print "<ip>\t<url>" lines for each unique responder.
  python3 - <<'PY'
import socket, sys, time, re

MX = 2
TARGETS = ["ssdp:all", "upnp:rootdevice", "urn:dial-multiscreen-org:service:dial:1"]
MCAST = ("239.255.255.250", 1900)

seen = set()
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    s.settimeout(0.5)
    for st in TARGETS:
        msg = (
            "M-SEARCH * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            "MAN: \"ssdp:discover\"\r\n"
            f"MX: {MX}\r\n"
            f"ST: {st}\r\n\r\n"
        ).encode()
        try:
            s.sendto(msg, MCAST)
        except OSError as e:
            print(f"# send failed ({st}): {e}", file=sys.stderr)
    deadline = time.monotonic() + MX + 1
    while time.monotonic() < deadline:
        try:
            data, addr = s.recvfrom(4096)
        except socket.timeout:
            continue
        text = data.decode("latin-1", "replace")
        m = re.search(r"(?mi)^LOCATION:\s*(\S+)", text)
        if not m: continue
        loc = m.group(1).strip()
        if loc in seen: continue
        seen.add(loc)
        print(f"{addr[0]}\t{loc}")
PY
}

extract() {
  # Pretty-print the canonical fields from a description.xml passed via
  # the XMLBODY env var. We can't pipe the XML on stdin AND use a 'PY'
  # heredoc for the script in one call (the heredoc takes stdin) — env var
  # avoids that collision cleanly.
  local xml_path="$1"
  XMLBODY="$(cat "$xml_path")" python3 -I - <<'PY'
import os, re

body = os.environ.get("XMLBODY", "")

def grab(pat, label):
    m = re.search(pat, body, re.IGNORECASE | re.DOTALL)
    if m:
        v = re.sub(r"\s+", " ", m.group(1)).strip()
        print(f"  {label}: {v[:200]}")

print("  --- description.xml fields ---")
# transport_protocol can appear as transport_protocol=NNNN inside a text
# field, or as a dedicated element — try both.
m = re.search(r"transport[_-]?protocol\s*[:=]\s*([0-9A-Za-z._-]+)", body, re.I)
if m:
    print(f"  transport_protocol: {m.group(1)}")
else:
    print(f"  transport_protocol: -  (not present in this XML)")

for pat, label in [
    (r"<friendlyName>([^<]+)</friendlyName>", "friendlyName"),
    (r"<modelName>([^<]+)</modelName>", "modelName"),
    (r"<modelNumber>([^<]+)</modelNumber>", "modelNumber"),
    (r"<modelDescription>([^<]+)</modelDescription>", "modelDescription"),
    (r"<manufacturer>([^<]+)</manufacturer>", "manufacturer"),
    (r"<UDN>([^<]+)</UDN>", "UDN"),
    (r"<deviceType>([^<]+)</deviceType>", "deviceType"),
    (r"<serialNumber>([^<]+)</serialNumber>", "serialNumber (REDACT before posting)"),
]:
    grab(pat, label)

services = re.findall(r"<serviceType>([^<]+)</serviceType>", body)
if services:
    print("  serviceList:")
    for s in services:
        print(f"    - {s}")
else:
    print("  serviceList: -")
PY
}

fetch_and_print() {
  local url="$1"
  local tmp
  tmp=$(mktemp)
  trap 'rm -f "$tmp"' RETURN
  echo
  echo "== $url =="
  if ! curl -fsS --max-time 4 -o "$tmp" "$url"; then
    echo "  (fetch failed — host down or path wrong)"
    return 1
  fi
  echo "  (bytes: $(wc -c < "$tmp"))"
  extract "$tmp"
}

if [[ -z "$TV" ]]; then
  echo "SSDP M-SEARCH (~2-3 s)..."
  # macOS still ships bash 3.2, which has no mapfile/readarray. while-read
  # works on bash 3.2+ and zsh (which macOS now defaults /bin/bash users to
  # when they run .sh under /bin/bash explicitly as we do with the shebang).
  LOCS=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && LOCS+=("$line")
  done < <(discover)
  if [[ ${#LOCS[@]} -eq 0 ]]; then
    echo "No SSDP responders. Make sure this host is on the same subnet as the TV,"
    echo "and that no local firewall is dropping multicast on 239.255.255.250:1900."
    echo "On a multi-interface host (Mac with Wi-Fi + Ethernet + VPN tunnels),"
    echo "the kernel may send the M-SEARCH out the wrong NIC — pass the TV IP"
    echo "directly instead:  $0 <tv-ip>"
    exit 1
  fi
  echo "Responders:"
  for pair in "${LOCS[@]}"; do
    echo "  $pair"
  done
  for pair in "${LOCS[@]}"; do
    url="${pair##*$'\t'}"
    fetch_and_print "$url" || true
  done
else
  if [[ -n "$PORT" ]]; then
    fetch_and_print "http://$TV:$PORT/description.xml"
  else
    # Try the common VIDAA UPnP ports in order; stop at the first that answers.
    hit=""
    for p in 49152 49153 49154 8080 1400 2869; do
      if curl -fsS --max-time 2 "http://$TV:$p/description.xml" >/dev/null 2>&1; then
        fetch_and_print "http://$TV:$p/description.xml" && hit=1 && break
      fi
    done
    if [[ -z "$hit" ]]; then
      echo "None of 49152/49153/49154/8080/1400/2869 answered."
      echo "Try: $0  (no args, uses SSDP discovery)"
      exit 1
    fi
  fi
fi
