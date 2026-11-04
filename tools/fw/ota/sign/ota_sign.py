#!/usr/bin/env python3
"""Hisense/VIDAA OTA request signing primitive.

    signature = URLEncode(base64(RSA_public_encrypt(MD5(content), pubkey,
                                                   PKCS1v15)))

The vendor public key is NOT embedded and there is no default key. Supply a PEM
public key with ``--pubkey PATH`` or the ``HISENSE_OTA_PUBKEY`` environment
variable (also a path).

This module signs a caller-provided string only. It performs no network I/O,
builds no authenticated request, and stores no credentials.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import sys
import urllib.parse

_INSTALL_HINT = (
    "the optional dependency 'cryptography' is required for signing; install it "
    "with: python -m pip install -r requirements-ota.txt"
)


class OtaSignError(Exception):
    """Raised for key, dependency, or signing errors."""


def _crypto():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
    except ImportError as exc:
        raise OtaSignError(_INSTALL_HINT) from exc
    return serialization, padding, rsa


def _md5(data):
    try:
        return hashlib.md5(data, usedforsecurity=False).digest()
    except TypeError:  # Python without the usedforsecurity keyword
        return hashlib.md5(data).digest()


def load_public_key(path):
    """Load an RSA public key from a PEM file."""
    serialization, _padding, rsa = _crypto()
    try:
        with open(path, "rb") as handle:
            pem = handle.read()
    except OSError as exc:
        raise OtaSignError("cannot read public key %r: %s" % (path, exc.strerror)) from exc
    try:
        key = serialization.load_pem_public_key(pem)
    except ValueError as exc:
        raise OtaSignError("%r is not a valid PEM public key" % path) from exc
    if not isinstance(key, rsa.RSAPublicKey):
        raise OtaSignError("%r is not an RSA public key" % path)
    return key


def hitvsign(content, pubkey):
    """Return the URL-encoded signature for ``content``.

    ``content`` is hashed as UTF-8 bytes, matching the reconstructed vendor
    script.
    """
    if not isinstance(content, str):
        raise TypeError("content must be a str")
    _serialization, padding, rsa = _crypto()
    if not isinstance(pubkey, rsa.RSAPublicKey):
        raise TypeError("pubkey must be an RSA public key")

    digest = _md5(content.encode("utf-8"))
    try:
        encrypted = pubkey.encrypt(digest, padding.PKCS1v15())
    except ValueError as exc:
        raise OtaSignError("RSA encryption failed: %s" % exc) from exc
    encoded = base64.b64encode(encrypted).decode("ascii")
    return urllib.parse.quote(encoded, safe="")


def run_selftest():
    """Sign with a throwaway key and verify the MD5 round-trip.

    Returns the signature length. No key material is printed or persisted.
    """
    _serialization, padding, rsa = _crypto()
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    content = "selftest"
    signature = hitvsign(content, private_key.public_key())
    encrypted = base64.b64decode(urllib.parse.unquote(signature), validate=True)
    plaintext = private_key.decrypt(encrypted, padding.PKCS1v15())
    if plaintext != _md5(content.encode("utf-8")):
        raise OtaSignError("selftest failed: MD5 mismatch")
    return len(signature)


def _build_parser():
    parser = argparse.ArgumentParser(
        description="Sign a string with the reconstructed Hisense OTA scheme.",
        epilog=(
            "The public key must be supplied by the user; nothing is embedded. "
            "No network access is performed."
        ),
    )
    parser.add_argument(
        "--pubkey",
        metavar="PATH",
        help="PEM RSA public key (default: HISENSE_OTA_PUBKEY, also a path)",
    )
    parser.add_argument("--string", dest="content", metavar="TEXT", help="content to sign")
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="generate a throwaway key and verify the signing round-trip",
    )
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)

    if args.selftest:
        if args.content is not None or args.pubkey is not None:
            print(
                "error: --selftest cannot be combined with --string or --pubkey",
                file=sys.stderr,
            )
            return 2
        try:
            length = run_selftest()
        except OtaSignError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 2
        print("selftest: OK (signature length %d)" % length)
        return 0

    if args.content is None:
        print("error: --string is required (or use --selftest)", file=sys.stderr)
        return 2

    key_path = args.pubkey or os.environ.get("HISENSE_OTA_PUBKEY")
    if not key_path:
        print(
            "error: no public key: pass --pubkey PATH or set HISENSE_OTA_PUBKEY",
            file=sys.stderr,
        )
        return 2

    try:
        pubkey = load_public_key(key_path)
        print(hitvsign(args.content, pubkey))
    except (OtaSignError, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
