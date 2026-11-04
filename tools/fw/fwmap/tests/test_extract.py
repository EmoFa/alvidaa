from __future__ import annotations

from pathlib import Path

import pytest

from fwmap.config import default_config
from fwmap.extract import (
    canonical_file_url,
    extract_firmware_links,
    extract_page_links,
    parse_package_filename,
    slugify_model,
)
from fwmap.fetch import FwmapError

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_package_filename() -> None:
    parsed = parse_package_filename("100u65qevs_pkg_20250101.tar.gz")
    assert parsed == {"model_code": "100U65QEVS", "package_date": "2025-01-01"}

    assert parse_package_filename("100u65qevs.tar.gz") == {
        "model_code": None,
        "package_date": None,
    }
    # invalid calendar date must not be invented
    assert parse_package_filename("m7000_pkg_20241340.tar.gz") == {
        "model_code": "M7000",
        "package_date": None,
    }


def test_canonical_file_url_drops_query_and_fragment() -> None:
    assert (
        canonical_file_url(
            "HTTPS://WWW.HISENSE.ES/wp-content/uploads/firmwares/a_pkg_20240101.tar.gz?x=1#frag"
        )
        == "https://www.hisense.es/wp-content/uploads/firmwares/a_pkg_20240101.tar.gz"
    )


def test_extract_firmware_links_from_html() -> None:
    html = (FIXTURES / "site" / "page_m7000.html").read_text(encoding="utf-8")
    region = default_config().region("es")
    links = extract_firmware_links(
        html,
        region.page_url("m7000"),
        media_prefix=region.media_prefix,
        archive_extensions=region.archive_extensions,
        source_kind="slug",
        source_page=region.page_url("m7000"),
        region_tier=region.evidence_tier,
    )
    assert [link.filename for link in links] == [
        "m7000_pkg_20231212.tar.gz",
        "m7000_pkg_20240115.tar.gz",
    ]
    assert all(link.evidence_tier == "confirmed" for link in links)
    assert all(link.model_code == "M7000" for link in links)


def test_extract_ignores_non_firmware_links() -> None:
    html = """
    <a href="/wp-content/uploads/2024/01/m7000.jpg">preview</a>
    <a href="/descargas-firmware/m7000/">model page</a>
    <div data-url="/about/">about</div>
    """
    region = default_config().region("es")
    links = extract_firmware_links(
        html,
        region.page_url("m7000"),
        media_prefix=region.media_prefix,
        archive_extensions=region.archive_extensions,
        source_kind="pages",
        source_page=region.index_url(),
        region_tier=region.evidence_tier,
    )
    assert links == []


def test_extract_page_links() -> None:
    html = (FIXTURES / "site" / "page_index.html").read_text(encoding="utf-8")
    region = default_config().region("es")
    pages = extract_page_links(html, region.index_url(), page_prefix=region.page_prefix)
    assert [slug for slug, _ in pages] == ["m7000", "100u7q", "does-not-exist"]


def test_slugify_model() -> None:
    assert slugify_model("100U7Q") == "100u7q"
    assert slugify_model(" M7000 ") == "m7000"
    with pytest.raises(FwmapError):
        slugify_model("///")
