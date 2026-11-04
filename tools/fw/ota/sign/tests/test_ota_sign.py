"""Round-trip test for the OTA signing primitive. No network, no vendor key."""

import base64
import hashlib
import sys
import urllib.parse
from pathlib import Path

import pytest

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import padding, rsa  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ota_sign  # noqa: E402


def _new_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def test_hitvsign_roundtrip():
    key = _new_key()
    content = "field=value&field2=value2"
    signature = ota_sign.hitvsign(content, key.public_key())

    encrypted = base64.b64decode(urllib.parse.unquote(signature), validate=True)
    assert len(encrypted) == key.key_size // 8
    assert signature == urllib.parse.quote(base64.b64encode(encrypted).decode("ascii"), safe="")

    plaintext = key.decrypt(encrypted, padding.PKCS1v15())
    assert plaintext == hashlib.md5(content.encode("utf-8")).digest()


def test_load_public_key_and_cli(tmp_path, capsys):
    key = _new_key()
    pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    key_path = tmp_path / "pub.pem"
    key_path.write_bytes(pem)

    assert ota_sign.main(["--pubkey", str(key_path), "--string", "hello"]) == 0
    signature = capsys.readouterr().out.strip()
    encrypted = base64.b64decode(urllib.parse.unquote(signature), validate=True)
    assert key.decrypt(encrypted, padding.PKCS1v15()) == hashlib.md5(b"hello").digest()


def test_selftest():
    assert ota_sign.run_selftest() > 0
