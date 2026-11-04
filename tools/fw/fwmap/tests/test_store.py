from __future__ import annotations

from pathlib import Path

from fwmap.store import Store


def record(**overrides):
    data = {
        "url": "https://www.hisense.es/wp-content/uploads/firmwares/m7000_pkg_20240115.tar.gz",
        "url_canonical": "https://www.hisense.es/wp-content/uploads/firmwares/m7000_pkg_20240115.tar.gz",
        "filename": "m7000_pkg_20240115.tar.gz",
        "model_slug": "m7000",
        "model_code": "M7000",
        "package_date": "2024-01-15",
        "region": "es",
        "source_kind": "slug",
        "source_page": "https://www.hisense.es/descargas-firmware/m7000/",
        "evidence_tier": "confirmed",
        "status": "listed",
        "notes": None,
    }
    data.update(overrides)
    return data


def test_dedupe_by_canonical_url(tmp_path: Path) -> None:
    with Store(tmp_path / "m.sqlite") as store:
        first_id, created = store.upsert_file(record())
        assert created is True
        second_id, created = store.upsert_file(record())
        assert created is False
        assert first_id == second_id
        rows = store.list_files()
        assert len(rows) == 1
        assert rows[0]["first_seen"] is not None
        assert rows[0]["last_seen"] is not None


def test_dedupe_by_filename_and_region(tmp_path: Path) -> None:
    with Store(tmp_path / "m.sqlite") as store:
        first_id, _ = store.upsert_file(record())
        other_url = (
            "https://www.hisense.es/wp-content/uploads/firmwares/"
            "m7000_pkg_20240115.tar.gz"
        ).replace("www.", "cdn.")
        second_id, created = store.upsert_file(
            record(url=other_url, url_canonical=other_url)
        )
        assert created is False
        assert first_id == second_id
        rows = store.list_files()
        assert len(rows) == 1
        assert "duplicate_url=" in (rows[0]["notes"] or "")


def test_update_file_overwrites_metadata(tmp_path: Path) -> None:
    with Store(tmp_path / "m.sqlite") as store:
        file_id, _ = store.upsert_file(record())
        store.update_file(file_id, {"size": 42, "etag": '"abc"'})
        row = store.get_file(file_id)
        assert row is not None
        assert row["size"] == 42
        assert row["etag"] == '"abc"'


def test_coverage_counts(tmp_path: Path) -> None:
    with Store(tmp_path / "m.sqlite") as store:
        store.upsert_file(record())
        store.upsert_file(
            record(
                url="https://www.hisense.es/wp-content/uploads/firmwares/55a6g_pkg_20240202.zip",
                url_canonical="https://www.hisense.es/wp-content/uploads/firmwares/55a6g_pkg_20240202.zip",
                filename="55a6g_pkg_20240202.zip",
                model_code="55A6G",
                package_date="2024-02-02",
                model_slug=None,
                evidence_tier="hypothesis",
            )
        )
        store.upsert_page(
            "https://www.hisense.es/descargas-firmware/m7000/",
            region="es",
            source_kind="slug",
            evidence_tier="confirmed",
            classification="listed",
        )
        coverage = store.coverage()
        assert coverage["files_total"] == 2
        assert coverage["pages_total"] == 1
        assert coverage["files_by_evidence_tier"] == {"confirmed": 1, "hypothesis": 1}
        assert coverage["pages_by_classification"] == {"listed": 1}
        assert coverage["filename_pattern_proven"] is False
        assert coverage["filename_pattern_evidence"] == "offline_or_unverified"
        assert coverage["filename_pattern_matching_files"] == 1

        # A recorded live run (allow_network=1) is required to call the pattern
        # proven about the real site.
        store.start_run(
            command="scan",
            region="es",
            strategies=("slug",),
            fetcher="network",
            allow_network=True,
        )
        live = store.coverage()
        assert live["filename_pattern_proven"] is True
        assert live["filename_pattern_evidence"] == "live_run"
        assert live["filename_pattern_confirmed_files"] == 1
        assert coverage["files_with_size"] == 0
