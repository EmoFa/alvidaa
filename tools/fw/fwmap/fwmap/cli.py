"""Command line interface for fwmap."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sqlite3
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Sequence

from . import __version__
from .config import AppConfig, RegionConfig, VALID_STRATEGIES, load_config
from .extract import parse_package_filename, slugify_model
from .fetch import (
    FwmapError,
    HostNotAllowed,
    LocalTransport,
    NetworkDisabled,
    PoliteFetcher,
    Response,
    RobotsDenied,
    UrllibTransport,
    download_to,
    normalize_url,
    sanitize_filename,
)
from .store import Store, init_db
from .strategies import ScanContext, crawl_model_page, media_url, run_scan

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_GUARD = 2


class UsageError(FwmapError):
    """Invalid command line combination."""


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("fwmap.sqlite"),
        help="SQLite manifest path (default: fwmap.sqlite)",
    )
    parser.add_argument("--config", type=Path, help="optional TOML config overlay")
    parser.add_argument(
        "--offline",
        type=Path,
        metavar="FIXTURE_DIR",
        help="serve all requests from a local fixture directory (no network)",
    )
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="allow live HTTP(S); network is disabled by default",
    )
    parser.add_argument(
        "--allow-host",
        action="append",
        default=[],
        metavar="HOST",
        help="add a host to the allowlist (repeatable)",
    )
    parser.add_argument("--region", default=None, help="configured region name")
    parser.add_argument("--verbose", action="store_true", help="log progress to stderr")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fwmap",
        description=(
            "Catalog publicly linked firmware metadata on configured vendor sites. "
            "Network is off unless --allow-network is given."
        ),
    )
    parser.add_argument("--version", action="version", version=f"fwmap {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create or migrate the SQLite manifest")
    _common(p_init)
    p_init.set_defaults(func=cmd_init)

    p_probe = sub.add_parser("probe", help="probe one model page and classify it")
    _common(p_probe)
    p_probe.add_argument("--slug", help="model page slug, e.g. 100u7q")
    p_probe.add_argument("--model", help="model name; normalized to a slug")
    p_probe.add_argument(
        "--render",
        action="store_true",
        help="render with Playwright (requires the optional render extra)",
    )
    p_probe.set_defaults(func=cmd_probe)

    p_scan = sub.add_parser("scan", help="run one or more enumeration strategies")
    _common(p_scan)
    p_scan.add_argument(
        "--strategy",
        help=(
            "comma-separated subset of media,sitemap,pages,slug "
            "(default: config or all four)"
        ),
    )
    p_scan.add_argument(
        "--model", action="append", default=[], help="model for the slug strategy"
    )
    p_scan.add_argument("--models-file", type=Path, help="file with one model per line")
    p_scan.add_argument(
        "--render",
        action="store_true",
        help="render model pages with Playwright (requires the optional extra)",
    )
    p_scan.set_defaults(func=cmd_scan)

    p_sync = sub.add_parser("sync", help="HEAD/Range metadata for stored files")
    _common(p_sync)
    p_sync.add_argument("--limit", type=int, default=100, help="maximum rows to sync")
    p_sync.set_defaults(func=cmd_sync)

    p_list = sub.add_parser("list", help="list manifest entries")
    _common(p_list)
    p_list.add_argument("--model", help="filter by model code or slug")
    p_list.add_argument("--json", action="store_true", help="emit JSON")
    p_list.set_defaults(func=cmd_list)

    p_download = sub.add_parser("download", help="download one file with a byte cap")
    _common(p_download)
    p_download.add_argument("--id", type=int, required=True, help="file row id")
    p_download.add_argument("--out", type=Path, required=True, help="output directory")
    p_download.add_argument(
        "--max-bytes", type=int, default=2_000_000_000, help="hard download limit"
    )
    p_download.add_argument(
        "--force", action="store_true", help="overwrite an existing output file"
    )
    p_download.set_defaults(func=cmd_download)

    p_verify = sub.add_parser("verify", help="verify a stored record (optionally a file)")
    _common(p_verify)
    p_verify.add_argument("--id", type=int, required=True, help="file row id")
    p_verify.add_argument("--file", type=Path, help="local file to hash and compare")
    p_verify.set_defaults(func=cmd_verify)

    p_export = sub.add_parser("export", help="export the manifest")
    _common(p_export)
    p_export.add_argument("--format", choices=("json", "csv"), required=True)
    p_export.add_argument("--out", type=Path, required=True, help="output path")
    p_export.set_defaults(func=cmd_export)

    p_coverage = sub.add_parser("coverage", help="print the coverage report")
    _common(p_coverage)
    p_coverage.add_argument("--json", action="store_true", help="emit JSON")
    p_coverage.set_defaults(func=cmd_coverage)

    p_doctor = sub.add_parser("doctor", help="show environment and defaults")
    _common(p_doctor)
    p_doctor.set_defaults(func=cmd_doctor)

    return parser


def _load(args: argparse.Namespace) -> tuple[AppConfig, RegionConfig]:
    config = load_config(args.config)
    region = config.region(args.region or "es")
    return config, region


def _hosts(config: AppConfig, region: RegionConfig, args: argparse.Namespace) -> frozenset[str]:
    return config.allowed_hosts(region, tuple(args.allow_host))


def _make_fetcher(
    config: AppConfig,
    region: RegionConfig,
    args: argparse.Namespace,
) -> PoliteFetcher:
    hosts = _hosts(config, region, args)
    if args.offline is not None:
        if not args.offline.is_dir():
            raise UsageError(f"--offline directory not found: {args.offline}")
        if args.render:
            raise UsageError("--render cannot be combined with --offline")
        transport = LocalTransport(args.offline)
        return PoliteFetcher(
            transport,
            hosts,
            user_agent=config.user_agent,
            rate_limit_seconds=0.0,
            max_retries=0,
            backoff_seconds=0.0,
        )
    if not args.allow_network:
        raise NetworkDisabled(
            "network access is disabled; pass --allow-network for a live run "
            "or --offline FIXTURE_DIR"
        )
    transport = UrllibTransport(
        hosts,
        allow_network=True,
        user_agent=config.user_agent,
        timeout_seconds=config.timeout_seconds,
        max_body_bytes=config.max_body_bytes,
    )
    return PoliteFetcher(
        transport,
        hosts,
        user_agent=config.user_agent,
        rate_limit_seconds=config.rate_limit_seconds,
        max_retries=config.max_retries,
    )


def _logger(args: argparse.Namespace) -> Callable[[str], None] | None:
    if not args.verbose:
        return None
    return lambda message: print(f"[fwmap] {message}", file=sys.stderr)


def _read_models(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise UsageError(f"cannot read models file {path}: {exc}") from exc
    models: list[str] = []
    for raw in lines:
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        token = re.split(r"[,\s]+", line)[0]
        if token and token not in models:
            models.append(token)
    return models


def _parse_strategies(value: str | None, config: AppConfig) -> list[str]:
    if value is None:
        return list(config.enabled_strategies)
    items: list[str] = []
    for part in value.split(","):
        name = part.strip()
        if name and name not in items:
            items.append(name)
    unknown = [name for name in items if name not in VALID_STRATEGIES]
    if unknown:
        raise UsageError(
            f"unknown strategies: {', '.join(unknown)} "
            f"(valid: {', '.join(VALID_STRATEGIES)})"
        )
    if not items:
        raise UsageError("no strategies selected")
    return items


def cmd_init(args: argparse.Namespace) -> int:
    path = init_db(args.db)
    print(json.dumps({"db": str(path), "status": "initialized"}, indent=2))
    return EXIT_OK


def cmd_probe(args: argparse.Namespace) -> int:
    if bool(args.slug) == bool(args.model):
        raise UsageError("probe needs exactly one of --slug or --model")
    config, region = _load(args)
    fetcher = _make_fetcher(config, region, args)
    slug = (args.slug or args.model or "").strip().lower()
    if args.model and not args.slug:
        slug = slugify_model(args.model)
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", slug):
        raise UsageError(f"invalid slug: {slug!r}")

    with Store(args.db) as store:
        run_id = store.start_run(
            command="probe",
            region=region.name,
            strategies=["slug"],
            fetcher="offline" if args.offline else "network",
            allow_network=bool(args.allow_network and not args.offline),
        )
        ctx = ScanContext(
            config=config,
            region=region,
            fetcher=fetcher,
            store=store,
            allowed_hosts=_hosts(config, region, args),
            render=args.render,
            logger=_logger(args),
        )
        classification, link_count = crawl_model_page(
            ctx, region.page_url(slug), slug, source_kind="slug"
        )
        ctx.stats["fetcher"] = dict(fetcher.stats)
        store.finish_run(run_id, ctx.stats)

        page_url = normalize_url(region.page_url(slug))
        page = store.get_page(page_url) or {}
        files = store.files_for_source_page(page_url)
        coverage = store.coverage(limit_runs=0)
        result = {
            "region": region.name,
            "slug": slug,
            "url": page_url,
            "classification": classification,
            "http_status": page.get("http_status"),
            "firmware_links": [
                {
                    "url": row["url_canonical"],
                    "filename": row["filename"],
                    "model_code": row["model_code"],
                    "package_date": row["package_date"],
                    "evidence_tier": row["evidence_tier"],
                }
                for row in files
            ],
            "link_count": link_count,
            "evidence_tier": "user_supplied",
            "filename_pattern_proven": coverage["filename_pattern_proven"],
            "render": bool(args.render),
            "note": (
                "empty is ambiguous: the page may be unlisted, template-broken, "
                "geo/UA filtered, or rendered after the wait window"
                if classification == "empty"
                else None
            ),
            "stats": ctx.stats,
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return EXIT_OK


def cmd_scan(args: argparse.Namespace) -> int:
    config, region = _load(args)
    strategies = _parse_strategies(args.strategy, config)
    models: list[str] = []
    for model in args.model:
        if model not in models:
            models.append(model)
    if args.models_file is not None:
        for model in _read_models(args.models_file):
            if model not in models:
                models.append(model)
    if "slug" in strategies and not models:
        if args.strategy is not None:
            raise UsageError("slug strategy needs --model or --models-file")
        strategies = [name for name in strategies if name != "slug"]

    fetcher = _make_fetcher(config, region, args)
    with Store(args.db) as store:
        run_id = store.start_run(
            command="scan",
            region=region.name,
            strategies=strategies,
            fetcher="offline" if args.offline else "network",
            allow_network=bool(args.allow_network and not args.offline),
        )
        ctx = ScanContext(
            config=config,
            region=region,
            fetcher=fetcher,
            store=store,
            allowed_hosts=_hosts(config, region, args),
            render=args.render,
            logger=_logger(args),
        )
        try:
            stats = run_scan(
                ctx,
                strategies,
                models=models,
                models_source="models_file" if args.models_file else "cli",
            )
            stats["fetcher"] = dict(fetcher.stats)
            stats["requests"] = fetcher.stats["requests"]
        finally:
            store.finish_run(run_id, ctx.stats)
        coverage = store.coverage(limit_runs=1)
        summary = {
            "region": region.name,
            "strategies": strategies,
            "stats": stats,
            "files_total": coverage["files_total"],
            "filename_pattern_proven": coverage["filename_pattern_proven"],
            "pages_by_classification": coverage["pages_by_classification"],
            "db": str(args.db),
        }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return EXIT_OK


def _content_length(response: Response) -> int | None:
    raw = response.header("Content-Length")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _total_from_content_range(response: Response) -> int | None:
    raw = response.header("Content-Range")
    if not raw or "/" not in raw:
        return None
    try:
        return int(raw.rsplit("/", 1)[1])
    except ValueError:
        return None


def cmd_sync(args: argparse.Namespace) -> int:
    config, region = _load(args)
    fetcher = _make_fetcher(config, region, args)
    synced = 0
    errors: list[dict[str, Any]] = []
    with Store(args.db) as store:
        rows = store.files_for_sync(args.limit)
        for row in rows:
            try:
                response = fetcher.get(row["url"], method="HEAD")
                if response.status in (405, 501) or response.status >= 400:
                    response = fetcher.get(
                        row["url"], headers={"Range": "bytes=0-0"}
                    )
            except RobotsDenied as exc:
                errors.append({"url": row["url"], "error": f"robots: {exc}"})
                continue
            except FwmapError as exc:
                errors.append({"url": row["url"], "error": str(exc)})
                continue
            if response.status >= 400:
                errors.append(
                    {"url": row["url"], "error": f"HTTP {response.status}"}
                )
                continue
            size = _content_length(response) or _total_from_content_range(response)
            store.update_file(
                int(row["id"]),
                {
                    "status": f"http:{response.status}",
                    "size": size,
                    "etag": response.header("ETag"),
                    "last_modified": response.header("Last-Modified"),
                    "content_type": response.header("Content-Type"),
                },
            )
            synced += 1
    print(
        json.dumps(
            {
                "synced": synced,
                "errors": errors,
                "fetcher": fetcher.stats,
                "db": str(args.db),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return EXIT_OK


def cmd_list(args: argparse.Namespace) -> int:
    with Store(args.db) as store:
        rows = store.list_files(model=args.model, region=args.region)
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return EXIT_OK
    if not rows:
        print("no entries")
        return EXIT_OK
    columns = ("id", "region", "filename", "model_code", "package_date", "size", "evidence_tier")
    print("\t".join(columns))
    for row in rows:
        print("\t".join("-" if row.get(column) is None else str(row[column]) for column in columns))
    return EXIT_OK


def _region_for_row(config: AppConfig, row: dict[str, Any], fallback: RegionConfig) -> RegionConfig:
    name = row.get("region")
    if isinstance(name, str) and name in config.regions:
        return config.regions[name]
    return fallback


def cmd_download(args: argparse.Namespace) -> int:
    if args.offline is not None:
        raise UsageError("download does not support --offline; it writes remote bytes")
    config, fallback_region = _load(args)
    with Store(args.db) as store:
        row = store.get_file(args.id)
        if row is None:
            raise FwmapError(f"no file with id {args.id}")
        region = _region_for_row(config, row, fallback_region)
        hosts = config.allowed_hosts(region, tuple(args.allow_host))
        filename = row.get("filename") or urllib.parse.unquote(
            urllib.parse.urlsplit(row["url_canonical"]).path.rsplit("/", 1)[-1]
        )
        safe_name = sanitize_filename(str(filename))
        if not args.out.is_dir():
            raise FwmapError(f"output directory does not exist: {args.out}")
        destination = args.out / safe_name
        if destination.exists() and not args.force:
            raise FwmapError(f"refusing to overwrite {destination} (use --force)")
        metadata = download_to(
            row["url_canonical"],
            destination,
            hosts,
            allow_network=bool(args.allow_network),
            user_agent=config.user_agent,
            max_bytes=args.max_bytes,
            timeout_seconds=config.timeout_seconds,
        )
        store.update_file(args.id, metadata)
    print(
        json.dumps(
            {
                "id": args.id,
                "path": str(destination),
                **metadata,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return EXIT_OK


def _hash_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cmd_verify(args: argparse.Namespace) -> int:
    config, fallback_region = _load(args)
    checks: list[dict[str, Any]] = []
    with Store(args.db) as store:
        row = store.get_file(args.id)
        if row is None:
            raise FwmapError(f"no file with id {args.id}")
        region = _region_for_row(config, row, fallback_region)
        hosts = config.allowed_hosts(region, tuple(args.allow_host))

        def check(name: str, ok: bool, detail: str) -> None:
            checks.append({"name": name, "ok": ok, "detail": detail})

        canonical = row["url_canonical"]
        try:
            check("canonical_url", normalize_url(canonical) == canonical, canonical)
        except FwmapError as exc:
            check("canonical_url", False, str(exc))

        expected_name = urllib.parse.unquote(
            urllib.parse.urlsplit(canonical).path.rsplit("/", 1)[-1]
        )
        check(
            "filename_matches_url",
            not row["filename"] or row["filename"] == expected_name,
            f"stored={row['filename']!r} url={expected_name!r}",
        )
        parsed = parse_package_filename(row["filename"] or "")
        check(
            "model_code_matches_filename",
            row["model_code"] is None or row["model_code"] == parsed["model_code"],
            f"stored={row['model_code']!r} parsed={parsed['model_code']!r}",
        )
        check(
            "package_date_matches_filename",
            row["package_date"] is None or row["package_date"] == parsed["package_date"],
            f"stored={row['package_date']!r} parsed={parsed['package_date']!r}",
        )
        check(
            "evidence_tier",
            row["evidence_tier"] in ("confirmed", "hypothesis", "user_supplied"),
            str(row["evidence_tier"]),
        )
        try:
            host = urllib.parse.urlsplit(canonical).hostname or ""
            check("host_allowlisted", host in hosts, host)
        except ValueError as exc:
            check("host_allowlisted", False, str(exc))
        check(
            "sha256_format",
            row["sha256"] is None or re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is not None,
            str(row["sha256"]),
        )

        if args.file is not None:
            exists = args.file.is_file()
            check("local_file_exists", exists, str(args.file))
            if exists:
                digest = _hash_file(args.file)
                check(
                    "local_file_sha256",
                    row["sha256"] is None or digest == row["sha256"],
                    digest,
                )
                if row["size"] is not None:
                    check(
                        "local_file_size",
                        args.file.stat().st_size == row["size"],
                        f"{args.file.stat().st_size} vs {row['size']}",
                    )
        else:
            check("local_file", True, "not provided; metadata-only verification")

    status = "ok" if all(item["ok"] for item in checks) else "failed"
    print(
        json.dumps(
            {"id": args.id, "status": status, "checks": checks},
            indent=2,
            sort_keys=True,
        )
    )
    return EXIT_OK if status == "ok" else EXIT_ERROR


def cmd_export(args: argparse.Namespace) -> int:
    with Store(args.db) as store:
        if args.format == "json":
            path = store.export_json(args.out)
        else:
            path = store.export_csv(args.out)
    print(json.dumps({"exported": str(path), "format": args.format}, indent=2))
    return EXIT_OK


def cmd_coverage(args: argparse.Namespace) -> int:
    with Store(args.db) as store:
        coverage = store.coverage()
    if args.json:
        print(json.dumps(coverage, indent=2, sort_keys=True))
        return EXIT_OK
    print(f"files: {coverage['files_total']}  pages: {coverage['pages_total']}  models: {coverage['models_total']}")
    print(f"with size: {coverage['files_with_size']}  with sha256: {coverage['files_with_sha256']}")
    print(f"evidence tiers: {coverage['files_by_evidence_tier']}")
    print(f"page classes: {coverage['pages_by_classification']}")
    print(
        "filename pattern proven: "
        f"{coverage['filename_pattern_proven']} "
        f"({coverage['filename_pattern_confirmed_files']} confirmed files)"
    )
    if coverage["filename_pattern_example"]:
        print(f"example: {coverage['filename_pattern_example']}")
    print(coverage["disclaimer"])
    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    report = {
        "fwmap_version": __version__,
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "playwright_available": importlib.util.find_spec("playwright") is not None,
        "network_default": "disabled (requires --allow-network)",
        "robots": "honored via urllib.robotparser",
        "offline": "LocalTransport via --offline FIXTURE_DIR",
        "regions": {
            name: {
                "host": region.host,
                "page_prefix": region.page_prefix,
                "evidence_tier": region.evidence_tier,
            }
            for name, region in sorted(config.regions.items())
        },
        "rate_limit_seconds": config.rate_limit_seconds,
        "max_retries": config.max_retries,
        "max_pages": config.max_pages,
        "media_endpoint_example": media_url(config.region("es"), 1) if "es" in config.regions else None,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except UsageError as exc:
        print(f"fwmap: {exc}", file=sys.stderr)
        return EXIT_GUARD
    except NetworkDisabled as exc:
        print(f"fwmap: {exc}", file=sys.stderr)
        return EXIT_GUARD
    except (HostNotAllowed, RobotsDenied) as exc:
        print(f"fwmap: {exc}", file=sys.stderr)
        return EXIT_GUARD
    except (FwmapError, ValueError, OSError, sqlite3.Error) as exc:
        print(f"fwmap: error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
