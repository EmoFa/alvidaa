# fwmap — public firmware metadata catalog

`fwmap` builds a **metadata catalog** of firmware files that are publicly
linked on configured vendor sites. It stores URLs, filenames, regions, dates
and optional HTTP metadata in SQLite, and emits JSON/CSV plus a coverage
report.

It does **not** bundle, mirror or redistribute firmware. It never logs in,
never sends cookies or auth headers, and network access is off unless you pass
`--allow-network`.

---

## Evidence tiers (read this first)

Every stored file carries an `evidence_tier`:

| Tier | Meaning |
|---|---|
| `confirmed` | The URL was extracted from a response `fwmap` fetched itself, on a region whose page structure is artifact-backed. |
| `hypothesis` | The URL was observed on a regional site whose structure is **not** artifact-backed, or the value was derived from an unverified convention. |
| `user_supplied` | The model slug / identifier came from the user (`--model`, models file), not from a site observation. |

Important consequences:

- **Artifact-backed:** the model-page route
  `https://www.hisense.es/descargas-firmware/<slug>/` (HTTP 200 for `100u7q`
  and for `m7000`), the singular download index `/descarga-firmware/`, and the
  file pattern
  `https://www.hisense.es/wp-content/uploads/firmwares/<MODEL>_pkg_<YYYYMMDD>.tar.gz`
  (observed for `HE55M7000UWTSG_pkg_20181127.tar.gz` and
  `HE65M7000UWTSG_pkg_20190123.tar.gz` in a preserved prior-run transcript).
- **UNVERIFIED_HYPOTHESIS:** `/wp-json/wp/v2/media`, `wp-sitemap.xml`,
  robots.txt, pagination, and every other region. The tool probes them, but
  does not claim they exist.
- `100u7q` returned HTTP 200 with a **0-byte body**; the rendered DOM is the
  39-byte empty skeleton. A page that returns HTTP 200 with no links is
  classified `empty`. `empty` is **ambiguous**: it can mean "not listed",
  "template broken", "geo/UA filtered" or "content hydrated after the wait
  window". It is never reported as "no firmware exists".
- `coverage.filename_pattern_proven` becomes `true` only after a **live** run
  (`--allow-network`) extracted a matching URL. An offline fixture run is
  labeled `filename_pattern_evidence = offline_or_unverified`, so synthetic
  tests cannot masquerade as evidence about the real site.

---

## Install

Python 3.11+ and the standard library are enough for the core tool.

```sh
cd tools/fwmap
python -m pip install -e .
# or run without installing:
python -m fwmap --help
```

Optional rendering (`--render`) uses Playwright:

```sh
python -m pip install -e '.[render]'
python -m playwright install chromium
```

Tests only need pytest and never touch the network:

```sh
python -m pip install pytest
python -m pytest
```

---

## Quickstart (offline, no network)

```sh
cd tools/fwmap
python -m fwmap init --db catalog.sqlite

# Use the synthetic fixtures shipped with the tests:
python -m fwmap scan --db catalog.sqlite \
  --offline tests/fixtures/site \
  --region es --strategy media,sitemap,pages,slug --model m7000

python -m fwmap list --db catalog.sqlite --json
python -m fwmap coverage --db catalog.sqlite
python -m fwmap export --db catalog.sqlite --format json --out catalog.json
```

## Quickstart (live, explicit opt-in)

```sh
cd tools/fwmap
python -m fwmap scan --db catalog.sqlite --allow-network --region es \
  --strategy sitemap,pages,slug --model 100u7q

# Render a JavaScript-heavy page (optional extra):
python -m fwmap probe --db catalog.sqlite --allow-network --region es \
  --slug 100u7q --render

# HEAD/Range metadata for stored files (size, ETag, Last-Modified):
python -m fwmap sync --db catalog.sqlite --allow-network --limit 50
```

`--allow-network` is required for every live operation. Without it the tool
prints a clear error and exits with code `2` before opening a socket.
`--offline FIXTURE_DIR` always wins and performs zero network requests.

---

## Commands

| Command | Purpose |
|---|---|
| `fwmap init --db PATH` | Create the SQLite schema (WAL). |
| `fwmap probe --region es --slug 100u7q [--render]` | Fetch one model page, classify it (`empty`, `listed`, `not_found`, `error`) and store extracted links. |
| `fwmap scan --region es [--strategy media,sitemap,pages,slug] [--model X] [--models-file F] [--db PATH]` | Run enumeration strategies. |
| `fwmap sync --db PATH [--limit N]` | HEAD (fallback `GET Range: bytes=0-0`) for size/ETag/Last-Modified/content-type. |
| `fwmap list [--model X] [--region es] [--json]` | List manifest rows. |
| `fwmap download --db PATH --id ID --out DIR [--max-bytes N]` | Stream one file, enforce a hard byte cap, compute SHA-256. Refuses non-allowlisted hosts. |
| `fwmap verify --db PATH --id ID [--file PATH]` | Check record invariants; optionally hash a local file. |
| `fwmap export --db PATH --format json\|csv --out PATH` | Export the manifest. |
| `fwmap coverage --db PATH [--json]` | Coverage report, including whether the filename pattern is proven. |
| `fwmap doctor` | Environment, optional extras and configured regions. |

Common options: `--db`, `--config`, `--offline`, `--allow-network`,
`--allow-host`, `--region`, `--verbose`.

Exit codes: `0` success, `1` operational error, `2` guard/usage error
(network disabled, host not allowlisted, robots denial, bad flags).

---

## Strategies

1. **media** — `/wp-json/wp/v2/media?per_page=100&page=N&_fields=...`
   (hypothesis). Filters for the configured media prefix and archive
   extensions. Paginates up to `max_pages`, using `X-WP-TotalPages` when
   present.
2. **sitemap** — reads `Sitemap:` lines from robots.txt, then
   `/wp-sitemap.xml` and `/sitemap_index.xml`; recurses at most 2 levels and
   collects `/descargas-firmware/<slug>/` pages.
3. **pages** — walks the singular download index `index_prefix`
   (`/descarga-firmware/`, then `/descarga-firmware/page/N/`) up to
   `max_pages`, extracting model links. The model pages themselves stay on the
   plural `page_prefix` (`/descargas-firmware/<slug>/`).
4. **slug** — probes `<page_prefix>/<slug>/` for each `--model` / models-file
   entry and classifies the response. If the default strategy set is used
   without models, `slug` is skipped; an explicit `--strategy ...,slug`
   without models is a usage error.

HTML extraction covers `<a href>`, `data-*` attributes, JSON-LD script blocks
and inline JavaScript string literals. File URLs are canonicalized (lower-case
host, no fragment, query dropped for file identity) and deduplicated by
canonical URL and by `(filename, region)`.

---

## Data model

SQLite (WAL) with four tables:

- `files` — `id, url, url_canonical, filename, model_slug, model_code,
  package_date, region, source_kind, source_page, evidence_tier, first_seen,
  last_seen, status, size, etag, last_modified, content_type, sha256, notes`.
  `url_canonical` is unique; a partial unique index also enforces
  `(filename, region)`.
- `pages` — every model page seen, with HTTP status and classification
  (`discovered`, `listed`, `empty`, `not_found`, `error`).
- `models` — model slug per region, with its provenance and tier.
- `runs` — command, strategies, fetcher kind, allow-network flag and stats.

Missing fields stay `NULL`. `model_code` and `package_date` are only filled
when the filename itself contains the `<MODEL>_pkg_<YYYYMMDD>` pattern. A slug
is never silently treated as a model code. `package_date` is the packaging date
encoded in the filename, not a build or release date.

Dedupe: the same canonical URL updates `last_seen`; the same
`(filename, region)` under a different URL keeps one row and records
`duplicate_url=...` in `notes`.

---

## Coverage semantics

`fwmap coverage` reports:

- files/pages/models total, by region, by evidence tier and by source kind;
- rows with known size / SHA-256;
- page classifications (`empty`, `listed`, `not_found`, `error`);
- `filename_pattern_proven` plus the number of confirmed matching files;
- the last runs with their stats and the fetcher request/robots counters.

A **"full map"** can only mean: *all publicly linked firmware files observed
on the configured public sites at crawl time*. It does **not** mean all
firmware that exists. OTA/service-only images, factory images, internally
distributed builds, deleted files without tombstones and paid/unofficial
mirrors are out of scope. Regions whose structure has not been verified stay
`hypothesis`.

---

## Network guard and politeness

- Scheme must be `http`/`https`; host must be in the region hosts or
  `--allow-host` / `general.allow_hosts`.
- Redirects are checked hop by hop; a redirect to a non-allowlisted host is
  refused.
- robots.txt is fetched per origin and honored with
  `urllib.robotparser`. A 4xx/unreachable robots.txt follows the standard
  "allow all" rule.
- Default rate: 1 request / 2 s (`general.rate_limit_seconds`), bounded
  exponential backoff, max 3 retries, finite page caps and timeouts.
- No cookies, no auth headers, no login flows, no credential handling.
- `--render` aborts every subresource whose host is not allowlisted. It uses a
  fresh browser context with no stored cookies.

---

## Adding a region

Copy the pattern in `config.example.toml` / `examples/regions.toml`:

```toml
[regions.pt]
host = "www.hisense.pt"
hosts = ["www.hisense.pt", "hisense.pt"]
page_prefix = "/descargas-firmware"   # model pages
index_prefix = "/descarga-firmware"    # download index
media_prefix = "/wp-content/uploads/firmwares/"
evidence_tier = "hypothesis"           # until a live observation proves it
```

Then `fwmap scan --config config.toml --region pt ...`. Only add hosts you are
authorized to query. The built-in default contains only `es`.

---

## Offline mode

`--offline DIR` uses a `LocalTransport` that reads `routes.json` plus fixture
files and performs **zero** network calls. Route keys are normalized URLs:

```json
{
  "https://www.hisense.es/robots.txt": {"status": 200, "file": "robots.txt"},
  "https://www.hisense.es/descargas-firmware/m7000/": {
    "status": 200,
    "file": "page_m7000.html",
    "headers": {"Content-Type": "text/html"}
  }
}
```

An unlisted route raises a visible fixture error instead of pretending to be a
404. The bundled fixtures cover a two-page WP media response, a sitemap index
with child sitemaps, a populated model page with two links, an empty model
page, a 404 page and a robots-denial case.

---

## Limitations

- Coverage is not completeness. Empty pages are ambiguous.
- `model_slug` is unknown for media-only discoveries; a media filename is not
  proof that the model page slug equals the model code.
- Query strings are dropped for file identity, so URLs that genuinely require a
  token cannot be reproduced as separate entries.
- Hash and exact version require a download; `sync` only reads headers.
- `--render` executes page JavaScript from the allowlisted site. It is optional
  and off by default. It cannot see content blocked by geo/IP or served after
  the settle window.
- The default config intentionally contains only `es`; other regions are
  hypotheses.
- `verify` without `--file` is a metadata consistency check, not a proof that
  the remote bytes are unchanged.

---

## Legal / responsible use

- Metadata only. This repository ships **no firmware** and does not mirror
  vendor binaries.
- Respect the target site's terms, robots.txt and applicable law. Use a
  conservative rate limit.
- Do not use this tool to bypass authentication, paywalls, geo-blocking or
  access controls. It has no login support by design.
- Vendor and model names are used descriptively; no affiliation is implied.
