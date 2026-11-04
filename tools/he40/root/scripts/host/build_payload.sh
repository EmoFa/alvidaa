#!/usr/bin/env bash
# Builds the final libtvsysinfo payload from the included original.
# Requires: python3, arm-linux-gnueabihf-{as,ld,objcopy}.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"

for t in arm-linux-gnueabihf-as arm-linux-gnueabihf-ld arm-linux-gnueabihf-objcopy python3; do
  command -v "$t" >/dev/null || { echo "missing: $t"; exit 1; }
done

python3 "$HERE/build_tvi_payload.py"
echo "---"
sha256sum "$ROOT/tools/pub/libtvsysinfo.so"
echo "expected: 37b13f91959acea9b3c3fd4d0e62bb2d4cb41f773add060bef68ac67657f5b0a"
