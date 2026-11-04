from __future__ import annotations

import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def site_fixtures() -> Path:
    return FIXTURES / "site"


@pytest.fixture()
def robots_deny_fixtures() -> Path:
    return FIXTURES / "robots_deny"


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "manifest.sqlite"
