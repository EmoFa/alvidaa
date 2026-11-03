#!/usr/bin/env bash
# Deploy the alvidaa overlay to the TV — validated, deterministic batch.
#
# Builds the final index.html LOCALLY (from the TV's own pristine backup) and
# pushes it — never edit files in place on the TV (the one-line minified HTML
# mangles under in-place edits; that killed the UI once already).
#
# The final file = pristine loader + head flash-kill style + self-healing
# bootstrap (boot screen + retrying script loader; un-hides the stock home
# if the bridge stays unreachable).
#
# Batch = 1 TV write + 1 cache clear + 1 reboot (write-minimization law).
#
# Usage: tools/deploy-overlay.sh [tv-ip]   (default 192.168.0.11)
set -euo pipefail

TV="${1:-192.168.0.11}"
KEY="$(cd "$(dirname "$0")" && pwd)/../server/keys/tv_root_ed25519"
BRIDGE="http://192.168.0.85:8770"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "==> 1/4 fetch pristine loader (TV's own .alvidaa-bak)"
ssh -p 2222 -i "$KEY" -o BatchMode=yes root@"$TV" \
  'cat /APPS/channelA/hisenseUI/index.html.alvidaa-bak' > "$WORK/orig.html"
echo "    original: $(wc -c < "$WORK/orig.html") bytes"

echo "==> 2/4 build final (head style + self-healing bootstrap)"
python3 - "$WORK/orig.html" "$HERE/../launcher/bootstrap.snippet.html" "$WORK/final.html" "$BRIDGE" <<'PYEOF'
import hashlib, sys
orig, snippet, out, bridge = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
s = open(orig).read()
assert "</head>" in s and "</html>" in s, "unexpected original structure"
s = s.replace("</head>",
  '<style id="alvidaa-head-style">#app{display:none!important}'
  'html,body{background:#0a0d12!important}</style></head>')
s += open(snippet).read().replace("__BRIDGE__", bridge)
open(out, "w").write(s)
print("    built:", len(s.encode()), "bytes, md5", hashlib.md5(s.encode()).hexdigest())
PYEOF

echo "==> 3/4 push + verify + cache clear + reboot"
cat "$WORK/final.html" | ssh -p 2222 -i "$KEY" -o BatchMode=yes root@"$TV" '
cat > /APPS/channelA/hisenseUI/index.html
export PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/openbox/bin:/var/local
MD1=$(/var/local/tvtools/busybox md5sum /APPS/channelA/hisenseUI/index.html | cut -d" " -f1)
echo "    on TV: $MD1"
/var/local/tvtools/busybox rm -rf /var/local/hisenseUI/cobalt_home/*
sync
reboot'
echo "==> 4/4 reboot issued — expect: starting screen → overlay (self-heals to stock home if bridge is down)"
