#!/usr/bin/env sh
# Thin portable wrapper; all logic lives in fwinv.py.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/fwinv.py" "$@"
