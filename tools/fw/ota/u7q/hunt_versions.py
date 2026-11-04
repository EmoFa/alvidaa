#!/usr/bin/env python3
"""Private, rate-limited Hisense OTA `check_version` version hunt (own device only).

What it does
------------
Sends a small, ordered list of candidate `currentVersion` values to the fixed
Hisense EU upgrade endpoint and records the (redacted) responses, so the owner
of a 100U7Q / 100U65QEVS device can see whether any candidate resolves to an
upgrade rule or firmware URL.

Hard safety properties
----------------------
* Endpoint host/path are hardcoded. There is no --host / --url option.
* Redirects are never followed (http.client); a 3xx is recorded, not chased.
* No socket is opened unless --allow-network is given. Default is --dry-run.
* The access token is read from HISENSE_ACCESS_TOKEN only. It is never printed,
  never written to disk, and is redacted as `***` in every output and file.
* Small request budget (default 7, hard cap 10) with a >=5 s delay, 20 s timeout,
  at most one retry per request after a transport error.
* No login, no sign_in, no token generation, no appKey/appSecret, no credential
  guessing, no credential storage.

This is published as a research tool. It is still a personal diagnostic: the
default is `--dry-run`, it never logs in, never generates credentials, and only
uses a token you already hold for your own device.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import socket
import ssl
import sys
import time
from pathlib import Path
from urllib.parse import quote

# --- Fixed target -----------------------------------------------------------
ENDPOINT_HOST = "upgrade-eu.hismarttv.com"
ENDPOINT_PATH = "/upgrade/check_version"
ENDPOINT_URL = "https://" + ENDPOINT_HOST + ENDPOINT_PATH

TIMEOUT_SECONDS = 20.0
MAX_REQUESTS_HARD_CAP = 10
MIN_DELAY_SECONDS = 5.0
MAX_RESPONSE_BYTES = 1_048_576
REDACTED = "***"

HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded;charset=iso-8859-1",
    "User-Agent": "HisenseTV",
    "Accept": "*/*",
    "Connection": "close",
}

# First entry is the version the owner's TV reports. All others are UNVERIFIED
# candidates (paid-mirror listing or hand-guess) -- they are *not* evidence that
# a corresponding firmware image exists upstream.
CURRENT_DEVICE_VERSION = "V0000.09.60I.Q0813"
BUILTIN_VERSIONS: tuple[str, ...] = (
    CURRENT_DEVICE_VERSION,
    "V0000.09.60I.Q0525",
    "E009-Q0525",
    "E010-P1009",
    "E006-P0528",
    "E005-P0430",
    "E004-P0320",
)

# Server codes that mean "stop now, the remaining requests cannot succeed".
FATAL_CODES = {
    "100013": (
        "accessToken missing/expired: this helper cannot obtain a token. "
        "Issue a fresh token from your own device session outside this script "
        "and rerun. Do not hammer the endpoint."
    ),
    "100014": (
        "parameter error (deviceId): the request body does not match the "
        "device binding the server expects. Stop and report back; guessing "
        "more parameters is out of scope for this helper."
    ),
}

_ERROR_CODE_RE = re.compile(r'"?errorCode"?\s*[:=>]+\s*"?(-?\d+)', re.IGNORECASE)
_ERROR_MSG_RE = re.compile(r'"?errorMessage"?\s*[:=>]+\s*"?([^"&<\r\n]*)', re.IGNORECASE)
_URL_RE = re.compile(r'https?://[^\s"\'<>&]+', re.IGNORECASE)


class TransportError(RuntimeError):
    """Network-level failure after the single allowed retry."""


# --- Request construction ---------------------------------------------------
def q(value: str) -> str:
    """Percent-encode one form value (no character left unencoded but unreserved)."""
    return quote(str(value), safe="", encoding="utf-8", errors="strict")


def build_body(
    *,
    version: str,
    dvc_rsv: str,
    stat_code: str,
    post_code: str,
    brand_code: str,
    mac: str,
    lang: str,
    token: str,
) -> str:
    """Build the exact check_version form body, in the documented field order."""
    parts = [
        "msgVersion=513",
        "msgType=256",
        "msgId=66",
        "currentVersion=" + q(version),
        "dvcRsv=" + q(dvc_rsv),
    ]
    # Optional fields are only appended when non-empty.
    for key, value in (
        ("statCode", stat_code),
        ("postCode", post_code),
        ("brandCode", brand_code),
        ("MAC", mac),
    ):
        if value:
            parts.append(key + "=" + q(value))
    parts.extend(
        (
            "accessToken=" + q(token),
            "version=7.0",
            "format=0",
            "sourceType=1",
            "languageId=" + q(lang),
        )
    )
    return "&".join(parts)


def _token_variants(token: str) -> list[str]:
    """Raw and percent-encoded spellings of the token, longest first."""
    variants = [token, q(token), q(token).lower()]
    unique: list[str] = []
    for value in variants:
        if value and value not in unique:
            unique.append(value)
    return sorted(unique, key=len, reverse=True)


def redact(text: str, token: str) -> str:
    """Replace every known spelling of the token with `***`."""
    if not text or not token:
        return text
    out = text
    for variant in _token_variants(token):
        out = out.replace(variant, REDACTED)
    return out


def safe_version(version: str) -> str:
    """Filename-safe, bounded rendering of a version string."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", version).strip("._-")
    return (cleaned or "version")[:60]


# --- Response parsing -------------------------------------------------------
def parse_response(text: str) -> tuple[str | None, str, list[str]]:
    """Extract errorCode, errorMessage and any URL-ish fields. Best effort only."""
    code: str | None = None
    match = _ERROR_CODE_RE.search(text)
    if match:
        code = match.group(1)

    message = ""
    match = _ERROR_MSG_RE.search(text)
    if match:
        message = match.group(1).strip()

    urls: list[str] = []
    for candidate in _URL_RE.findall(text):
        cleaned = candidate.rstrip(".,;:)")
        if cleaned and cleaned not in urls:
            urls.append(cleaned)
    return code, message, urls


# --- Network ----------------------------------------------------------------
def send_request(body: str, *, allow_network: bool, timeout: float = TIMEOUT_SECONDS) -> tuple[int, str]:
    """POST the body once. Refuses to run without --allow-network (exit 2).

    http.client never follows redirects, so a 3xx is returned as a plain status.
    """
    if not allow_network:
        print(
            "refusing to send: --allow-network was not given; no socket opened",
            file=sys.stderr,
        )
        raise SystemExit(2)

    payload = body.encode("ascii")
    context = ssl.create_default_context()
    conn = http.client.HTTPSConnection(ENDPOINT_HOST, timeout=timeout, context=context)
    try:
        conn.request("POST", ENDPOINT_PATH, body=payload, headers=HEADERS)
        response = conn.getresponse()
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        text = raw.decode("utf-8", "replace")
        if len(raw) > MAX_RESPONSE_BYTES:
            text += "\n[truncated: response exceeded 1 MiB]"
        return response.status, text
    finally:
        conn.close()


def send_with_retry(
    body: str,
    *,
    allow_network: bool,
    timeout: float,
    pause: float,
) -> tuple[int, str, bool]:
    """One POST, with at most one retry after a transport error."""
    last_error: Exception | None = None
    for attempt in (1, 2):
        try:
            status, text = send_request(body, allow_network=allow_network, timeout=timeout)
            return status, text, attempt == 2
        except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
            last_error = exc
            if attempt == 1:
                time.sleep(pause)
    raise TransportError(f"{type(last_error).__name__}: {last_error}")


# --- Input handling ---------------------------------------------------------
def _validate_version(value: str) -> str:
    version = value.strip()
    if not version:
        raise ValueError("empty version string")
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) > 0x7E for ch in version):
        raise ValueError(f"version contains whitespace/control/non-ASCII characters: {value!r}")
    if len(version) > 64:
        raise ValueError(f"version longer than 64 characters: {value!r}")
    return version


def collect_versions(
    path: Path | None,
    extra: list[str] | tuple[str, ...] = (),
    include_builtin: bool = True,
) -> list[str]:
    """Built-in candidates first, then --version values, then --versions-file."""
    ordered: list[str] = []
    if include_builtin:
        for value in BUILTIN_VERSIONS:
            ordered.append(_validate_version(value))

    for value in extra:
        try:
            ordered.append(_validate_version(value))
        except ValueError as exc:
            raise SystemExit(f"invalid --version value: {exc}") from exc

    if path is not None:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise SystemExit(f"cannot read --versions-file {path}: {exc}") from exc
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                ordered.append(_validate_version(stripped))
            except ValueError as exc:
                raise SystemExit(f"invalid version in {path}: {exc}") from exc

    unique: list[str] = []
    for value in ordered:
        if value not in unique:
            unique.append(value)
    return unique


def _unique_path(directory: Path, name: str) -> Path:
    candidate = directory / name
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    for index in range(2, 100):
        alternative = directory / f"{stem}-{index}{suffix}"
        if not alternative.exists():
            return alternative
    raise RuntimeError(f"no free filename for {name} in {directory}")


def _write_text(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _short(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    return value[: width - 1] + "…"


def _label(version: str) -> str:
    if version == CURRENT_DEVICE_VERSION:
        return "current device version"
    return "UNVERIFIED candidate"


def print_table(rows: list[dict[str, object]]) -> None:
    print()
    print(f"{'version':<24} {'code':<8} {'message':<44} url")
    print("-" * 110)
    for row in rows:
        version = str(row.get("version", ""))
        code = str(row.get("error_code") or "-")
        message = str(row.get("error_message") or "-")
        urls = row.get("urls") or []
        url = str(urls[0]) if urls else "-"
        print(f"{_short(version, 24):<24} {_short(code, 8):<8} {_short(message, 44):<44} {_short(url, 90)}")


# --- Self-test (no network) -------------------------------------------------
def run_self_test() -> int:
    fake_token = "FAKE-TOKEN_a+b/c=d&e"
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"ok   {name}")
        else:
            print(f"FAIL {name} {detail}")
            failures.append(name)

    common = dict(
        dvc_rsv="100U65QEVS",  # sanitize:allow (model family, not a device id)
        stat_code="DEU",
        post_code="",
        brand_code="his",
        mac="02:00:00:00:00:01",  # sanitize:allow (fake self-test value)
        lang="0",
        token=fake_token,
    )
    body = build_body(version="E009-Q0525", **common)
    check(
        "body prefix/order",
        body.startswith(
            "msgVersion=513&msgType=256&msgId=66&currentVersion=E009-Q0525&dvcRsv=100U65QEVS"  # sanitize:allow
            "&statCode=DEU&brandCode=his&MAC=02%3A00%3A00%3A00%3A00%3A01&accessToken="  # sanitize:allow
        ),
        body,
    )
    check("encoded token present exactly once", body.count(q(fake_token)) == 1)
    check(
        "body tail order",
        body.endswith("&version=7.0&format=0&sourceType=1&languageId=0"),
        body,
    )

    redacted_body = redact(body, fake_token)
    check("raw token absent after redaction", fake_token not in redacted_body)
    check("encoded token absent after redaction", q(fake_token) not in redacted_body)
    check("redaction marker present", "accessToken=***" in redacted_body)

    minimal = build_body(version="E004-P0320", dvc_rsv="100U65QEVS", stat_code="", post_code="", brand_code="", mac="", lang="0", token=fake_token)  # sanitize:allow
    check("optional fields omitted when empty", "statCode" not in minimal and "MAC=" not in minimal and "postCode" not in minimal)
    check("required fields always present", minimal.startswith("msgVersion=513&msgType=256&msgId=66&currentVersion=E004-P0320&dvcRsv=100U65QEVS&accessToken="), minimal)  # sanitize:allow

    check("safe filename has no separator", "/" not in safe_version("a/b") and "\\" not in safe_version("a\\b"))
    check("safe filename is bounded", len(safe_version("X" * 200)) <= 60)
    check("safe filename fallback", safe_version("??") == "version")
    check("filename pattern", re.fullmatch(r"\d{8}-\d{6}-" + re.escape(safe_version("E009-Q0525")) + r"\.txt", "20261103-101500-E009-Q0525.txt") is not None)

    xml = (
        "<result><errorCode>205001</errorCode>"
        "<errorMessage>no match upgrade rule, please define rules first</errorMessage>"
        "<strategyUrl>https://cdn.example/fw.pkg</strategyUrl></result>"
    )
    code, message, urls = parse_response(xml)
    check("parse xml code", code == "205001", str(code))
    check("parse xml message", message.startswith("no match upgrade rule"), message)
    check("parse xml url", urls == ["https://cdn.example/fw.pkg"], str(urls))
    code_json, _, _ = parse_response('{"errorCode":100014,"errorMessage":"parameter"}')
    check("parse json code", code_json == "100014", str(code_json))
    check("parse empty response", parse_response("") == (None, "", []))

    real_socket = socket.socket

    def _no_socket(*_args, **_kwargs):
        raise AssertionError("socket created during self-test")

    socket.socket = _no_socket  # type: ignore[assignment]
    try:
        try:
            send_request(body, allow_network=False)
            check("network guard exits", False, "send_request returned without --allow-network")
        except SystemExit as exc:
            check("network guard exit code 2", exc.code == 2, f"code={exc.code!r}")
    finally:
        socket.socket = real_socket  # type: ignore[assignment]

    if failures:
        print(f"SELF-TEST FAILED ({len(failures)} failing checks)", file=sys.stderr)
        return 1
    print("SELF-TEST OK (no network used)")
    return 0


# --- CLI --------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the fixed Hisense EU check_version endpoint with a few candidate versions.",
        epilog="Default is --dry-run. Real requests require --allow-network and a token in HISENSE_ACCESS_TOKEN.",
    )
    parser.add_argument("--versions-file", type=Path, help="extra candidate versions, one per line ('#' comments allowed)")
    parser.add_argument("--version", action="append", default=[], help="candidate version (repeatable); use with --no-builtin for a targeted run")
    parser.add_argument("--no-builtin", action="store_true", help="do not include the built-in candidate list")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "hunt", help="directory for responses and summary.json (default: <script dir>/hunt)")
    parser.add_argument("--max-requests", type=int, default=7, help="maximum requests, 1..10 (default: 7)")
    parser.add_argument("--dvc-rsv", help="override HISENSE_DVC_RSV (machine type)")
    parser.add_argument("--stat-code", help="override HISENSE_STAT_CODE (country)")
    parser.add_argument("--post-code", help="override HISENSE_POST_CODE (zip)")
    parser.add_argument("--brand-code", help="override HISENSE_BRAND_CODE")
    parser.add_argument("--mac", help="override HISENSE_MAC")
    parser.add_argument("--lang", help="override HISENSE_LANG")
    parser.add_argument("--delay", type=float, default=8.0, help=f"seconds between requests, >= {MIN_DELAY_SECONDS:g} (default: 8)")
    parser.add_argument("--dry-run", action="store_true", help="print requests with the token redacted (default)")
    parser.add_argument("--allow-network", action="store_true", help="actually send requests; without this the helper is dry-run only")
    parser.add_argument("--self-test", action="store_true", help="run body-builder/redaction/guard checks without network")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    if not 1 <= args.max_requests <= MAX_REQUESTS_HARD_CAP:
        parser.error(f"--max-requests must be between 1 and {MAX_REQUESTS_HARD_CAP}")
    if args.delay < MIN_DELAY_SECONDS:
        parser.error(f"--delay must be at least {MIN_DELAY_SECONDS:g} seconds")

    raw_token = os.environ.get("HISENSE_ACCESS_TOKEN", "")
    token = raw_token.strip()
    if not token:
        print("error: HISENSE_ACCESS_TOKEN is not set (or empty). Provide your own device token.", file=sys.stderr)
        return 2
    if any(ch.isspace() for ch in token):
        print("error: HISENSE_ACCESS_TOKEN contains whitespace; refusing to send a malformed token.", file=sys.stderr)
        return 2
    if any(ord(ch) < 0x20 or ord(ch) > 0x7E for ch in token):
        print("error: HISENSE_ACCESS_TOKEN contains non-ASCII/control characters.", file=sys.stderr)
        return 2

    dvc_rsv = (args.dvc_rsv or os.environ.get("HISENSE_DVC_RSV", "100U65QEVS")).strip()
    stat_code = (args.stat_code or os.environ.get("HISENSE_STAT_CODE", "DEU")).strip()
    post_code = (args.post_code if args.post_code is not None else os.environ.get("HISENSE_POST_CODE", "")).strip()
    brand_code = (args.brand_code or os.environ.get("HISENSE_BRAND_CODE", "his")).strip()
    mac_value = (args.mac if args.mac is not None else os.environ.get("HISENSE_MAC", "")).strip()
    lang = (args.lang or os.environ.get("HISENSE_LANG", "0")).strip() or "0"
    if not dvc_rsv:
        print("error: HISENSE_DVC_RSV is empty.", file=sys.stderr)
        return 2

    versions = collect_versions(args.versions_file, args.version, not args.no_builtin)
    if len(versions) > args.max_requests:
        print(
            f"note: {len(versions)} candidates queued, limiting to --max-requests {args.max_requests}",
            file=sys.stderr,
        )
        versions = versions[: args.max_requests]

    def body_for(version: str) -> str:
        return build_body(
            version=version,
            dvc_rsv=dvc_rsv,
            stat_code=stat_code,
            post_code=post_code,
            brand_code=brand_code,
            mac=mac_value,
            lang=lang,
            token=token,
        )

    if args.dry_run or not args.allow_network:
        if not args.allow_network and not args.dry_run:
            print("note: --allow-network not given -> dry-run only, no socket will be opened.", file=sys.stderr)
        print(f"endpoint: POST {ENDPOINT_URL} (fixed)")
        print(f"device:   dvcRsv={dvc_rsv} statCode={stat_code or '-'} brandCode={brand_code or '-'} "
              f"postCode={'set' if post_code else 'empty'} MAC={'set' if mac_value else 'empty'} languageId={lang}")
        for index, version in enumerate(versions, 1):
            print()
            print(f"[dry-run {index}/{len(versions)}] {version} ({_label(version)})")
            print(f"POST {ENDPOINT_URL}")
            print("body: " + redact(body_for(version), token))
        print()
        print(f"dry-run complete: {len(versions)} request(s) shown, 0 sent, token redacted as {REDACTED}.")
        return 0

    out_dir: Path = args.out
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"error: cannot create output directory {out_dir}: {exc}", file=sys.stderr)
        return 2

    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    results: list[dict[str, object]] = []
    stop_reason: str | None = None

    for index, version in enumerate(versions, 1):
        if index > 1:
            time.sleep(args.delay)

        body = body_for(version)
        print(f"[{index}/{len(versions)}] {version} ({_label(version)}) ...", flush=True)
        try:
            status, text, retried = send_with_retry(
                body,
                allow_network=True,
                timeout=TIMEOUT_SECONDS,
                pause=args.delay,
            )
        except TransportError as exc:
            results.append(
                {
                    "version": version,
                    "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "transport_error": str(exc),
                    "request_body": redact(body, token),
                }
            )
            stop_reason = f"transport error on {version}: {exc}"
            print(f"  transport error: {exc}", file=sys.stderr)
            print("  stopping: the network path is not working; not retrying further versions.", file=sys.stderr)
            break

        code, message, urls = parse_response(text)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        file_path = _unique_path(out_dir, f"{stamp}-{safe_version(version)}.txt")
        try:
            _write_text(file_path, redact(text, token))
        except OSError as exc:
            print(f"error: cannot write {file_path}: {exc}", file=sys.stderr)
            return 2

        entry: dict[str, object] = {
            "version": version,
            "label": _label(version),
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "http_status": status,
            "error_code": code,
            "error_message": message,
            "urls": urls,
            "retried": retried,
            "file": file_path.name,
            "request_body": redact(body, token),
        }
        if status in (301, 302, 303, 307, 308):
            entry["note"] = "redirect not followed"
        results.append(entry)

        print(f"  http={status} code={code or '-'} message={_short(message or '-', 80)}")
        if urls:
            print(f"  url={urls[0]}")

        if code in FATAL_CODES:
            stop_reason = f"server returned {code} on {version}: {FATAL_CODES[code]}"
            print(f"  stop: {FATAL_CODES[code]}", file=sys.stderr)
            break

    summary = {
        "endpoint": ENDPOINT_URL,
        "started": started,
        "finished": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "requested": len(versions),
        "answered": sum(1 for row in results if "http_status" in row),
        "dvc_rsv": dvc_rsv,
        "stat_code": stat_code,
        "post_code_supplied": bool(post_code),
        "brand_code": brand_code,
        "mac_supplied": bool(mac_value),
        "language_id": lang,
        "max_requests": args.max_requests,
        "delay_seconds": args.delay,
        "timeout_seconds": TIMEOUT_SECONDS,
        "stop_reason": stop_reason,
        "results": results,
    }
    blob = json.dumps(summary, indent=2, ensure_ascii=False)
    if token in blob or q(token) in blob:
        print("error: refusing to write summary.json: token still present after redaction.", file=sys.stderr)
        return 2
    summary_path = out_dir / "summary.json"
    try:
        _write_text(summary_path, blob + "\n")
    except OSError as exc:
        print(f"error: cannot write {summary_path}: {exc}", file=sys.stderr)
        return 2

    print_table(results)
    print()
    print(f"responses: {out_dir}")
    print(f"summary:   {summary_path}")
    if stop_reason:
        print(f"stopped:   {stop_reason}")
    print(f"token redacted as {REDACTED} in all printed and written output.")
    return 1 if stop_reason and stop_reason.startswith("transport error") else 0


if __name__ == "__main__":
    sys.exit(main())
