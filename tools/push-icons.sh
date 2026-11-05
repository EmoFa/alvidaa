#!/bin/bash
# Push launcher app icons into the on-TV bridge's icon cache.
#
# The bridge's /icon/<appId> handler serves <iconcache>/<alnum-id>.img (+ .type)
# from cache before trying the (egress-blocked) httpIcon URL. This tool
# pre-populates that cache with vendor UI assets (launcher/icons/), so tiles
# render real icons with no bridge rebuild and no reboot. Idempotent.
#
# Usage: TV_HOST=<tv-ip> tools/push-icons.sh
set -euo pipefail

TV="${TV_HOST:-192.168.0.11}"
HERE="$(cd "$(dirname "$0")" && pwd)"
KEY="$HERE/../server/keys/tv_root_ed25519"
ICONS="$HERE/../launcher/icons"
REMOTE_DIR="/var/local/alvidaa/launcher/iconcache"

# appId -> asset + content-type. The safe id must match the bridge's
# alnum-only transform (http.go iconBytes): non-alnum chars are stripped.
# Entries: <safeId>|<file>|<content-type>
MAPPING=(
  "284|tile-dtv.webp|image/webp"      # Live TV  (vendor launcher tile_dtv)
  "3|youtube.png|image/png"           # YouTube  (vendor app-service img)
  "16|browser.png|image/png"          # Browser  (vendor app-service TVBrowser)
  "2256|spotify.jpg|image/jpeg"       # Spotify  (official brand icon, Play Store listing)
  "vidaarecon|recon.png|image/png"    # Recon    (project icon; safeAppID drops the dash)
)

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

for entry in "${MAPPING[@]}"; do
  IFS='|' read -r id file ctype <<<"$entry"
  [ -f "$ICONS/$file" ] || { echo "ERROR: missing $ICONS/$file"; exit 1; }
  cp "$ICONS/$file" "$WORK/$id.img"
  printf '%s' "$ctype" > "$WORK/$id.type"
done

echo "==> pushing icons to $TV:$REMOTE_DIR"
ssh -p 2222 -i "$KEY" -o BatchMode=yes root@"$TV" "mkdir -p $REMOTE_DIR"
# COPYFILE_DISABLE: keep macOS from injecting AppleDouble (._*) junk
tar -cf - --exclude '._*' -C "$WORK" . | ssh -p 2222 -i "$KEY" -o BatchMode=yes root@"$TV" \
  "tar -xf - -C $REMOTE_DIR && chmod 644 $REMOTE_DIR/* && ls -la $REMOTE_DIR"

echo "==> verify:"
for entry in "${MAPPING[@]}"; do
  IFS='|' read -r id file ctype <<<"$entry"
  raw="$id"
  # reconstruct the original appId for the URL: safe id only strips non-alnum
  case "$id" in vidaarecon) raw="vidaa-recon" ;; esac
  printf '  /icon/%-12s -> ' "$raw"
  curl -s --max-time 6 -o /dev/null -w '%{http_code} %{content_type}\n' \
    "http://$TV:8770/icon/$raw"
done
