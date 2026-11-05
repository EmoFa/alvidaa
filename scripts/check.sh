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

step "1/7 generated tables vs JSON sources"
python3 scripts/gen-inventory.py --check || fail=1
python3 scripts/gen-exploits.py --check || fail=1

step "2/7 python syntax"
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

step "3/7 shell syntax"
shells=0
while IFS= read -r f; do
  shells=$((shells + 1))
  bash -n "$f" || { echo "   FAIL $f"; fail=1; }
done < <(git ls-files '*.sh')
echo "   $shells scripts checked"

step "4/7 relative markdown links"
python3 - <<'PY' || fail=1
import pathlib, re, subprocess, sys

raw = subprocess.run(["git", "ls-files", "-z", "*.md"],
                     capture_output=True, check=True).stdout
files = [pathlib.Path(p.decode()) for p in raw.split(b"\0") if p]
link = re.compile(r'\[[^\]]*\]\(([^)]+)\)')
skip = ("http://", "https://", "mailto:", "tel:")
bad = []
for doc in files:
    # Archived research notes keep their original tree-relative links; they
    # are not part of the public navigation.
    if "source" in doc.parts:
        continue
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

step "5/7 docs site (needs: pip install markdown)"
if python3 -c "import markdown" 2>/dev/null; then
  python3 scripts/gen-site.py --check || fail=1
else
  echo "   skipped — python3 -m pip install markdown"
fi

step "6/7 model guides are indexed"
python3 - <<'PY' || fail=1
import pathlib, sys

root = pathlib.Path("docs/models")
index = (root / "README.md").read_text(encoding="utf-8")
guides = sorted(root.glob("*/*/README.md"))
missing = [f"   FAIL {g.relative_to(root).as_posix()} is not linked from docs/models/README.md"
           for g in guides if g.relative_to(root).as_posix() not in index]
print("\n".join(missing) if missing else f"   {len(guides)} guides indexed")
sys.exit(1 if missing else 0)
PY

step "7/7 no secrets or vendor binaries"
python3 - <<'PY' || fail=1
import pathlib, subprocess, sys

LIMIT = 2 * 1024 * 1024
BAD_EXT = {".ipk", ".apk", ".pkg", ".img", ".elf", ".so", ".o", ".a", ".bin", ".ko", ".deb"}
SKIP = ("tools/sanitize/",)  # test fixtures carry deliberate key material
# built from a prefix so this file does not match itself
MARK = b"-----BEGIN "
PATTERNS = (MARK + b"OPENSSH PRIVATE KEY", MARK + b"RSA PRIVATE KEY",
            MARK + b"EC PRIVATE KEY", MARK + b"PGP PRIVATE KEY",
            MARK + b"CERTIFICATE")
IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".ico", ".gif"}

files = [p for p in subprocess.run(["git", "ls-files", "-z"], capture_output=True,
                                   check=True).stdout.split(b"\0") if p]
bad = []
for raw in files:
    path = raw.decode()
    if path.startswith(SKIP):
        continue
    f = pathlib.Path(path)
    if f.suffix.lower() in BAD_EXT:
        bad.append(f"   FAIL {path}: vendor/binary artifact")
        continue
    if f.stat().st_size > LIMIT:
        bad.append(f"   FAIL {path}: {f.stat().st_size // 1024} KB (limit 2048)")
        continue
    if f.suffix.lower() in IMAGES:
        continue
    blob = f.read_bytes()
    for pat in PATTERNS:
        if pat in blob:
            bad.append(f"   FAIL {path}: contains '{pat.decode()}'")
            break
print("\n".join(bad) if bad else f"   {len(files)} files scanned")
sys.exit(1 if bad else 0)
PY

if [ "$fail" -eq 0 ]; then
  printf '\nOK — repo checks clean\n'
else
  printf '\nFAILED — see above\n'
fi
exit "$fail"
