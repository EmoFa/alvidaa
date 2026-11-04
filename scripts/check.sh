#!/usr/bin/env bash
# Repo health check — read-only, safe to run any time.
#
#   1. generated tables match their JSON sources (inventory, exploits)
#   2. every tracked python file parses
#   3. every tracked shell script passes `bash -n`
#   4. every relative markdown link resolves
#
# Usage: scripts/check.sh          (from any directory)
# Exit 0 = clean, 1 = at least one failure. Writes nothing to the tree.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
fail=0

step() { printf '\n==> %s\n' "$*"; }

step "1/4 generated tables vs JSON sources"
python3 scripts/gen-inventory.py --check || fail=1
python3 scripts/gen-exploits.py --check || fail=1

step "2/4 python syntax"
python3 - <<'PY' || fail=1
import ast, subprocess, sys

raw = subprocess.run(["git", "ls-files", "-z", "*.py"],
                     capture_output=True, check=True).stdout
files = [p.decode() for p in raw.split(b"\0") if p]
bad = []
for path in files:
    try:
        ast.parse(open(path, encoding="utf-8").read(), filename=path)
    except SyntaxError as e:
        bad.append(f"   FAIL {path}:{e.lineno}: {e.msg}")
    except OSError as e:
        bad.append(f"   FAIL {path}: {e.strerror or e}")
print("\n".join(bad) if bad else f"   {len(files)} files parsed")
sys.exit(1 if bad else 0)
PY

step "3/4 shell syntax"
shells=0
while IFS= read -r f; do
  shells=$((shells + 1))
  bash -n "$f" || { echo "   FAIL $f"; fail=1; }
done < <(git ls-files '*.sh')
echo "   $shells scripts checked"

step "4/4 relative markdown links"
python3 - <<'PY' || fail=1
import pathlib, re, subprocess, sys

raw = subprocess.run(["git", "ls-files", "-z", "*.md"],
                     capture_output=True, check=True).stdout
files = [pathlib.Path(p.decode()) for p in raw.split(b"\0") if p]
link = re.compile(r'\[[^\]]*\]\(([^)]+)\)')
skip = ("http://", "https://", "mailto:", "tel:")
bad = []
for doc in files:
    try:
        text = doc.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        bad.append(f"   FAIL {doc}: {e.strerror or e}")
        continue
    for target in link.findall(text):
        target = target.split("#", 1)[0].strip()
        if not target or target.startswith(skip):
            continue
        if not (doc.parent / target).resolve().exists():
            bad.append(f"   FAIL {doc} -> {target}")
print("\n".join(bad) if bad else f"   {len(files)} markdown files checked")
sys.exit(1 if bad else 0)
PY

if [ "$fail" -eq 0 ]; then
  printf '\nOK — repo checks clean\n'
else
  printf '\nFAILED — see above\n'
fi
exit "$fail"
