#!/usr/bin/env bash
# Cross-compile the on-TV daemon for the TV: Linux armv7, fully static.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/bridge/dist}"
VERSION="${VERSION:-$(git -C "$ROOT" describe --always --dirty 2>/dev/null || echo dev)}"

mkdir -p "$OUT"
cd "$ROOT/bridge"

CGO_ENABLED=0 GOOS=linux GOARCH=arm GOARM=7 \
  go build -trimpath -ldflags "-s -w -X main.version=$VERSION" \
  -o "$OUT/alvidaa-bridge-armv7" .

echo "built: $OUT/alvidaa-bridge-armv7 ($VERSION)"
file "$OUT/alvidaa-bridge-armv7"
