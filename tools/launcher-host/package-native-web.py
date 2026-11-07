#!/usr/bin/env python3
"""Build a deterministic, credential-free private native-web release archive."""
import argparse
import gzip
import hashlib
import io
import json
import os
import struct
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
PRIVATE = HERE.parents[1] / "firmware"
REVISION = "f2d984c51edca1544e39f2d44cdf86b75b0b6703"
RUNTIME = (
    "native-feed-worker.cjs", "native-feed-engine.cjs", "native-feed-http.cjs",
    "native-feed-images.cjs", "native-web-program.cjs", "native-web-locale.cjs",
    "native-web-service.cjs", "native-web-boot.cjs", "native-web-release.cjs", "native-feed-boot.sh",
    "native-home.cjs", "native-trial.cjs", "native-update.cjs",
    "stock-ui-restart.cjs", "retire-native-bridge.cjs",
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_files(directory, manifest):
    result = {}
    for name, expected in manifest["files"].items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise ValueError("Unsafe manifest path")
        file = directory / name
        if file.is_symlink() or not file.resolve().is_relative_to(directory.resolve()):
            raise ValueError("Manifest entry escapes its source tree")
        data = file.read_bytes()
        if digest(data) != expected:
            raise ValueError("Integrity mismatch: " + name)
        result[name] = data
    return result


def build(stock, assets, processor, output):
    output = output.resolve()
    if not output.is_relative_to(PRIVATE):
        raise ValueError("Firmware-containing output must remain under firmware/")
    binary = processor.read_bytes()
    if len(binary) < 20 or binary[:6] != b"\x7fELF\x01\x01" or struct.unpack_from("<H", binary, 18)[0] != 40:
        raise ValueError("Expected a Linux ARM32 little-endian image helper, not a host binary")
    manifest_bytes = (assets / "assets.json").read_bytes()
    try:
        asset_manifest = json.loads(manifest_bytes)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("Invalid generated asset manifest") from None
    if asset_manifest["upstream"] != REVISION:
        raise ValueError("Unexpected asset source revision")
    asset_id = digest(manifest_bytes)[:20]
    asset_files = checked_files(assets, asset_manifest)
    for name in asset_files:
        if name not in ("fonts.css", "OFL.txt", "LICENSE-material-symbols.txt") and not (
            name.startswith("fonts/") and name.endswith(".ttf") or
            name.startswith("symbols/") and name.endswith(".png")
        ):
            raise ValueError("Unexpected generated asset type")
    upstream = HERE / "third-party/free-my-tv/upstream"
    upstream_bytes = (upstream / "MANIFEST.json").read_bytes()
    try:
        upstream_manifest = json.loads(upstream_bytes)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("Invalid pinned upstream manifest") from None
    if upstream_manifest["revision"] != REVISION:
        raise ValueError("Unexpected upstream revision")
    upstream_files = checked_files(upstream, upstream_manifest)
    files = {"runtime/" + name: (HERE / name).read_bytes() for name in RUNTIME}
    for name in ("LICENSE", "README.md"):
        files["runtime/third-party/free-my-tv/" + name] = (HERE / "third-party/free-my-tv" / name).read_bytes()
    files.update({"runtime/third-party/free-my-tv/upstream/" + name: data for name, data in upstream_files.items()})
    files["runtime/third-party/free-my-tv/upstream/MANIFEST.json"] = upstream_bytes
    files["runtime/native-image"] = binary
    with tempfile.TemporaryDirectory(prefix="fmtv-package-") as temporary:
        candidate = Path(temporary) / "candidate.js"
        subprocess.run(["node", str(HERE / "build-native-web.cjs"), str(stock), str(assets), str(candidate)], check=True, capture_output=True)
        files["runtime/candidate.js"] = candidate.read_bytes()
    files.update({"assets/" + asset_id + "/" + name: data for name, data in asset_files.items()})
    files["assets/" + asset_id + "/assets.json"] = manifest_bytes
    receipt = {"version": 1, "upstream": REVISION, "assetId": asset_id,
               "candidate": digest(files["runtime/candidate.js"]),
               "files": {name: {"sha256": digest(data), "size": len(data)} for name, data in sorted(files.items())}}
    files["RELEASE.json"] = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode()
    directories = set()
    for name in files:
        directories.update(str(parent) for parent in PurePosixPath(name).parents if str(parent) != ".")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        stream = output.open("xb")
    except FileExistsError:
        raise ValueError("Refusing to overwrite an existing release archive") from None
    try:
        with stream:
            os.fchmod(stream.fileno(), 0o600)
            with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed, \
                    tarfile.open(fileobj=compressed, mode="w") as archive:
                for name in sorted(directories):
                    info = tarfile.TarInfo(name)
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o755 if name.startswith("assets") else 0o700
                    archive.addfile(info)
                for name, data in sorted(files.items()):
                    info = tarfile.TarInfo(name)
                    info.mode = 0o755 if name == "runtime/native-image" else 0o644 if name.startswith("assets/") else 0o600
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("stock", "assets", "processor", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    receipt = build(args.stock, args.assets, args.processor, args.output)
    print(json.dumps({"candidate": receipt["candidate"], "assetId": receipt["assetId"], "files": len(receipt["files"])}))


if __name__ == "__main__":
    main()
