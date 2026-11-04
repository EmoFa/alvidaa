"""Configuration model and TOML overlay loader."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

DEFAULT_USER_AGENT = "fwmap/0.1 (public firmware metadata crawler)"
DEFAULT_ARCHIVE_EXTENSIONS: tuple[str, ...] = (
    ".tar.gz",
    ".tgz",
    ".tar",
    ".zip",
    ".bin",
    ".pkg",
    ".7z",
    ".rar",
)
VALID_EVIDENCE_TIERS = frozenset({"confirmed", "hypothesis", "user_supplied"})
VALID_STRATEGIES = ("media", "sitemap", "pages", "slug")


@dataclass(frozen=True)
class RegionConfig:
    """One public regional site and the path conventions used for it.

    ``evidence_tier`` describes the *site structure* (page route, media layout),
    not an individual downloaded file. Link-level tiers are assigned at
    extraction time; see :mod:`fwmap.extract`.
    """

    name: str
    host: str
    hosts: tuple[str, ...]
    # Model pages use the plural route on hisense.es; the download index uses
    # the singular route. Keep them separate instead of guessing one prefix.
    page_prefix: str = "/descargas-firmware"
    index_prefix: str = "/descarga-firmware"
    media_prefix: str = "/wp-content/uploads/firmwares/"
    archive_extensions: tuple[str, ...] = DEFAULT_ARCHIVE_EXTENSIONS
    evidence_tier: str = "hypothesis"

    def __post_init__(self) -> None:
        if not self.hosts:
            raise ValueError(f"region {self.name!r} has no hosts")
        if self.host not in self.hosts:
            object.__setattr__(self, "hosts", (self.host, *self.hosts))
        if self.evidence_tier not in VALID_EVIDENCE_TIERS:
            raise ValueError(
                f"region {self.name!r}: invalid evidence_tier {self.evidence_tier!r}"
            )
        if not self.page_prefix.startswith("/"):
            raise ValueError(f"region {self.name!r}: page_prefix must start with '/'")
        if not self.index_prefix.startswith("/"):
            raise ValueError(f"region {self.name!r}: index_prefix must start with '/'")
        if not self.media_prefix.startswith("/"):
            raise ValueError(f"region {self.name!r}: media_prefix must start with '/'")
        object.__setattr__(self, "page_prefix", self.page_prefix.rstrip("/"))
        object.__setattr__(self, "index_prefix", self.index_prefix.rstrip("/"))
        object.__setattr__(self, "media_prefix", self.media_prefix.rstrip("/") + "/")

    @property
    def base_url(self) -> str:
        return f"https://{self.host}"

    def page_url(self, slug: str) -> str:
        return f"{self.base_url}{self.page_prefix}/{slug}/"

    def index_url(self, page: int = 1) -> str:
        if page <= 1:
            return f"{self.base_url}{self.index_prefix}/"
        return f"{self.base_url}{self.index_prefix}/page/{page}/"


@dataclass(frozen=True)
class AppConfig:
    regions: dict[str, RegionConfig] = field(default_factory=dict)
    allow_hosts: tuple[str, ...] = ()
    rate_limit_seconds: float = 2.0
    timeout_seconds: float = 20.0
    max_retries: int = 3
    max_pages: int = 20
    max_body_bytes: int = 20 * 1024 * 1024
    user_agent: str = DEFAULT_USER_AGENT
    enabled_strategies: tuple[str, ...] = VALID_STRATEGIES
    fetch_model_pages: bool = True

    def region(self, name: str) -> RegionConfig:
        try:
            return self.regions[name]
        except KeyError as exc:
            known = ", ".join(sorted(self.regions)) or "none"
            raise ValueError(f"unknown region {name!r} (configured: {known})") from exc

    def allowed_hosts(
        self, region: RegionConfig, extra: tuple[str, ...] = ()
    ) -> frozenset[str]:
        hosts = set(region.hosts) | set(self.allow_hosts) | set(extra)
        return frozenset(host.lower().strip(".") for host in hosts if host)

    def with_region(self, region: RegionConfig) -> "AppConfig":
        regions = dict(self.regions)
        regions[region.name] = region
        return replace(self, regions=regions)


def default_config() -> AppConfig:
    """Built-in defaults.

    Only the Spanish site has artifact-backed evidence for the page route
    (HTTP 200 for ``/descargas-firmware/100u7q/``). Every other convention is a
    hypothesis and must be enabled explicitly in a config file.
    """

    es = RegionConfig(
        name="es",
        host="www.hisense.es",
        hosts=("www.hisense.es", "hisense.es"),
        page_prefix="/descargas-firmware",
        index_prefix="/descarga-firmware",
        media_prefix="/wp-content/uploads/firmwares/",
        evidence_tier="confirmed",
    )
    return AppConfig(regions={"es": es})


def _as_str_tuple(value: Any, key: str) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)) and all(
        isinstance(item, str) for item in value
    ):
        return tuple(value)
    raise ValueError(f"config key {key!r} must be a string or a list of strings")


def _apply_table(config: AppConfig, data: dict[str, Any]) -> AppConfig:
    general = data.get("general", {})
    if not isinstance(general, dict):
        raise ValueError("config table [general] must be a table")

    updates: dict[str, Any] = {}
    if "allow_hosts" in general:
        updates["allow_hosts"] = _as_str_tuple(
            general["allow_hosts"], "general.allow_hosts"
        )
    for key in (
        "rate_limit_seconds",
        "timeout_seconds",
        "max_retries",
        "max_pages",
        "max_body_bytes",
    ):
        if key in general:
            value = general[key]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"config key general.{key} must be a number")
            updates[key] = getattr(config, key).__class__(value)
    if "user_agent" in general:
        if not isinstance(general["user_agent"], str):
            raise ValueError("config key general.user_agent must be a string")
        updates["user_agent"] = general["user_agent"]
    if "enabled_strategies" in general:
        strategies = _as_str_tuple(
            general["enabled_strategies"], "general.enabled_strategies"
        )
        unknown = set(strategies) - set(VALID_STRATEGIES)
        if unknown:
            raise ValueError(f"unknown strategies in config: {sorted(unknown)}")
        updates["enabled_strategies"] = strategies
    if "fetch_model_pages" in general:
        if not isinstance(general["fetch_model_pages"], bool):
            raise ValueError("config key general.fetch_model_pages must be a boolean")
        updates["fetch_model_pages"] = general["fetch_model_pages"]
    if updates:
        config = replace(config, **updates)

    regions = data.get("regions", {})
    if not isinstance(regions, dict):
        raise ValueError("config table [regions] must be a table")
    merged = dict(config.regions)
    for name, table in regions.items():
        if not isinstance(table, dict):
            raise ValueError(f"config table [regions.{name}] must be a table")
        base = merged.get(name)
        hosts = _as_str_tuple(
            table.get("hosts", base.hosts if base else ()), f"regions.{name}.hosts"
        )
        host = table.get("host", base.host if base else (hosts[0] if hosts else ""))
        if not isinstance(host, str) or not host:
            raise ValueError(f"region {name!r} needs a non-empty host")
        extensions = table.get("archive_extensions")
        region = RegionConfig(
            name=name,
            host=host,
            hosts=hosts if host in hosts else (host, *hosts),
            page_prefix=str(
                table.get(
                    "page_prefix", base.page_prefix if base else "/descargas-firmware"
                )
            ),
            index_prefix=str(
                table.get(
                    "index_prefix", base.index_prefix if base else "/descarga-firmware"
                )
            ),
            media_prefix=str(
                table.get(
                    "media_prefix",
                    base.media_prefix if base else "/wp-content/uploads/firmwares/",
                )
            ),
            archive_extensions=(
                _as_str_tuple(extensions, f"regions.{name}.archive_extensions")
                if extensions is not None
                else (base.archive_extensions if base else DEFAULT_ARCHIVE_EXTENSIONS)
            ),
            evidence_tier=str(
                table.get("evidence_tier", base.evidence_tier if base else "hypothesis")
            ),
        )
        merged[name] = region
    return replace(config, regions=merged)


def load_config(path: Path | None = None) -> AppConfig:
    """Load built-in defaults and overlay an optional TOML file."""

    config = default_config()
    if path is None:
        return config
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read config file {path}: {exc}") from exc
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid TOML config {path}: {exc}") from exc
    return _apply_table(config, data)
