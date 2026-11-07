#!/usr/bin/env python3
"""Reproduce the pinned, public upstream web package without reading private config.

Usage: python tools/launcher-host/vendor-free-my-tv.py /path/to/upstream-clone [--check]
Only the pinned Git objects are used, never untracked files or working-tree edits.
"""
import argparse
import hashlib
import importlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

PIN = "f2d984c51edca1544e39f2d44cdf86b75b0b6703"
DEST = Path(__file__).resolve().parent / "third-party/free-my-tv/upstream"


def snapshot(source):
    archive = subprocess.run(
        ["git", "-C", str(source), "archive", PIN, "web", "tools", "app/assets", "app/res/drawable"],
        check=True, capture_output=True,
    ).stdout
    with tempfile.TemporaryDirectory(prefix="fmtv-pinned-source-") as directory:
        with tarfile.open(fileobj=io.BytesIO(archive)) as package:
            package.extractall(directory, filter="data")
        tools = str(Path(directory) / "tools")
        sys.path.insert(0, tools)
        try:
            webapp = importlib.import_module("webapp")
            files = webapp.files(dict(webapp.GENERIC), "alvidaa pinned upstream " + PIN)
        finally:
            sys.path.remove(tools)
            sys.modules.pop("webapp", None)
            sys.modules.pop("translate", None)
    for name in files:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Unsafe upstream package path")
    try:
        config = files["config.js"].decode("utf-8").split("window.CONFIG = ", 1)[1].strip().removesuffix(";")
        key = json.loads(config)["tmdbKey"]
    except (KeyError, IndexError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Upstream generic configuration has an unexpected format") from error
    if key:
        raise ValueError("Public upstream snapshot must never contain an API key")
    manifest = {"repository": "https://github.com/felipericardo/tv-launcher", "revision": PIN,
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files["MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = snapshot(args.source)
    if args.check:
        actual = {str(p.relative_to(DEST)) for p in DEST.rglob("*") if p.is_file()}
        if actual != set(files) or any((DEST / name).read_bytes() != data for name, data in files.items()):
            raise SystemExit("Upstream snapshot differs from the pinned public package")
        print("Pinned upstream snapshot verified")
        return
    if DEST.exists():
        raise SystemExit("Snapshot already exists; use --check rather than overwriting it")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".upstream-stage-", dir=DEST.parent) as stage:
        output = Path(stage) / "upstream"
        output.mkdir()
        for name, data in files.items():
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if DEST.exists():
            raise SystemExit("Snapshot appeared concurrently; refusing replacement")
        output.rename(DEST)
    print(f"Vendored {len(files) - 1} public upstream files and integrity manifest")


if __name__ == "__main__":
    main()
