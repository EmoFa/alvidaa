from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from fwmap.cli import main
from fwmap.config import default_config
from fwmap.fetch import (
    HostNotAllowed,
    LocalTransport,
    NetworkDisabled,
    PoliteFetcher,
    RobotsDenied,
    UrllibTransport,
)
from fwmap.strategies import media_url


def test_network_disabled_by_default(tmp_path: Path, monkeypatch) -> None:
    def no_socket(*args, **kwargs):
        raise AssertionError("socket must not be created")

    monkeypatch.setattr(socket, "socket", no_socket)
    db = tmp_path / "manifest.sqlite"
    exit_code = main(["scan", "--db", str(db), "--strategy", "pages"])
    assert exit_code == 2


def test_probe_requires_network_flag(tmp_path: Path) -> None:
    db = tmp_path / "manifest.sqlite"
    assert main(["probe", "--db", str(db), "--slug", "100u7q"]) == 2


def test_urllib_transport_refuses_without_consent() -> None:
    transport = UrllibTransport(
        frozenset({"www.hisense.es"}),
        allow_network=False,
        user_agent="fwmap-test",
    )
    with pytest.raises(NetworkDisabled):
        transport.request("https://www.hisense.es/robots.txt")


def test_robots_denial(robots_deny_fixtures: Path) -> None:
    region = default_config().region("es")
    transport = LocalTransport(robots_deny_fixtures)
    fetcher = PoliteFetcher(
        transport,
        frozenset({"www.hisense.es"}),
        user_agent="fwmap-test",
        rate_limit_seconds=0,
        max_retries=0,
    )
    with pytest.raises(RobotsDenied):
        fetcher.get(media_url(region, 1))
    assert fetcher.get(region.index_url()).status == 200
    assert fetcher.stats["robots_denied"] == 1


def test_host_allowlist(robots_deny_fixtures: Path) -> None:
    transport = LocalTransport(robots_deny_fixtures)
    fetcher = PoliteFetcher(
        transport,
        frozenset({"www.hisense.es"}),
        user_agent="fwmap-test",
        rate_limit_seconds=0,
        max_retries=0,
    )
    with pytest.raises(HostNotAllowed):
        fetcher.get("https://evil.example/firmware.tar.gz")


def test_scan_media_robots_denied_is_reported(
    tmp_path: Path, robots_deny_fixtures: Path, capsys
) -> None:
    db = tmp_path / "manifest.sqlite"
    exit_code = main(
        [
            "scan",
            "--db",
            str(db),
            "--offline",
            str(robots_deny_fixtures),
            "--strategy",
            "media",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stats"]["robots_denied"] == 1
    assert payload["files_total"] == 0


def test_render_rejected_offline(tmp_path: Path, site_fixtures: Path) -> None:
    db = tmp_path / "manifest.sqlite"
    exit_code = main(
        [
            "probe",
            "--db",
            str(db),
            "--offline",
            str(site_fixtures),
            "--render",
            "--slug",
            "m7000",
        ]
    )
    assert exit_code == 2


def test_download_rejected_offline(tmp_path: Path, site_fixtures: Path) -> None:
    db = tmp_path / "manifest.sqlite"
    exit_code = main(
        [
            "download",
            "--db",
            str(db),
            "--offline",
            str(site_fixtures),
            "--id",
            "1",
            "--out",
            str(tmp_path),
        ]
    )
    assert exit_code == 2


def test_unknown_strategy_rejected(tmp_path: Path, site_fixtures: Path) -> None:
    db = tmp_path / "manifest.sqlite"
    exit_code = main(
        [
            "scan",
            "--db",
            str(db),
            "--offline",
            str(site_fixtures),
            "--strategy",
            "bogus",
        ]
    )
    assert exit_code == 2
