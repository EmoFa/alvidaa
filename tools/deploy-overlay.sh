#!/usr/bin/env bash
# Deploy the alvidaa overlay to the TV — validated, deterministic batch.
#
# Builds the final index.html LOCALLY (from the TV's own pristine backup) and
# pushes it — never sed-edit files on the TV (the one-line minified HTML
# mangles under in-place edits; that killed the UI once already).
#
# Batch = 1 TV write + 1 cache clear + 1 reboot (write-minimization law).
#
# Usage: tools/deploy-overlay.sh [tv-ip]   (default 192.168.0.11)
set -euo pipefail

TV="${1:-192.168.0.11}"
KEY="$(cd "$(dirname "$0")" && pwd)/../server/keys/tv_root_ed25519"
BRIDGE="http://192.168.0.85:8770"
WORK="$(mktemp -d)"

echo "==> 1/4 fetch pristine loader (TV's own .alvidaa-bak)"
ssh -p 2222 -i "$KEY" -o BatchMode=yes root@"$TV" \
  'cat /APPS/channelA/hisenseUI/index.html.alvidaa-bak' > "$WORK/orig.html"
echo "    original: $(wc -c < "$WORK/orig.html") bytes"

echo "==> 2/4 build final (head flash-kill style + bootstrap script)"
python3 - "$WORK/orig.html" "$WORK/final.html" "$BRIDGE" <<'PYEOF'
import hashlib, sys
orig, out, bridge = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(orig).read()
assert "</head>" in s and "</html>" in s, "unexpected original structure"
s = s.replace("</head>",
  '<style id="alvidaa-head-style">#app{display:none!important}'
  'html,body{background:#0a0d12!important}</style></head>')
s += '<script src="' + bridge + '/alvidaa-remote.js"></script>\n'
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
echo "==> 4/4 reboot issued — expect: dark bg → overlay (no stock flash, no ads)"
rm -rf "$WORK"
