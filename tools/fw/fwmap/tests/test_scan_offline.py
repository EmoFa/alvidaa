from __future__ import annotations

import json
import socket
from pathlib import Path

from fwmap.cli import main
from fwmap.store import Store


def run_scan(db: Path, fixtures: Path, *extra: str) -> int:
    return main(
        [
            "scan",
            "--db",
            str(db),
            "--offline",
            str(fixtures),
            "--region",
            "es",
            "--strategy",
            "media,sitemap,pages,slug",
            "--model",
            "m7000",
            *extra,
        ]
    )


def test_scan_offline_end_to_end(tmp_path: Path, site_fixtures: Path, monkeypatch) -> None:
    def no_socket(*args, **kwargs):
        raise AssertionError("offline scan must not open a socket")

    monkeypatch.setattr(socket, "socket", no_socket)
    db = tmp_path / "manifest.sqlite"
    exit_code = run_scan(db, site_fixtures)
    assert exit_code == 0

    with Store(db) as store:
        files = store.list_files()
        assert len(files) == 4
        assert {row["filename"] for row in files} == {
            "100u65qevs_pkg_20250101.tar.gz",
            "m7000_pkg_20231212.tar.gz",
            "m7000_pkg_20240115.tar.gz",
            "55a6g_pkg_20240202.zip",
        }
        coverage = store.coverage()
        assert coverage["files_total"] == 4
        # Offline fixtures demonstrate the parser, not the real vendor site.
        assert coverage["filename_pattern_proven"] is False
        assert coverage["filename_pattern_evidence"] == "offline_or_unverified"
        assert coverage["filename_pattern_matching_files"] == 4
        assert coverage["filename_pattern_confirmed_files"] == 0
        assert coverage["pages_by_classification"] == {
            "empty": 1,
            "listed": 1,
            "not_found": 1,
        }
        assert coverage["models_total"] == 2
        assert coverage["files_by_evidence_tier"] == {"confirmed": 4}


def test_scan_offline_summary_json(
    tmp_path: Path, site_fixtures: Path, capsys
) -> None:
    db = tmp_path / "manifest.sqlite"
    assert run_scan(db, site_fixtures) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["files_total"] == 4
    assert payload["filename_pattern_proven"] is False
    assert payload["stats"]["fetcher"]["requests"] > 0


def test_list_and_coverage_json(tmp_path: Path, site_fixtures: Path, capsys) -> None:
    db = tmp_path / "manifest.sqlite"
    assert run_scan(db, site_fixtures) == 0
    capsys.readouterr()

    assert main(["list", "--db", str(db), "--model", "m7000", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 2
    assert all(row["model_code"] == "M7000" for row in rows)

    assert main(["coverage", "--db", str(db), "--json"]) == 0
    coverage = json.loads(capsys.readouterr().out)
    assert coverage["files_total"] == 4
    assert coverage["regions"][0]["region"] == "es"


def test_export_json_is_valid(tmp_path: Path, site_fixtures: Path) -> None:
    db = tmp_path / "manifest.sqlite"
    out = tmp_path / "export.json"
    assert run_scan(db, site_fixtures) == 0
    assert main(["export", "--db", str(db), "--format", "json", "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(payload["files"]) == 4
    assert payload["coverage"]["files_total"] == 4
    assert payload["models"]


def test_export_csv_has_header(tmp_path: Path, site_fixtures: Path) -> None:
    db = tmp_path / "manifest.sqlite"
    out = tmp_path / "export.csv"
    assert run_scan(db, site_fixtures) == 0
    assert main(["export", "--db", str(db), "--format", "csv", "--out", str(out)]) == 0
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("id,url,url_canonical,filename")
    assert len(lines) == 5


def test_probe_empty_page_is_ambiguous(tmp_path: Path, site_fixtures: Path, capsys) -> None:
    db = tmp_path / "manifest.sqlite"
    assert (
        main(
            [
                "probe",
                "--db",
                str(db),
                "--offline",
                str(site_fixtures),
                "--slug",
                "100u7q",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["classification"] == "empty"
    assert payload["link_count"] == 0
    assert payload["note"]


def test_probe_listed_page(tmp_path: Path, site_fixtures: Path, capsys) -> None:
    db = tmp_path / "manifest.sqlite"
    assert (
        main(
            [
                "probe",
                "--db",
                str(db),
                "--offline",
                str(site_fixtures),
                "--slug",
                "m7000",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["classification"] == "listed"
    assert payload["link_count"] == 2
    assert {link["filename"] for link in payload["firmware_links"]} == {
        "m7000_pkg_20231212.tar.gz",
        "m7000_pkg_20240115.tar.gz",
    }


def test_verify_metadata_record(tmp_path: Path, site_fixtures: Path, capsys) -> None:
    db = tmp_path / "manifest.sqlite"
    assert run_scan(db, site_fixtures) == 0
    capsys.readouterr()
    with Store(db) as store:
        file_id = store.list_files()[0]["id"]
    assert main(["verify", "--db", str(db), "--id", str(file_id)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["checks"]
