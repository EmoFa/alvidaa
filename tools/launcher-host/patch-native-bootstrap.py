#!/usr/bin/env python3
"""Remove only the extra launcher-server block from a private root installer IPK."""
import argparse
import gzip
import io
import subprocess
import tarfile
from pathlib import Path


def members(data):
    if not data.startswith(b"!<arch>\n"):
        raise ValueError("Not an ar/IPK archive")
    offset = 8
    result = []
    while offset < len(data):
        header = data[offset:offset + 60]
        if len(header) != 60 or header[-2:] != b"`\n":
            raise ValueError("Malformed ar header")
        size = int(header[48:58])
        body = data[offset + 60:offset + 60 + size]
        if len(body) != size:
            raise ValueError("Truncated ar member")
        result.append((header[:16].decode().strip().rstrip("/"), header, body))
        offset += 60 + size + size % 2
    return result


def patch(data):
    entries = members(data)
    if [name for name, _, _ in entries].count("control.tar.gz") != 1:
        raise ValueError("Expected exactly one control archive")
    output = bytearray(b"!<arch>\n")
    patched = False
    for name, header, body in entries:
        if name == "control.tar.gz":
            out = io.BytesIO()
            with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as src, tarfile.open(fileobj=out, mode="w") as dest:
                    for info in src.getmembers():
                        handle = src.extractfile(info) if info.isfile() else None
                        content = handle.read() if handle is not None else None
                        if info.name.lstrip("./") == "postinst":
                            if patched or content is None:
                                raise ValueError("Unexpected postinst entry")
                            start = b'echo "--- step: launcher host ---"'
                            end = b'echo "--- step: phone home ---"'
                            if content.count(start) != 1 or content.count(end) != 1:
                                raise ValueError("Unknown bootstrap revision; refusing to guess")
                            a, b = content.index(start), content.index(end)
                            block = content[a:b]
                            if b <= a or b"/var/local/alvidaa/alvidaa-bridge" not in block or b"/APPS/launcher/server.js" not in block:
                                raise ValueError("Both expected launcher paths must be in the removable block")
                            content = content[:a] + b'echo "--- native Home: no extra launcher server ---"\n  ' + content[b:]
                            subprocess.run(["sh", "-n"], input=content, check=True, capture_output=True)
                            info.size = len(content)
                            patched = True
                        dest.addfile(info, io.BytesIO(content) if content is not None else None)
            body = gzip.compress(out.getvalue(), mtime=0)
            header = header[:48] + str(len(body)).encode().ljust(10) + header[58:]
        output.extend(header + body + (b"\n" if len(body) % 2 else b""))
    if not patched:
        raise ValueError("Missing postinst")
    result = bytes(output)
    original = {n: b for n, _, b in entries if n != "control.tar.gz"}
    updated = {n: b for n, _, b in members(result) if n != "control.tar.gz"}
    if original != updated:
        raise AssertionError("Non-control payload changed")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    private = Path(__file__).resolve().parents[2] / "firmware"
    if not output.is_relative_to(private):
        parser.error("Vendor-containing output must stay under firmware/")
    result = patch(args.original.read_bytes())
    with output.open("xb") as file:
        output.chmod(0o600)
        file.write(result)
    print("Patched launcher boot block only; other IPK members unchanged")


if __name__ == "__main__":
    main()
