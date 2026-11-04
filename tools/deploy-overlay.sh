#!/usr/bin/env bash
# Deploy the alvidaa overlay to the TV — validated, deterministic batch.
#
# Builds the final index.html LOCALLY (from the TV's own pristine backup) and
# pushes it — never edit files in place on the TV (the one-line minified HTML
# mangles under in-place edits; that killed the UI once already).
#
# The final file = pristine loader + head flash-kill style + ONE plain
# <script src> to alvidaa-remote.js. Deliberately NOT the self-healing
# bootstrap: its retrying XHR deadlocks Cobalt after a CORS preflight
# (OPTIONS 200, POST never sent) and reproducibly froze the home engine
# (2026-11-03). Do not reintroduce it without a non-XHR fallback path.
#
# Failure mode by design: if the bridge is unreachable the script never
# loads, the head style keeps the stock UI hidden, and the home shows the
# dark flash-kill background with no launcher. There is no on-TV fallback.
#
# Batch = 1 TV write + 1 cache clear + 1 reboot (write-minimization law).
#
# Usage: tools/deploy-overlay.sh <tv-ip> <bridge-url>
#        or set TV_HOST and BRIDGE_URL in the environment.
set -euo pipefail

TV="${1:-${TV_HOST:-}}"
KEY="$(cd "$(dirname "$0")" && pwd)/../server/keys/tv_root_ed25519"
BRIDGE="${2:-${BRIDGE_URL:-}}"
[ -n "$TV" ] || { echo "ERROR: pass <tv-ip> or set TV_HOST"; exit 1; }
[ -n "$BRIDGE" ] || { echo "ERROR: pass <bridge-url> or set BRIDGE_URL"; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "==> 1/4 fetch pristine loader (TV's own .alvidaa-bak)"
ssh -p 2222 -i "$KEY" -o BatchMode=yes root@"$TV" \
  'cat /APPS/channelA/hisenseUI/index.html.alvidaa-bak' > "$WORK/orig.html"
echo "    original: $(wc -c < "$WORK/orig.html") bytes"

echo "==> 2/4 build final (head style + local script tag per findings 12 §5)"
python3 - "$WORK/orig.html" "$WORK/final.html" <<'PYEOF'
import hashlib, sys
orig, out = sys.argv[1], sys.argv[2]
s = open(orig).read()
assert "</head>" in s and "</html>" in s, "unexpected original structure"
s = s.replace("</head>",
  '<style id="alvidaa-head-style">#app{display:none!important}'
  'html,body{background:#0a0d12!important}</style></head>')
assert "</body>" in s, "unexpected original structure: missing </body>"
s = s.replace("</body>", '<script src="./alvidaa-remote.js"></script></body>')
open(out, "w").write(s)
print("    built:", len(s.encode()), "bytes, md5", hashlib.md5(s.encode()).hexdigest())
PYEOF

echo "==> 3/4 push overlay + index.html + verify + cache clear + reboot"
tar -cf - -C "$HERE/../launcher" alvidaa-remote.js -C "$WORK" final.html | ssh -p 2222 -i "$KEY" -o BatchMode=yes root@"$TV" '
/var/local/tvtools/busybox tar -xf - -C /tmp/
cat /tmp/final.html > /APPS/channelA/hisenseUI/index.html
cat /tmp/alvidaa-remote.js > /APPS/channelA/hisenseUI/alvidaa-remote.js
chmod 644 /APPS/channelA/hisenseUI/alvidaa-remote.js /APPS/channelA/hisenseUI/index.html
chown UhisApp:UGhisApp /APPS/channelA/hisenseUI/alvidaa-remote.js /APPS/channelA/hisenseUI/index.html
rm -f /tmp/final.html /tmp/alvidaa-remote.js
export PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/openbox/bin:/var/local
MD1=$(/var/local/tvtools/busybox md5sum /APPS/channelA/hisenseUI/index.html | /var/local/tvtools/busybox cut -d" " -f1)
MD2=$(/var/local/tvtools/busybox md5sum /APPS/channelA/hisenseUI/alvidaa-remote.js | /var/local/tvtools/busybox cut -d" " -f1)
echo "    on TV: index.html $MD1, alvidaa-remote.js $MD2"
/var/local/tvtools/busybox rm -rf /var/local/hisenseUI/cobalt_home/*
sync
# Findings 12 §4: `. /etc/profile` hangs in a non-interactive dropbear session,
# so the reboot never fires; /usr/local/bin/reboot also needs LD_LIBRARY_PATH.
# The static busybox reboot is the validated path.
/var/local/tvtools/busybox reboot -f'
echo "==> 4/4 reboot issued — expect: boot → local overlay; WebSocket connects on wlan0 up"
