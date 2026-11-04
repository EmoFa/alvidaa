"""Tests for sanitize/scan.py.

The dirty fixtures are stored with a ``.fixture`` suffix so a normal repository
scan skips them.  Each test copies them to a temporary directory under their
real names and scans that copy.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SANITIZE_DIR = Path(__file__).resolve().parents[1]
SCAN = SANITIZE_DIR / "scan.py"
RULES = SANITIZE_DIR / "rules.toml"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

FINDING_RE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+): (?P<rule>[a-z0-9_]+) "
    r"\[(?P<severity>[a-z]+)\] (?P<category>[a-z]+)$"
)


def run_scan(root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCAN),
        "--root",
        str(root),
        "--rules",
        str(RULES),
        *extra,
    ]
    return subprocess.run(command, text=True, capture_output=True, check=False)


def stage_dirty_fixtures(tmp_path: Path) -> Path:
    target = tmp_path / "dirty"
    target.mkdir()
    for source in sorted(FIXTURES.glob("*.fixture")):
        destination = target / source.name[: -len(".fixture")]
        shutil.copyfile(source, destination)
    return target


def finding_rule_ids(stdout: str) -> set[str]:
    rule_ids: set[str] = set()
    for line in stdout.splitlines():
        match = FINDING_RE.match(line)
        if match:
            rule_ids.add(match.group("rule"))
    return rule_ids


def test_dirty_fixtures_are_flagged(tmp_path: Path) -> None:
    root = stage_dirty_fixtures(tmp_path)
    result = run_scan(root)

    assert result.returncode == 1, result.stderr
    rule_ids = finding_rule_ids(result.stdout)
    expected = {
        "private_key_block",
        "certificate_block",
        "ssh_public_key",
        "ssh_fingerprint",
        "mac_address",
        "private_ipv4",
        "private_ipv6",
        "mdns_hostname",
        "serial_label",
        "netflix_esn",
        "credential_assignment",
        "jwt_token",
        "long_hex_token",
        "long_base64_secret",
        "password_hash",
        "home_path",
        "workspace_path",
        "cookie_header",
        "cloud_key",
        "password_material_file",
    }
    assert expected <= rule_ids, sorted(expected - rule_ids)
    assert "EXAMPLEONLY" not in result.stdout
    assert "RESULT: FINDINGS" in result.stdout


def test_clean_fixtures_pass() -> None:
    result = run_scan(FIXTURES / "clean")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: CLEAN" in result.stdout
    assert finding_rule_ids(result.stdout) == set()


def test_json_report_is_redacted(tmp_path: Path) -> None:
    root = stage_dirty_fixtures(tmp_path)
    result = run_scan(root, "--json")

    assert result.returncode == 1, result.stderr
    payload = json.loads(result.stdout)
    assert payload["summary"]["findings"] > 0
    assert payload["findings"]
    for finding in payload["findings"]:
        assert finding["match_redacted"] == "***"
        assert "value" not in finding
    assert "EXAMPLEONLY" not in result.stdout


def test_exclude_removes_a_fixture(tmp_path: Path) -> None:
    root = stage_dirty_fixtures(tmp_path)
    result = run_scan(root, "--exclude", "private_key.txt")

    assert result.returncode == 1, result.stderr
    rule_ids = finding_rule_ids(result.stdout)
    assert "private_key_block" not in rule_ids
    assert "credential_assignment" in rule_ids


def test_path_rule_for_password_material(tmp_path: Path) -> None:
    root = stage_dirty_fixtures(tmp_path)
    result = run_scan(root)

    assert result.returncode == 1
    assert "password_material_file" in finding_rule_ids(result.stdout)


def test_missing_root_is_a_usage_error(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    result = run_scan(missing)

    assert result.returncode == 2
    assert "does not exist" in result.stderr


def test_placeholders_and_documentation_ranges_are_allowed() -> None:
    result = run_scan(FIXTURES / "clean")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "192.0.2" not in result.stdout


def test_max_bytes_skips_large_files(tmp_path: Path) -> None:
    root = tmp_path / "large"
    root.mkdir()
    (root / "large.txt").write_text(
        "app" + "Key=" + "EXAMPLEONLY" + "APPKEY0001\n", encoding="utf-8"
    )
    result = run_scan(root, "--max-bytes", "1")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "size=1" in result.stdout
