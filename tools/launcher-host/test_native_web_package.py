"""Archive metadata/scope tests; never require proprietary firmware or credentials."""
import hashlib
import importlib.util
import json
import struct
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("native_web_package", Path(__file__).with_name("package-native-web.py"))
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load package builder")
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


class PackageTests(unittest.TestCase):
    def test_deterministic_private_archive_and_credential_exclusion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = root / "assets"
            (assets / "symbols").mkdir(parents=True)
            files = {"symbols/fixture.png": b"public fixture raster", "fonts.css": b"/* fixture font CSS */"}
            for name, data in files.items():
                (assets / name).write_bytes(data)
            (assets / "assets.json").write_text(json.dumps({"upstream": PACKAGE.REVISION, "files": {
                name: hashlib.sha256(data).hexdigest() for name, data in files.items()
            }}))
            (assets / "private-key.json").write_text("must never be packaged")
            binary = bytearray(20)
            binary[:6] = b"\x7fELF\x01\x01"
            struct.pack_into("<H", binary, 18, 40)
            helper = root / "helper"
            helper.write_bytes(binary)

            def build_candidate(arguments, **_kwargs):
                Path(arguments[-1]).write_bytes(b"/* ALVIDAA_FREE_MY_TV_NATIVE_V1 ALVIDAA_FREE_MY_TV_WEB_PARITY_V2 synthetic fixture */")

            with patch.object(PACKAGE, "PRIVATE", root), patch.object(PACKAGE.subprocess, "run", build_candidate):
                first, second = root / "a.tar.gz", root / "b.tar.gz"
                receipt = PACKAGE.build(root / "unused-stock", assets, helper, first)
                PACKAGE.build(root / "unused-stock", assets, helper, second)
                self.assertEqual(first.read_bytes(), second.read_bytes())
                self.assertEqual(first.stat().st_mode & 0o777, 0o600)
                with self.assertRaisesRegex(ValueError, "overwrite"):
                    PACKAGE.build(root / "unused-stock", assets, helper, first)
                with tarfile.open(first) as archive:
                    members = archive.getmembers()
                    self.assertTrue(all(member.uid == 0 and member.gid == 0 for member in members))
                    self.assertFalse(any("private-key" in member.name or "/keys/" in member.name for member in members))
                    self.assertEqual(archive.getmember("runtime").mode, 0o700)
                    self.assertEqual(archive.getmember("runtime/native-image").mode, 0o755)
                    self.assertEqual(archive.getmember("runtime/native-web-service.cjs").mode, 0o600)
                    for name, entry in receipt["files"].items():
                        stream = archive.extractfile(name)
                        if stream is None:
                            self.fail("Expected regular archive member")
                        data = stream.read()
                        self.assertEqual(len(data), entry["size"])
                        self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])
                    stage = root / "stage"
                    stage.mkdir(mode=0o700)
                    for member in members:
                        if not member.isfile():
                            continue
                        target = stage / member.name
                        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                        stream = archive.extractfile(member)
                        if stream is None:
                            self.fail("Expected regular release member")
                        target.write_bytes(stream.read())
                        target.chmod(member.mode)
            verified = PACKAGE.subprocess.run(
                ["node", str(stage / "runtime/native-web-release.cjs"), "verify", str(stage)],
                check=True, capture_output=True, text=True,
            )
            self.assertEqual(json.loads(verified.stdout)["candidate"], receipt["candidate"])

    def test_manifest_escape_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "private.json"
            outside.write_bytes(b"private fixture")
            assets = root / "assets"
            assets.mkdir()
            expected = hashlib.sha256(outside.read_bytes()).hexdigest()
            (assets / "alias.ttf").symlink_to(outside)
            for name in ("../private.json", "alias.ttf", "/private.json"):
                with self.assertRaises(ValueError):
                    PACKAGE.checked_files(assets, {"files": {name: expected}})

    def test_public_output_is_refused_before_reading_inputs(self):
        with self.assertRaisesRegex(ValueError, "firmware"):
            PACKAGE.build(Path("missing"), Path("missing"), Path("missing"), Path("public-release.tar.gz"))


if __name__ == "__main__":
    unittest.main()
