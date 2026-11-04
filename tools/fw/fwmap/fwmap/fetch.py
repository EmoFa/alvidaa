"""HTTP transport, allowlist, robots.txt, rate limiting and optional rendering.

Layering
--------
``Transport`` implementations perform a single request and know nothing about
politeness.  ``LocalTransport`` serves offline fixtures; ``UrllibTransport``
speaks HTTP(S) and refuses to run without ``allow_network=True``.
``PoliteFetcher`` wraps either transport and applies the domain allowlist,
robots.txt, rate limiting, retries and redirect checks.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Protocol

DEFAULT_TIMEOUT = 20.0
REDIRECT_LIMIT = 5
STREAM_CHUNK = 64 * 1024


class FwmapError(Exception):
    """Base class for expected fwmap failures."""


class NetworkDisabled(FwmapError):
    """Raised when a network operation was attempted without --allow-network."""


class HostNotAllowed(FwmapError):
    """Raised when a URL points to a host outside the configured allowlist."""


class RobotsDenied(FwmapError):
    """Raised when robots.txt disallows the request."""


class FetchError(FwmapError):
    """Raised for transport failures that do not carry an HTTP status."""


@dataclass(frozen=True)
class Response:
    url: str
    status: int
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""

    def header(self, name: str, default: str | None = None) -> str | None:
        wanted = name.lower()
        for key, value in self.headers.items():
            if key.lower() == wanted:
                return value
        return default

    def text(self, encoding: str | None = None) -> str:
        charset = encoding
        if charset is None:
            content_type = self.header("content-type", "") or ""
            marker = "charset="
            if marker in content_type.lower():
                charset = content_type.lower().split(marker, 1)[1].split(";")[0].strip()
        return self.body.decode(charset or "utf-8", errors="replace")


class Transport(Protocol):
    def request(
        self, url: str, method: str = "GET", headers: Mapping[str, str] | None = None
    ) -> Response: ...


def host_of(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.username or parsed.password:
        raise HostNotAllowed("credentials in URLs are not supported")
    host = (parsed.hostname or "").lower().strip(".")
    if not host:
        raise HostNotAllowed(f"URL has no host: {url!r}")
    return host


def normalize_url(url: str) -> str:
    """Canonical form: lower-case scheme/host, sorted query, no fragment."""

    parsed = urllib.parse.urlsplit(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise FwmapError(f"unsupported URL scheme: {parsed.scheme!r}")
    host = host_of(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise FwmapError(f"invalid port in URL: {url!r}") from exc
    if port in (80, 443):
        port = None
    netloc = host if port is None else f"{host}:{port}"
    path = parsed.path or "/"
    query = urllib.parse.urlencode(
        sorted(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    )
    return urllib.parse.urlunsplit((parsed.scheme.lower(), netloc, path, query, ""))


def check_allowed(url: str, allowed_hosts: frozenset[str]) -> str:
    host = host_of(url)
    if host not in allowed_hosts:
        allowed = ", ".join(sorted(allowed_hosts)) or "none"
        raise HostNotAllowed(f"host {host!r} is not allowlisted (allowed: {allowed})")
    return host


class LocalTransport:
    """Offline transport backed by a fixture directory and ``routes.json``.

    Route keys are normalized URLs.  A route is either
    ``{"status": 200, "headers": {...}, "file": "relative/path"}`` or
    ``{"status": 200, "headers": {...}, "body": "inline text"}``.
    Missing routes raise :class:`FetchError` so fixture gaps stay visible.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        routes_path = self.root / "routes.json"
        try:
            data = json.loads(routes_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise FetchError(f"offline fixture missing {routes_path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise FetchError(f"invalid fixture routes {routes_path}: {exc}") from exc
        if not isinstance(data, dict):
            raise FetchError(f"fixture routes must be a JSON object: {routes_path}")
        self.routes: dict[str, dict] = {
            normalize_url(url): route for url, route in data.items()
        }

    def request(
        self, url: str, method: str = "GET", headers: Mapping[str, str] | None = None
    ) -> Response:
        key = normalize_url(url)
        route = self.routes.get(key)
        if route is None:
            raise FetchError(f"offline fixture has no route for {key}")
        status = int(route.get("status", 200))
        merged_headers = {str(k): str(v) for k, v in (route.get("headers") or {}).items()}
        if "body" in route:
            body = str(route["body"]).encode("utf-8")
        elif "file" in route:
            target = (self.root / str(route["file"])).resolve()
            if not target.is_relative_to(self.root):
                raise FetchError(f"fixture path escapes root: {route['file']!r}")
            try:
                body = target.read_bytes()
            except OSError as exc:
                raise FetchError(f"cannot read fixture {target}: {exc}") from exc
        else:
            body = b""
        if method.upper() == "HEAD":
            body = b""
        return Response(url=key, status=status, headers=merged_headers, body=body)


class _RedirectGuard(urllib.request.HTTPRedirectHandler):
    max_redirections = REDIRECT_LIMIT

    def __init__(self, allowed_hosts: frozenset[str]) -> None:
        super().__init__()
        self.allowed_hosts = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        check_allowed(newurl, self.allowed_hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def build_opener(
    allowed_hosts: frozenset[str], user_agent: str
) -> urllib.request.OpenerDirector:
    opener = urllib.request.build_opener(_RedirectGuard(allowed_hosts))
    opener.addheaders = [
        ("User-Agent", user_agent),
        ("Accept", "text/html,application/json,application/xml;q=0.9,*/*;q=0.8"),
    ]
    # No cookie jar, no auth handler, no proxy credentials.
    return opener


class UrllibTransport:
    """HTTP(S) transport.  Refuses to open a socket without explicit consent."""

    def __init__(
        self,
        allowed_hosts: frozenset[str],
        *,
        allow_network: bool,
        user_agent: str,
        timeout_seconds: float = DEFAULT_TIMEOUT,
        max_body_bytes: int = 20 * 1024 * 1024,
    ) -> None:
        self.allowed_hosts = allowed_hosts
        self.allow_network = allow_network
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.max_body_bytes = max_body_bytes
        self._opener: urllib.request.OpenerDirector | None = None

    @property
    def opener(self) -> urllib.request.OpenerDirector:
        if not self.allow_network:
            raise NetworkDisabled(
                "network access is disabled; pass --allow-network to enable it"
            )
        if self._opener is None:
            self._opener = build_opener(self.allowed_hosts, self.user_agent)
        return self._opener

    def request(
        self, url: str, method: str = "GET", headers: Mapping[str, str] | None = None
    ) -> Response:
        target = normalize_url(url)
        check_allowed(target, self.allowed_hosts)
        request = urllib.request.Request(
            target,
            method=method.upper(),
            headers=dict(headers or {}),
        )
        try:
            with self.opener.open(request, timeout=self.timeout_seconds) as raw:
                final_url = raw.geturl()
                check_allowed(final_url, self.allowed_hosts)
                status = raw.status
                response_headers = dict(raw.headers.items())
                if method.upper() == "HEAD":
                    body = b""
                else:
                    body = raw.read(self.max_body_bytes + 1)
                    if len(body) > self.max_body_bytes:
                        raise FetchError(
                            f"response body exceeds {self.max_body_bytes} bytes: {target}"
                        )
                return Response(final_url, status, response_headers, body)
        except urllib.error.HTTPError as exc:
            body = b"" if method.upper() == "HEAD" else exc.read(self.max_body_bytes)
            return Response(
                exc.geturl() or target, exc.code, dict(exc.headers.items()), body
            )
        except HostNotAllowed:
            raise
        except urllib.error.URLError as exc:
            raise FetchError(f"request failed for {target}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise FetchError(f"request timed out for {target}") from exc


class RobotsCache:
    """Per-origin robots.txt policy using ``urllib.robotparser``."""

    def __init__(self, transport: Transport, user_agent: str) -> None:
        self.transport = transport
        self.user_agent = user_agent
        self._policies: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.statuses: dict[str, int] = {}

    def _origin(self, url: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _policy(self, origin: str) -> urllib.robotparser.RobotFileParser | None:
        if origin in self._policies:
            return self._policies[origin]
        robots_url = f"{origin}/robots.txt"
        policy: urllib.robotparser.RobotFileParser | None
        try:
            response = self.transport.request(robots_url)
            self.statuses[origin] = response.status
        except FwmapError:
            policy = None
        else:
            if 200 <= response.status < 300:
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(response.text().splitlines())
                # ``can_fetch`` treats a zero ``last_checked`` as "not loaded".
                # Set it explicitly so direct parse() use is deterministic.
                parser.last_checked = time.time()
                policy = parser
            else:
                # Standard behaviour: a missing/forbidden robots.txt allows all.
                policy = None
        self._policies[origin] = policy
        return policy

    def can_fetch(self, url: str) -> bool:
        origin = self._origin(url)
        policy = self._policy(origin)
        if policy is None:
            return True
        return policy.can_fetch(self.user_agent, url)


class PoliteFetcher:
    """Allowlist + robots + rate limit + bounded retries around a transport."""

    def __init__(
        self,
        transport: Transport,
        allowed_hosts: frozenset[str],
        *,
        user_agent: str,
        rate_limit_seconds: float = 2.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        honor_robots: bool = True,
    ) -> None:
        self.transport = transport
        self.allowed_hosts = allowed_hosts
        self.user_agent = user_agent
        self.rate_limit_seconds = max(0.0, rate_limit_seconds)
        self.max_retries = max(0, max_retries)
        self.backoff_seconds = max(0.0, backoff_seconds)
        self.robots = RobotsCache(transport, user_agent) if honor_robots else None
        self._last_request = 0.0
        self.stats: dict[str, int] = {
            "requests": 0,
            "robots_denied": 0,
            "retries": 0,
            "errors": 0,
        }

    def _throttle(self) -> None:
        if self.rate_limit_seconds <= 0:
            return
        elapsed = time.monotonic() - self._last_request
        remaining = self.rate_limit_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_request = time.monotonic()

    def can_fetch(self, url: str) -> bool:
        check_allowed(url, self.allowed_hosts)
        if self.robots is None:
            return True
        return self.robots.can_fetch(url)

    def get(
        self,
        url: str,
        method: str = "GET",
        headers: Mapping[str, str] | None = None,
    ) -> Response:
        target = normalize_url(url)
        check_allowed(target, self.allowed_hosts)
        if (
            self.robots is not None
            and not target.endswith("/robots.txt")
            and not self.robots.can_fetch(target)
        ):
            self.stats["robots_denied"] += 1
            raise RobotsDenied(f"robots.txt disallows {target}")

        attempts = self.max_retries + 1
        last_error: FwmapError | None = None
        response: Response | None = None
        for attempt in range(attempts):
            if attempt:
                self.stats["retries"] += 1
                if self.backoff_seconds:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))
            self._throttle()
            self.stats["requests"] += 1
            try:
                response = self.transport.request(target, method=method, headers=headers)
            except HostNotAllowed:
                raise
            except FetchError as exc:
                last_error = exc
                self.stats["errors"] += 1
                continue
            if response.status < 500 and response.status != 429:
                return response
            last_error = FetchError(f"server error {response.status} for {target}")
            self.stats["errors"] += 1
        if last_error is not None:
            raise last_error
        raise FetchError(f"no response for {target}")


def render_html(
    url: str,
    allowed_hosts: frozenset[str],
    *,
    timeout_ms: int = 45_000,
    settle_ms: int = 3_000,
    user_agent: str = "fwmap/0.1 (public firmware metadata crawler)",
) -> str:
    """Render a page with optional Playwright.

    Only the top-level URL is checked against the allowlist; every subresource
    request is also intercepted and aborted unless its host is allowlisted.
    No cookies or credentials are used.
    """

    target = normalize_url(url)
    check_allowed(target, allowed_hosts)
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    except ImportError as exc:
        raise FwmapError(
            "--render requires the optional Playwright extra: "
            "pip install 'fwmap[render]' && python -m playwright install chromium"
        ) from exc

    with sync_playwright() as playwright:  # pragma: no cover - optional extra
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()

            def route_handler(route) -> None:  # noqa: ANN001
                request_url = route.request.url
                if request_url.startswith(("data:", "about:", "blob:")):
                    route.continue_()
                    return
                try:
                    check_allowed(request_url, allowed_hosts)
                except HostNotAllowed:
                    route.abort()
                else:
                    route.continue_()

            page.route("**/*", route_handler)
            page.goto(target, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(settle_ms)
            html = page.content()
            context.close()
        finally:
            browser.close()
    return html


def sanitize_filename(name: str) -> str:
    """Return a safe basename; refuse empty, dot and traversal names."""

    base = os.path.basename(name.replace("\\", "/")).strip()
    if base in ("", ".", "..") or base.startswith("."):
        raise FwmapError(f"refusing unsafe filename: {name!r}")
    if "/" in base or "\x00" in base:
        raise FwmapError(f"refusing unsafe filename: {name!r}")
    return base


def download_to(
    url: str,
    destination: Path,
    allowed_hosts: frozenset[str],
    *,
    allow_network: bool,
    user_agent: str,
    max_bytes: int,
    timeout_seconds: float = DEFAULT_TIMEOUT,
) -> dict[str, object]:
    """Stream a file to ``destination`` with a hard byte cap.

    Returns metadata for the manifest.  The destination is written via a
    ``.part`` file and only renamed on success.
    """

    if not allow_network:
        raise NetworkDisabled("download requires --allow-network")
    target = normalize_url(url)
    check_allowed(target, allowed_hosts)
    destination = Path(destination)
    if not destination.parent.is_dir():
        raise FwmapError(f"output directory does not exist: {destination.parent}")

    opener = build_opener(allowed_hosts, user_agent)
    request = urllib.request.Request(target, method="GET")
    part = destination.with_name(destination.name + ".part")
    digest = hashlib.sha256()
    size = 0
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            check_allowed(response.geturl(), allowed_hosts)
            content_length = response.headers.get("Content-Length")
            if content_length is not None and int(content_length) > max_bytes:
                raise FwmapError(
                    f"remote size {content_length} exceeds --max-bytes {max_bytes}"
                )
            with part.open("wb") as handle:
                while True:
                    chunk = response.read(STREAM_CHUNK)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        raise FwmapError(
                            f"download exceeded --max-bytes {max_bytes}: {target}"
                        )
                    digest.update(chunk)
                    handle.write(chunk)
            metadata = {
                "size": size,
                "sha256": digest.hexdigest(),
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "content_type": response.headers.get("Content-Type"),
                "status": f"http:{response.status}",
            }
        os.replace(part, destination)
        return metadata
    except urllib.error.HTTPError as exc:
        raise FetchError(f"download failed with HTTP {exc.code}: {target}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"download failed for {target}: {exc.reason}") from exc
    finally:
        if part.exists():
            part.unlink(missing_ok=True)
