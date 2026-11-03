#!/usr/bin/env bash
# Deploy the alvidaa overlay to the TV — the validated batched sequence.
# One TV write + one cache clear + one reboot, per the write-minimization law.
#
# What lands on the TV:
#   1. head style: #app hidden + alvidaa background from parse-time
#      (kills the stock-home/ads flash before sdk.js renders)
#   2. the bootstrap script tag (loads launcher/alvidaa-remote.js from the bridge)
#   3. Cobalt cache clear (stale page otherwise serves forever)
#   4. reboot
#
# Usage: tools/deploy-overlay.sh [tv-ip]   (default 192.168.0.11)
set -euo pipefail

TV="${1:-192.168.0.11}"
KEY="$(cd "$(dirname "$0")" && pwd)/../server/keys/tv_root_ed25519"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> head style + bootstrap + cache clear + reboot on $TV"
ssh -p 2222 -i "$KEY" -o BatchMode=yes root@"$TV" '
export PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/openbox/bin:/var/local
F=/APPS/channelA/hisenseUI/index.html
# 1. idempotent head style (removes any previous insert first)
sed -i "/alvidaa-head-style/d" "$F"
sed -i "s|</head>|<style id=\"alvidaa-head-style\">#app{display:none!important}html,body{background:#0a0d12!important}</style></head>|" "$F"
# 2. idempotent bootstrap script tag
sed -i "/alvidaa-remote.js/d" "$F"
echo "<script src=\"http://192.168.0.85:8770/alvidaa-remote.js\"></script>" >> "$F"
# 3. cache clear + 4. reboot
/var/local/tvtools/busybox rm -rf /var/local/hisenseUI/cobalt_home/*
sync
/var/local/tvtools/busybox md5sum "$F"
sleep 1
reboot
' 2>/dev/null || true

echo "==> reboot issued — TV returns in ~90s with: dark bg → overlay (no stock flash, no ads)"
