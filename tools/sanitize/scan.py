#!/usr/bin/env python3
"""Offline secret/PII scanner for the PublicContent repository.

The scanner walks a directory tree, reads text files only, and applies the
regex rules from ``rules.toml``.  It never prints the matched value: findings
carry only the rule id, severity and category.

Exit codes
----------
0   no findings
1   findings were reported
2   usage error, unreadable rules file, or an I/O error while scanning

This tool is a guardrail, not a proof of anonymization.  A clean scan means
"none of the configured patterns matched"; human review is still required.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sys
import tomllib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

ALLOW_MARKER = "sanitize:allow"
DEFAULT_MAX_BYTES = 1024 * 1024

# Directories that never contain publishable source text.
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".venv",
    "venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
}

# Extensions that are treated as binary/opaque.  ``.fixture`` files are test
# containers: they intentionally contain fake secrets and are copied to a
# temporary directory by the test suite before being scanned.
SKIP_EXTS = {
    ".7z",
    ".a",
    ".apk",
    ".bin",
    ".bmp",
    ".bz2",
    ".class",
    ".db",
    ".deb",
    ".elf",
    ".eth",
    ".exe",
    ".fixture",
    ".gif",
    ".gz",
    ".ico",
    ".img",
    ".iso",
    ".jar",
    ".jpeg",
    ".jpg",
    ".o",
    ".p12",
    ".pcap",
    ".pdf",
    ".pkg",
    ".png",
    ".pyc",
    ".rpm",
    ".so",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".ttf",
    ".webp",
    ".woff",
    ".woff2",
    ".xz",
    ".zip",
}

SAFE_IPV4 = tuple(
    ipaddress.ip_network(value)
    for value in (
        "192.0.2.0/24",
        "198.51.100.0/24",
        "203.0.113.0/24",
    )
)
SAFE_IPV6 = (ipaddress.ip_network("2001:db8::/32"),)

SAFE_DOMAIN_SUFFIXES = (
    ".example",
    ".example.com",
    ".example.net",
    ".example.org",
    ".invalid",
    ".test",
)

# ``${TV_HOST}`` and ``<DEVICE_SERIAL>`` style placeholders.
PLACEHOLDER_RE = re.compile(r"\$\{[^}\n]{1,200}\}|<[A-Za-z][A-Za-z0-9_.-]{1,40}>")

# A line that starts with a hex digest followed by a filename, as used by
# SHA256SUMS / MD5SUMS files.
CHECKSUM_LINE_RE = re.compile(r"^\s*[0-9a-fA-F]{32,128}\s+[ *]?\S")


class ScannerError(Exception):
    """Configuration or usage problem that must exit with code 2."""


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    severity: str
    regex: re.Pattern[str]
    allow_if: re.Pattern[str] | None = None
    paths: tuple[re.Pattern[str], ...] = ()
    target: str = "content"


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule_id: str
    severity: str
    category: str

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "line": self.line,
            "rule_id": self.rule_id,
            "severity": self.severity,
            "category": self.category,
            "match_redacted": "***",
        }


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a shell-style glob into a full-match regex.

    ``*`` matches within one path segment, ``**`` matches across segments and
    ``**/`` also matches zero directories.  ``?`` matches one non-slash
    character.  Everything else is matched literally.
    """
    out: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                index += 2
                if index < len(pattern) and pattern[index] == "/":
                    out.append("(?:.*/)?")
                    index += 1
                else:
                    out.append(".*")
                continue
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(char))
        index += 1
    return re.compile("^" + "".join(out) + "$")


def compile_globs(patterns: Iterable[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(glob_to_regex(pattern) for pattern in patterns)


def rel_matches(rel_path: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    return any(pattern.match(rel_path) for pattern in patterns)


def load_rules(path: Path) -> list[Rule]:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ScannerError(f"cannot read rules file {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ScannerError(f"invalid TOML in {path}: {exc}") from exc

    items = raw.get("rules")
    if not isinstance(items, list) or not items:
        raise ScannerError(f"{path} contains no [[rules]] entries")

    rules: list[Rule] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ScannerError(f"rule #{index} is not a table")
        rule_id = item.get("id")
        category = item.get("category")
        severity = item.get("severity")
        regex_text = item.get("regex")
        if not isinstance(rule_id, str) or not rule_id:
            raise ScannerError(f"rule #{index}: missing id")
        if rule_id in seen_ids:
            raise ScannerError(f"rule #{index}: duplicate id {rule_id!r}")
        seen_ids.add(rule_id)
        if not isinstance(category, str) or not category:
            raise ScannerError(f"rule {rule_id}: missing category")
        if not isinstance(severity, str) or not severity:
            raise ScannerError(f"rule {rule_id}: missing severity")
        if not isinstance(regex_text, str) or not regex_text:
            raise ScannerError(f"rule {rule_id}: missing regex")

        flags = re.IGNORECASE if item.get("ignore_case") is True else 0
        try:
            regex = re.compile(regex_text, flags)
        except re.error as exc:
            raise ScannerError(f"rule {rule_id}: invalid regex: {exc}") from exc

        allow_if_text = item.get("allow_if")
        if allow_if_text is not None and not isinstance(allow_if_text, str):
            raise ScannerError(f"rule {rule_id}: allow_if must be a string")
        try:
            allow_if = re.compile(allow_if_text, flags) if allow_if_text else None
        except re.error as exc:
            raise ScannerError(f"rule {rule_id}: invalid allow_if regex: {exc}") from exc

        paths_value = item.get("paths", [])
        if not isinstance(paths_value, list) or not all(
            isinstance(entry, str) for entry in paths_value
        ):
            raise ScannerError(f"rule {rule_id}: paths must be a list of strings")

        target = item.get("target", "content")
        if target not in {"content", "path"}:
            raise ScannerError(f"rule {rule_id}: target must be 'content' or 'path'")

        rules.append(
            Rule(
                id=rule_id,
                category=category,
                severity=severity,
                regex=regex,
                allow_if=allow_if,
                paths=compile_globs(paths_value),
                target=target,
            )
        )
    return rules


def is_placeholder_match(line: str, start: int, end: int) -> bool:
    for match in PLACEHOLDER_RE.finditer(line):
        if match.start() <= start and end <= match.end():
            return True
    return False


def is_globally_allowed(line: str, start: int, end: int) -> bool:
    """Return True for values that are explicitly safe to publish.

    Safe values are placeholders, documentation domains, TEST-NET address
    ranges and digest lines in checksum files.
    """
    value = line[start:end]
    if is_placeholder_match(line, start, end):
        return True

    stripped = value.strip().strip("\"'")
    lowered = stripped.lower()
    if lowered in {"example.com", "example.net", "example.org"}:
        return True
    if lowered.endswith(SAFE_DOMAIN_SUFFIXES):
        return True

    try:
        address = ipaddress.ip_address(stripped)
    except ValueError:
        address = None
    if address is not None:
        if address.version == 4 and any(address in net for net in SAFE_IPV4):
            return True
        if address.version == 6 and any(address in net for net in SAFE_IPV6):
            return True

    if CHECKSUM_LINE_RE.match(line) and re.fullmatch(r"[0-9a-fA-F]+", stripped):
        return True
    return False


def scan_path_rules(rel_path: str, rules: Sequence[Rule]) -> list[Finding]:
    findings: list[Finding] = []
    for rule in rules:
        if rule.target != "path":
            continue
        if rule.paths and not rel_matches(rel_path, rule.paths):
            continue
        if rule.regex.search(rel_path):
            findings.append(
                Finding(
                    path=rel_path,
                    line=1,
                    rule_id=rule.id,
                    severity=rule.severity,
                    category=rule.category,
                )
            )
    return findings


def scan_text(rel_path: str, text: str, rules: Sequence[Rule]) -> list[Finding]:
    findings: list[Finding] = []
    content_rules = [rule for rule in rules if rule.target == "content"]
    for line_number, line in enumerate(text.splitlines(), 1):
        if ALLOW_MARKER in line.lower():
            continue
        for rule in content_rules:
            if rule.paths and not rel_matches(rel_path, rule.paths):
                continue
            if rule.allow_if is not None and rule.allow_if.search(line):
                continue
            for match in rule.regex.finditer(line):
                if not match.group(0):
                    continue
                if is_globally_allowed(line, match.start(), match.end()):
                    continue
                findings.append(
                    Finding(
                        path=rel_path,
                        line=line_number,
                        rule_id=rule.id,
                        severity=rule.severity,
                        category=rule.category,
                    )
                )
                # One finding per rule per line is enough for triage.
                break
    return findings


def iter_files(root: Path, excludes: Sequence[re.Pattern[str]]) -> Iterator[tuple[Path, str]]:
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        rel_dir = current.relative_to(root).as_posix()
        if rel_dir == ".":
            rel_dir = ""
        kept: list[str] = []
        for dirname in sorted(dirnames):
            rel = f"{rel_dir}/{dirname}" if rel_dir else dirname
            if dirname in SKIP_DIRS or rel_matches(rel, excludes):
                continue
            kept.append(dirname)
        dirnames[:] = kept
        for filename in sorted(filenames):
            rel = f"{rel_dir}/{filename}" if rel_dir else filename
            if rel_matches(rel, excludes):
                continue
            path = current / filename
            if path.is_symlink() or not path.is_file():
                continue
            yield path, rel


def skipped_by_extension(filename: str) -> bool:
    return Path(filename).suffix.lower() in SKIP_EXTS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sanitize/scan.py",
        description="Offline secret/PII scanner (values are never printed).",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit a machine-readable JSON report to stdout",
    )
    parser.add_argument(
        "--rules",
        default=None,
        help="path to rules.toml (default: rules.toml next to this script)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="exclude paths matching GLOB (repeatable, relative to --root)",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        metavar="N",
        help=f"skip files larger than N bytes (default: {DEFAULT_MAX_BYTES})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.max_bytes < 0:
        print("error: --max-bytes must not be negative", file=sys.stderr)
        return EXIT_ERROR

    root = Path(args.root)
    if not root.exists():
        print(f"error: --root does not exist: {args.root}", file=sys.stderr)
        return EXIT_ERROR
    if not root.is_dir():
        print(f"error: --root is not a directory: {args.root}", file=sys.stderr)
        return EXIT_ERROR
    root = root.resolve()

    rules_path = (
        Path(args.rules)
        if args.rules is not None
        else Path(__file__).resolve().with_name("rules.toml")
    )
    try:
        rules = load_rules(rules_path)
    except ScannerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    excludes = compile_globs(args.exclude)

    findings: list[Finding] = []
    errors: list[str] = []
    skip_reasons: Counter[str] = Counter()
    files_scanned = 0
    bytes_scanned = 0

    for path, rel_path in iter_files(root, excludes):
        if skipped_by_extension(path.name):
            skip_reasons["extension"] += 1
            continue

        findings.extend(scan_path_rules(rel_path, rules))

        try:
            size = path.stat().st_size
        except OSError as exc:
            errors.append(f"{rel_path}: cannot stat: {exc}")
            continue
        if size > args.max_bytes:
            skip_reasons["size"] += 1
            continue

        try:
            data = path.read_bytes()
        except OSError as exc:
            errors.append(f"{rel_path}: cannot read: {exc}")
            continue

        if b"\x00" in data[:4096]:
            skip_reasons["binary"] += 1
            continue

        files_scanned += 1
        bytes_scanned += len(data)
        text = data.decode("utf-8", errors="replace")
        findings.extend(scan_text(rel_path, text, rules))

    unique: list[Finding] = []
    seen: set[tuple[str, int, str]] = set()
    for finding in findings:
        key = (finding.path, finding.line, finding.rule_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    unique.sort(key=lambda item: (item.path, item.line, item.rule_id))

    severity_counts = Counter(finding.severity for finding in unique)
    summary = {
        "files_scanned": files_scanned,
        "bytes_scanned": bytes_scanned,
        "files_skipped": sum(skip_reasons.values()),
        "skip_reasons": dict(sorted(skip_reasons.items())),
        "findings": len(unique),
        "by_severity": dict(sorted(severity_counts.items())),
        "errors": len(errors),
    }

    if args.json:
        payload = {
            "tool": "sanitize/scan.py",
            "root": args.root,
            "rules": str(rules_path.name),
            "summary": summary,
            "findings": [finding.as_dict() for finding in unique],
            "errors": errors,
        }
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        for finding in unique:
            print(
                f"{finding.path}:{finding.line}: {finding.rule_id} "
                f"[{finding.severity}] {finding.category}"
            )
        print()
        print(
            f"Scanned {files_scanned} file(s), {bytes_scanned} byte(s); "
            f"skipped {sum(skip_reasons.values())} (extensions, size, binary)."
        )
        if skip_reasons:
            details = ", ".join(
                f"{reason}={count}" for reason, count in sorted(skip_reasons.items())
            )
            print(f"Skip reasons: {details}")
        if severity_counts:
            details = ", ".join(
                f"{severity}={severity_counts[severity]}"
                for severity in ("critical", "high", "medium", "low", "info")
                if severity in severity_counts
            )
            print(f"Findings: {len(unique)} ({details})")
        else:
            print("Findings: 0")
        if errors:
            print(f"Errors: {len(errors)}", file=sys.stderr)
            for message in errors:
                print(f"  {message}", file=sys.stderr)
        print("Values are never printed; matches are redacted as ***.")
        print("RESULT: " + ("FINDINGS" if unique else "CLEAN"))

    if errors:
        return EXIT_ERROR
    if unique:
        return EXIT_FINDINGS
    return EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
