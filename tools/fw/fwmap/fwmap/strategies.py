"""Enumeration strategies: WP REST media, sitemap, page index, slug probe."""

from __future__ import annotations

import json
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

from .config import AppConfig, RegionConfig
from .extract import (
    SLUG_RE,
    canonical_file_url,
    classify_page,
    extract_firmware_links,
    extract_page_links,
    filename_from_url,
    parse_package_filename,
    slugify_model,
)
from .fetch import (
    FetchError,
    FwmapError,
    HostNotAllowed,
    PoliteFetcher,
    Response,
    RobotsDenied,
    normalize_url,
    render_html,
)
from .store import Store


@dataclass
class ScanContext:
    config: AppConfig
    region: RegionConfig
    fetcher: PoliteFetcher
    store: Store
    allowed_hosts: frozenset[str]
    render: bool = False
    logger: Any = None
    stats: dict[str, Any] = field(
        default_factory=lambda: {
            "files_new": 0,
            "files_seen": 0,
            "links_observed": 0,
            "pages_fetched": 0,
            "pages_by_classification": {},
            "robots_denied": 0,
            "errors": 0,
            "sitemap_documents": 0,
        }
    )

    def log(self, message: str) -> None:
        if self.logger is not None:
            self.logger(message)

    def bump(self, key: str, amount: int = 1) -> None:
        self.stats[key] = int(self.stats.get(key, 0)) + amount

    def bump_classification(self, classification: str) -> None:
        counts = self.stats.setdefault("pages_by_classification", {})
        counts[classification] = int(counts.get(classification, 0)) + 1


def media_url(region: RegionConfig, page: int) -> str:
    fields = "id,date,slug,source_url,mime_type,media_details"
    query = urllib.parse.urlencode(
        {"per_page": 100, "page": page, "_fields": fields}
    )
    return f"{region.base_url}/wp-json/wp/v2/media?{query}"


def _tier(region: RegionConfig) -> str:
    return "confirmed" if region.evidence_tier == "confirmed" else "hypothesis"


def _store_link(ctx: ScanContext, link: Any, slug: str | None) -> None:
    record = {
        "url": link.url,
        "url_canonical": link.url_canonical,
        "filename": link.filename,
        "model_slug": slug,
        "model_code": link.model_code,
        "package_date": link.package_date,
        "region": ctx.region.name,
        "source_kind": link.source_kind,
        "source_page": link.source_page,
        "evidence_tier": link.evidence_tier,
        "status": "listed",
        "notes": link.notes or None,
    }
    _, created = ctx.store.upsert_file(record)
    ctx.bump("links_observed")
    if created:
        ctx.bump("files_new")
    else:
        ctx.bump("files_seen")


def fetch_document(ctx: ScanContext, url: str, *, html: bool = False) -> Response:
    if html and ctx.render:
        if not ctx.fetcher.can_fetch(url):
            raise RobotsDenied(f"robots.txt disallows {url}")
        body = render_html(url, ctx.allowed_hosts, user_agent=ctx.config.user_agent)
        ctx.fetcher.stats["requests"] += 1
        return Response(url=normalize_url(url), status=200, headers={}, body=body.encode("utf-8"))
    return ctx.fetcher.get(url)


def crawl_model_page(
    ctx: ScanContext,
    url: str,
    slug: str,
    *,
    source_kind: str,
) -> tuple[str, int]:
    """Fetch one model page, extract links, persist page + file rows."""

    try:
        response = fetch_document(ctx, url, html=True)
    except RobotsDenied:
        ctx.bump("robots_denied")
        ctx.store.upsert_page(
            normalize_url(url),
            region=ctx.region.name,
            model_slug=slug,
            source_kind=source_kind,
            evidence_tier=_tier(ctx.region),
            status="robots_denied",
            classification="error",
            note="robots.txt denied the request",
        )
        return "error", 0
    except HostNotAllowed as exc:
        ctx.bump("errors")
        ctx.log(f"skip non-allowlisted page {url}: {exc}")
        return "error", 0
    except FetchError as exc:
        ctx.bump("errors")
        ctx.log(f"fetch failed {url}: {exc}")
        ctx.store.upsert_page(
            normalize_url(url),
            region=ctx.region.name,
            model_slug=slug,
            source_kind=source_kind,
            evidence_tier=_tier(ctx.region),
            status="fetch_error",
            classification="error",
            note=str(exc)[:300],
        )
        return "error", 0

    ctx.bump("pages_fetched")
    body = response.text()
    links = extract_firmware_links(
        body,
        response.url or url,
        media_prefix=ctx.region.media_prefix,
        archive_extensions=ctx.region.archive_extensions,
        source_kind=source_kind,
        source_page=normalize_url(url),
        region_tier=ctx.region.evidence_tier,
    )
    classification = classify_page(response.status, len(links))
    ctx.bump_classification(classification)

    note = "empty page is ambiguous: not evidence that no firmware exists" if classification == "empty" else None
    ctx.store.upsert_page(
        normalize_url(url),
        region=ctx.region.name,
        model_slug=slug,
        source_kind=source_kind,
        evidence_tier=_tier(ctx.region),
        status=f"http:{response.status}",
        http_status=response.status,
        classification=classification,
        note=note,
    )
    if classification in ("listed", "empty"):
        ctx.store.upsert_model(
            slug,
            ctx.region.name,
            model_code=None,
            source=source_kind,
            evidence_tier=_tier(ctx.region) if classification == "listed" else "user_supplied",
            notes=note,
        )
    for link in links:
        _store_link(ctx, link, slug)
    return classification, len(links)


def scan_media(ctx: ScanContext) -> None:
    page = 1
    total_pages = 1
    while page <= min(ctx.config.max_pages, total_pages):
        url = media_url(ctx.region, page)
        try:
            response = ctx.fetcher.get(url)
        except RobotsDenied:
            ctx.bump("robots_denied")
            ctx.log("media strategy skipped: robots.txt denied /wp-json/")
            return
        except FwmapError as exc:
            ctx.bump("errors")
            ctx.log(f"media strategy failed: {exc}")
            return
        if response.status == 404:
            ctx.log("media endpoint returned 404")
            return
        if response.status != 200:
            ctx.bump("errors")
            ctx.log(f"media endpoint returned HTTP {response.status}")
            return
        try:
            items = json.loads(response.text())
        except json.JSONDecodeError as exc:
            ctx.bump("errors")
            ctx.log(f"media endpoint returned invalid JSON: {exc}")
            return
        if not isinstance(items, list):
            ctx.bump("errors")
            ctx.log("media endpoint did not return a JSON list")
            return

        header_total = response.header("X-WP-TotalPages")
        if header_total is not None:
            try:
                total_pages = max(1, int(header_total))
            except ValueError:
                total_pages = page
        elif len(items) >= 100:
            total_pages = page + 1
        else:
            total_pages = page
        ctx.bump("pages_fetched")

        for item in items:
            if not isinstance(item, dict):
                continue
            source_url = item.get("source_url")
            if not isinstance(source_url, str) or not source_url:
                continue
            try:
                canonical = canonical_file_url(source_url)
            except (FwmapError, ValueError):
                continue
            filename = filename_from_url(canonical)
            if not _is_media_firmware(ctx.region, canonical, filename):
                continue
            parsed = parse_package_filename(filename)
            details = item.get("media_details")
            size = None
            if isinstance(details, dict) and isinstance(details.get("filesize"), int):
                size = details["filesize"]
            notes = []
            if item.get("id") is not None:
                notes.append(f"wp_media_id={item['id']}")
            if item.get("date"):
                notes.append(f"wp_date={item['date']}")
            if item.get("slug"):
                notes.append(f"wp_slug={item['slug']}")
            _, created = ctx.store.upsert_file(
                {
                    "url": canonical,
                    "url_canonical": canonical,
                    "filename": filename,
                    "model_slug": None,
                    "model_code": parsed["model_code"],
                    "package_date": parsed["package_date"],
                    "region": ctx.region.name,
                    "source_kind": "media",
                    "source_page": normalize_url(url),
                    "evidence_tier": _tier(ctx.region),
                    "status": "listed",
                    "size": size,
                    "content_type": item.get("mime_type")
                    if isinstance(item.get("mime_type"), str)
                    else None,
                    "notes": "; ".join(notes) or None,
                }
            )
            ctx.bump("links_observed")
            ctx.bump("files_new" if created else "files_seen")
        if page >= total_pages:
            return
        page += 1


def _is_media_firmware(region: RegionConfig, url: str, filename: str) -> bool:
    lowered = filename.lower()
    if not any(lowered.endswith(ext.lower()) for ext in region.archive_extensions):
        return False
    path = urllib.parse.urlsplit(url).path
    return region.media_prefix in path or parse_package_filename(filename)["model_code"] is not None


def _robots_sitemaps(ctx: ScanContext) -> list[str]:
    url = f"{ctx.region.base_url}/robots.txt"
    try:
        response = ctx.fetcher.get(url)
    except FwmapError:
        return []
    if response.status != 200:
        return []
    sitemaps: list[str] = []
    for line in response.text().splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("sitemap:"):
            value = stripped.split(":", 1)[1].strip()
            if value:
                sitemaps.append(value)
    return sitemaps


def _sitemap_page_slug(region: RegionConfig, url: str) -> str | None:
    path = urllib.parse.urlsplit(url).path
    prefix = region.page_prefix.rstrip("/") + "/"
    if not path.startswith(prefix):
        return None
    remainder = path[len(prefix) :].strip("/")
    if not remainder or "/" in remainder or not SLUG_RE.match(remainder):
        return None
    return remainder.lower()


def scan_sitemap(ctx: ScanContext) -> None:
    roots = _robots_sitemaps(ctx)
    roots.extend(
        [
            f"{ctx.region.base_url}/wp-sitemap.xml",
            f"{ctx.region.base_url}/sitemap_index.xml",
        ]
    )
    queue: list[tuple[str, int]] = []
    seen_docs: set[str] = set()
    for root in roots:
        try:
            canonical = normalize_url(urllib.parse.urljoin(ctx.region.base_url, root))
        except (FwmapError, ValueError):
            continue
        if canonical not in seen_docs:
            seen_docs.add(canonical)
            queue.append((canonical, 0))

    page_urls: dict[str, str] = {}
    documents = 0
    while queue and documents < ctx.config.max_pages:
        url, depth = queue.pop(0)
        try:
            response = ctx.fetcher.get(url)
        except RobotsDenied:
            ctx.bump("robots_denied")
            continue
        except FwmapError as exc:
            ctx.bump("errors")
            ctx.log(f"sitemap fetch failed {url}: {exc}")
            continue
        if response.status != 200:
            ctx.log(f"sitemap {url} returned HTTP {response.status}")
            continue
        documents += 1
        ctx.bump("sitemap_documents")
        try:
            tree = ET.fromstring(response.body)
        except ET.ParseError as exc:
            ctx.bump("errors")
            ctx.log(f"sitemap parse failed {url}: {exc}")
            continue
        for element in tree.iter():
            if not element.tag.lower().endswith("loc") or not element.text:
                continue
            value = element.text.strip()
            try:
                loc = normalize_url(urllib.parse.urljoin(url, value))
            except (FwmapError, ValueError):
                continue
            path = urllib.parse.urlsplit(loc).path
            if path.endswith(".xml") and depth < 2 and loc not in seen_docs:
                seen_docs.add(loc)
                queue.append((loc, depth + 1))
                continue
            slug = _sitemap_page_slug(ctx.region, loc)
            if slug is not None:
                page_urls.setdefault(slug, loc)

    if not page_urls:
        ctx.log("sitemap strategy found no model pages")
        return
    for slug, page_url in list(page_urls.items())[: ctx.config.max_pages]:
        ctx.store.upsert_page(
            page_url,
            region=ctx.region.name,
            model_slug=slug,
            source_kind="sitemap",
            evidence_tier=_tier(ctx.region),
            status="from_sitemap",
            classification="discovered",
        )
        if ctx.config.fetch_model_pages:
            crawl_model_page(ctx, page_url, slug, source_kind="sitemap")


def scan_pages(ctx: ScanContext) -> None:
    discovered: dict[str, str] = {}
    for page_number in range(1, ctx.config.max_pages + 1):
        url = ctx.region.index_url(page_number)
        try:
            response = ctx.fetcher.get(url)
        except RobotsDenied:
            ctx.bump("robots_denied")
            ctx.log("page index skipped: robots.txt denied")
            return
        except FwmapError as exc:
            ctx.bump("errors")
            ctx.log(f"page index fetch failed {url}: {exc}")
            break
        if response.status == 404:
            break
        if response.status != 200:
            ctx.bump("errors")
            ctx.log(f"page index {url} returned HTTP {response.status}")
            break
        ctx.bump("pages_fetched")
        body = response.text()
        direct = extract_firmware_links(
            body,
            response.url or url,
            media_prefix=ctx.region.media_prefix,
            archive_extensions=ctx.region.archive_extensions,
            source_kind="pages",
            source_page=normalize_url(url),
            region_tier=ctx.region.evidence_tier,
        )
        for link in direct:
            _store_link(ctx, link, None)

        new_pages = 0
        for slug, page_url in extract_page_links(
            body, response.url or url, page_prefix=ctx.region.page_prefix
        ):
            if slug in discovered:
                continue
            discovered[slug] = page_url
            new_pages += 1
            ctx.store.upsert_page(
                page_url,
                region=ctx.region.name,
                model_slug=slug,
                source_kind="pages",
                evidence_tier=_tier(ctx.region),
                status="discovered",
                classification="discovered",
            )
        if new_pages == 0:
            break

    if not ctx.config.fetch_model_pages:
        return
    for slug, page_url in list(discovered.items())[: ctx.config.max_pages]:
        crawl_model_page(ctx, page_url, slug, source_kind="pages")


def scan_slug(ctx: ScanContext, models: list[str], *, source: str = "cli") -> dict[str, Any]:
    results: dict[str, Any] = {}
    for model in models[: ctx.config.max_pages]:
        slug = slugify_model(model)
        ctx.store.upsert_model(
            slug,
            ctx.region.name,
            model_code=None,
            source=source,
            evidence_tier="user_supplied",
            notes="slug supplied by the user; page evidence only valid after a fetch",
        )
        url = ctx.region.page_url(slug)
        classification, count = crawl_model_page(ctx, url, slug, source_kind="slug")
        results[slug] = {
            "url": normalize_url(url),
            "classification": classification,
            "links": count,
            "evidence_tier": "user_supplied",
        }
    return results


def run_scan(
    ctx: ScanContext,
    strategies: list[str],
    *,
    models: list[str] | None = None,
    models_source: str = "cli",
) -> dict[str, Any]:
    strategy_stats: dict[str, Any] = {}
    for strategy in strategies:
        before_new = int(ctx.stats["files_new"])
        before_links = int(ctx.stats["links_observed"])
        if strategy == "media":
            scan_media(ctx)
        elif strategy == "sitemap":
            scan_sitemap(ctx)
        elif strategy == "pages":
            scan_pages(ctx)
        elif strategy == "slug":
            result = scan_slug(ctx, models or [], source=models_source)
            strategy_stats["slug"] = {
                "models": result,
                "files_new": int(ctx.stats["files_new"]) - before_new,
                "links_observed": int(ctx.stats["links_observed"]) - before_links,
            }
        else:
            raise FwmapError(f"unknown strategy: {strategy}")
        if strategy != "slug":
            strategy_stats.setdefault(strategy, {})
            strategy_stats[strategy].update(
                {
                    "files_new": int(ctx.stats["files_new"]) - before_new,
                    "links_observed": int(ctx.stats["links_observed"]) - before_links,
                }
            )
    ctx.stats["strategies"] = strategy_stats
    return ctx.stats
