#!/usr/bin/env python3
"""Add/remove only the native feed boot fragment in a private retired-bridge IPK."""
import argparse
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("native_ipk_patch", HERE / "patch-native-bootstrap.py")
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
ANCHOR = b'echo "--- native Home: no extra launcher server ---"\n  '


def transform(content, remove=False):
    fragment = (HERE / "native-feed-boot.sh").read_bytes()
    installed = ANCHOR + fragment + b"  "
    if remove:
        if content.count(installed) != 1:
            raise ValueError("Expected exactly the owned feed boot fragment")
        return content.replace(installed, ANCHOR, 1)
    if content.count(ANCHOR) != 1 or b"ALVIDAA_NATIVE_WEB_FEED_V1" in content:
        raise ValueError("Unknown or already modified retired-bridge bootstrap")
    if ANCHOR + b'echo "--- step: phone home ---"' not in content:
        raise ValueError("Unexpected changes next to the retirement marker")
    return content.replace(ANCHOR, installed, 1)


def patch(data, remove=False):
    return BASE.patch(data, lambda content: transform(content, remove))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(HERE.parents[1] / "firmware"):
        parser.error("Vendor-containing output must stay under firmware/")
    result = patch(args.original.read_bytes(), args.remove)
    with output.open("xb") as stream:
        output.chmod(0o600)
        stream.write(result)
    print("Patched only the owned feed boot fragment; other payloads preserved")


if __name__ == "__main__":
    main()
