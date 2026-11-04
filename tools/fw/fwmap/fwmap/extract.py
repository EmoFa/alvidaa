"""HTML/JSON link extraction and filename parsing."""

from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from typing import Iterable, Iterator

from .fetch import FwmapError, normalize_url

PACKAGE_RE = re.compile(
    r"^(?P<code>[A-Za-z0-9][A-Za-z0-9-]*)_pkg_(?P<date>\d{8})(?:\.[A-Za-z0-9.]+)?$"
)
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SCRIPT_URL_RE = re.compile(
    r"""(?:https?://[^\s"'<>()\\]+|/[^\s"'<>()\\]+|[\w][\w./-]*\.(?:tar\.gz|tgz|zip|bin|pkg|7z|rar))""",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FirmwareLink:
    url: str
    url_canonical: str
    filename: str
    model_code: str | None
    package_date: str | None
    evidence_tier: str
    source_kind: str
    source_page: str
    notes: str = ""


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: list[str] = []
        self.scripts: list[tuple[str, str]] = []
        self._in_script = False
        self._script_type = ""
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if not value:
                continue
            lowered = name.lower()
            if lowered in ("href", "src") or lowered.startswith("data-"):
                self.values.append(value)
        if tag.lower() == "script":
            attributes = {name.lower(): (value or "") for name, value in attrs}
            self._script_type = attributes.get("type", "")
            self._in_script = True
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._in_script:
            self.scripts.append((self._script_type, "".join(self._buffer)))
            self._in_script = False


def _json_strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _json_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _json_strings(item)


def parse_package_filename(filename: str) -> dict[str, str | None]:
    """Parse ``<MODEL>_pkg_<YYYYMMDD>.<ext>``.

    This pattern is a HYPOTHESIS until a live run observes it; parsing only
    records what is present in the filename, it never fills in missing values.
    """

    match = PACKAGE_RE.match(filename)
    if not match:
        return {"model_code": None, "package_date": None}
    raw_date = match.group("date")
    try:
        date = datetime.strptime(raw_date, "%Y%m%d").date().isoformat()
    except ValueError:
        date = None
    return {"model_code": match.group("code").upper(), "package_date": date}


def is_archive_filename(filename: str, extensions: Iterable[str]) -> bool:
    lowered = filename.lower()
    return any(lowered.endswith(ext.lower()) for ext in extensions)


def filename_from_url(url: str) -> str:
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    return path.rsplit("/", 1)[-1]


def canonical_file_url(url: str) -> str:
    """Canonical URL for file identity: no fragment, no query."""

    normalized = normalize_url(url)
    parsed = urllib.parse.urlsplit(normalized)
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, "", "")
    )


def is_firmware_url(
    url: str,
    *,
    media_prefix: str,
    archive_extensions: Iterable[str],
) -> bool:
    """True for an archive under the media prefix or matching the package pattern."""

    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    path = urllib.parse.unquote(parsed.path)
    filename = path.rsplit("/", 1)[-1]
    if not is_archive_filename(filename, archive_extensions):
        return False
    if media_prefix in path:
        return True
    return PACKAGE_RE.match(filename) is not None


def _candidate_strings(html: str) -> list[str]:
    collector = _Collector()
    try:
        collector.feed(html)
        collector.close()
    except Exception:  # html.parser is lenient; keep whatever was collected
        pass

    candidates = list(collector.values)
    for script_type, body in collector.scripts:
        if "ld+json" in script_type.lower():
            try:
                candidates.extend(_json_strings(json.loads(body)))
            except json.JSONDecodeError:
                pass
        candidates.extend(match.group(0) for match in SCRIPT_URL_RE.finditer(body))
    return candidates


def extract_firmware_links(
    html: str,
    base_url: str,
    *,
    media_prefix: str,
    archive_extensions: Iterable[str],
    source_kind: str,
    source_page: str,
    region_tier: str,
) -> list[FirmwareLink]:
    """Extract, canonicalize and deduplicate firmware links from one document.

    ``evidence_tier`` is ``confirmed`` when the link was observed in a fetched
    response on a region whose structure is itself artifact-backed, otherwise
    ``hypothesis`` (observed on an unverified regional site).
    """

    extensions = tuple(archive_extensions)
    tier = "confirmed" if region_tier == "confirmed" else "hypothesis"
    seen: set[str] = set()
    links: list[FirmwareLink] = []
    for raw in _candidate_strings(html):
        value = raw.strip()
        if not value or value.lower().startswith(("javascript:", "mailto:", "data:")):
            continue
        absolute = urllib.parse.urljoin(base_url, value)
        try:
            canonical = canonical_file_url(absolute)
        except (FwmapError, ValueError):
            continue
        if canonical in seen:
            continue
        if not is_firmware_url(
            canonical, media_prefix=media_prefix, archive_extensions=extensions
        ):
            continue
        seen.add(canonical)
        filename = filename_from_url(canonical)
        parsed = parse_package_filename(filename)
        notes = ""
        if tier == "hypothesis":
            notes = "region structure is unverified; link observed but not artifact-backed"
        links.append(
            FirmwareLink(
                url=canonical,
                url_canonical=canonical,
                filename=filename,
                model_code=parsed["model_code"],
                package_date=parsed["package_date"],
                evidence_tier=tier,
                source_kind=source_kind,
                source_page=source_page,
                notes=notes,
            )
        )
    return links


def extract_page_links(
    html: str, base_url: str, *, page_prefix: str
) -> list[tuple[str, str]]:
    """Return ``(slug, canonical_page_url)`` pairs from anchors/data attributes."""

    collector = _Collector()
    try:
        collector.feed(html)
        collector.close()
    except Exception:
        pass

    prefix = page_prefix.rstrip("/") + "/"
    seen: set[str] = set()
    pages: list[tuple[str, str]] = []
    for value in collector.values:
        if value.lower().startswith(("javascript:", "mailto:", "data:")):
            continue
        absolute = urllib.parse.urljoin(base_url, value.strip())
        try:
            canonical = normalize_url(absolute)
        except (FwmapError, ValueError):
            continue
        path = urllib.parse.urlsplit(canonical).path
        if not path.startswith(prefix):
            continue
        remainder = path[len(prefix) :].strip("/")
        if not remainder or "/" in remainder:
            continue
        if not SLUG_RE.match(remainder):
            continue
        slug = remainder.lower()
        if slug in seen:
            continue
        seen.add(slug)
        page_parts = urllib.parse.urlsplit(canonical)
        page_url = urllib.parse.urlunsplit(
            (page_parts.scheme, page_parts.netloc, page_parts.path, "", "")
        )
        if not page_url.endswith("/"):
            page_url += "/"
        pages.append((slug, page_url))
    return pages


def slugify_model(value: str) -> str:
    """Normalize a model name to a conservative URL slug (never invents digits)."""

    candidate = value.strip().lower().replace("_", "-").replace(" ", "-")
    candidate = re.sub(r"[^a-z0-9.-]+", "-", candidate).strip("-")
    if not candidate or not SLUG_RE.match(candidate):
        raise FwmapError(f"cannot derive a safe slug from model {value!r}")
    return candidate


def classify_page(status: int, link_count: int) -> str:
    if status == 200:
        return "listed" if link_count > 0 else "empty"
    if status == 404:
        return "not_found"
    return "error"
