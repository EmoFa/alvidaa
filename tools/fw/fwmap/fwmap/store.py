"""SQLite manifest: schema, dedupe, exports and coverage report."""

from __future__ import annotations

import csv
import json
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .extract import PACKAGE_RE, is_archive_filename

SCHEMA_VERSION = 1

FILE_FIELDS = (
    "id",
    "url",
    "url_canonical",
    "filename",
    "model_slug",
    "model_code",
    "package_date",
    "region",
    "source_kind",
    "source_page",
    "evidence_tier",
    "first_seen",
    "last_seen",
    "status",
    "size",
    "etag",
    "last_modified",
    "content_type",
    "sha256",
    "notes",
)

METADATA_FIELDS = (
    "model_slug",
    "model_code",
    "package_date",
    "source_page",
    "size",
    "etag",
    "last_modified",
    "content_type",
    "sha256",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    url_canonical TEXT NOT NULL UNIQUE,
    filename TEXT,
    model_slug TEXT,
    model_code TEXT,
    package_date TEXT,
    region TEXT,
    source_kind TEXT,
    source_page TEXT,
    evidence_tier TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    status TEXT,
    size INTEGER,
    etag TEXT,
    last_modified TEXT,
    content_type TEXT,
    sha256 TEXT,
    notes TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_files_filename_region
    ON files(filename, region)
    WHERE filename IS NOT NULL AND region IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_files_model_code ON files(model_code);
CREATE INDEX IF NOT EXISTS ix_files_region ON files(region);

CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    url_canonical TEXT NOT NULL UNIQUE,
    model_slug TEXT,
    region TEXT,
    source_kind TEXT,
    status TEXT,
    http_status INTEGER,
    classification TEXT,
    evidence_tier TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    note TEXT
);
CREATE INDEX IF NOT EXISTS ix_pages_region ON pages(region);
CREATE INDEX IF NOT EXISTS ix_pages_class ON pages(classification);

CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL,
    region TEXT NOT NULL,
    model_code TEXT,
    source TEXT,
    evidence_tier TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    notes TEXT,
    UNIQUE(slug, region)
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    command TEXT NOT NULL,
    region TEXT,
    strategies TEXT,
    fetcher TEXT,
    allow_network INTEGER,
    stats_json TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db(path: Path) -> Path:
    path = Path(path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _merge_notes(existing: str | None, addition: str | None) -> str | None:
    if not addition:
        return existing
    if not existing:
        return addition
    if addition in existing.split("; "):
        return existing
    return f"{existing}; {addition}"


class Store:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        init_db(self.path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    # -- files ---------------------------------------------------------

    def upsert_file(self, record: dict[str, Any]) -> tuple[int, bool]:
        """Insert or merge a file row.

        Dedupe is by canonical URL first, then by ``(filename, region)``.  A
        second URL for the same file is recorded in ``notes`` instead of
        creating a duplicate row.
        """

        now = utcnow()
        canonical = record["url_canonical"]
        row = self.conn.execute(
            "SELECT * FROM files WHERE url_canonical = ?", (canonical,)
        ).fetchone()
        created = False
        if row is None:
            filename = record.get("filename")
            region = record.get("region")
            if filename and region:
                row = self.conn.execute(
                    "SELECT * FROM files WHERE filename = ? AND region = ?",
                    (filename, region),
                ).fetchone()
                if row is not None:
                    record = dict(record)
                    record["notes"] = _merge_notes(
                        record.get("notes"), f"duplicate_url={canonical}"
                    )

        if row is None:
            columns = [
                "url",
                "url_canonical",
                "filename",
                "model_slug",
                "model_code",
                "package_date",
                "region",
                "source_kind",
                "source_page",
                "evidence_tier",
                "first_seen",
                "last_seen",
                "status",
                "size",
                "etag",
                "last_modified",
                "content_type",
                "sha256",
                "notes",
            ]
            values = [
                record.get("url") or canonical,
                canonical,
                record.get("filename"),
                record.get("model_slug"),
                record.get("model_code"),
                record.get("package_date"),
                record.get("region"),
                record.get("source_kind"),
                record.get("source_page"),
                record.get("evidence_tier") or "hypothesis",
                now,
                now,
                record.get("status"),
                record.get("size"),
                record.get("etag"),
                record.get("last_modified"),
                record.get("content_type"),
                record.get("sha256"),
                record.get("notes"),
            ]
            cursor = self.conn.execute(
                f"INSERT INTO files ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                values,
            )
            self.conn.commit()
            return int(cursor.lastrowid), True

        updates: dict[str, Any] = {"last_seen": now}
        for field in METADATA_FIELDS:
            if record.get(field) is not None and row[field] is None:
                updates[field] = record[field]
        if record.get("status") is not None:
            updates["status"] = record["status"]
        if record.get("notes"):
            updates["notes"] = _merge_notes(row["notes"], record["notes"])
        if row["evidence_tier"] != "confirmed" and record.get("evidence_tier") == "confirmed":
            updates["evidence_tier"] = "confirmed"
        assignments = ", ".join(f"{field} = ?" for field in updates)
        self.conn.execute(
            f"UPDATE files SET {assignments} WHERE id = ?",
            [*updates.values(), row["id"]],
        )
        self.conn.commit()
        return int(row["id"]), created

    def get_file(self, file_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        return dict(row) if row else None

    def list_files(
        self, *, model: str | None = None, region: str | None = None
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if model:
            clauses.append(
                "(lower(model_code) = lower(?) OR lower(model_slug) = lower(?))"
            )
            params.extend([model, model])
        if region:
            clauses.append("region = ?")
            params.append(region)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM files {where} ORDER BY lower(filename), region", params
        ).fetchall()
        return [dict(row) for row in rows]

    def files_for_sync(self, limit: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT * FROM files
            WHERE size IS NULL OR etag IS NULL OR last_modified IS NULL
            ORDER BY id LIMIT ?
            """,
            (max(0, limit),),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_page(self, url: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM pages WHERE url_canonical = ?", (url,)
        ).fetchone()
        return dict(row) if row else None

    def files_for_source_page(self, url: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM files WHERE source_page = ? ORDER BY lower(filename)", (url,)
        ).fetchall()
        return [dict(row) for row in rows]

    # -- pages / models / runs ----------------------------------------

    def update_file(self, file_id: int, fields: dict[str, Any]) -> None:
        """Overwrite selected metadata columns for an existing file row."""

        allowed = {
            "status",
            "size",
            "etag",
            "last_modified",
            "content_type",
            "sha256",
            "notes",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"cannot update unknown file fields: {sorted(unknown)}")
        if not fields:
            return
        updates = dict(fields)
        updates["last_seen"] = utcnow()
        assignments = ", ".join(f"{field} = ?" for field in updates)
        self.conn.execute(
            f"UPDATE files SET {assignments} WHERE id = ?",
            [*updates.values(), file_id],
        )
        self.conn.commit()

    def upsert_page(
        self,
        url: str,
        *,
        region: str,
        source_kind: str,
        evidence_tier: str,
        model_slug: str | None = None,
        status: str | None = None,
        http_status: int | None = None,
        classification: str | None = None,
        note: str | None = None,
    ) -> int:
        canonical = url
        now = utcnow()
        row = self.conn.execute(
            "SELECT * FROM pages WHERE url_canonical = ?", (canonical,)
        ).fetchone()
        if row is None:
            cursor = self.conn.execute(
                """
                INSERT INTO pages (url, url_canonical, model_slug, region, source_kind,
                    status, http_status, classification, evidence_tier, first_seen, last_seen, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    url,
                    canonical,
                    model_slug,
                    region,
                    source_kind,
                    status,
                    http_status,
                    classification,
                    evidence_tier,
                    now,
                    now,
                    note,
                ),
            )
            self.conn.commit()
            return int(cursor.lastrowid)
        updates: dict[str, Any] = {"last_seen": now}
        for field, value in (
            ("model_slug", model_slug),
            ("status", status),
            ("http_status", http_status),
            ("classification", classification),
        ):
            if value is not None:
                updates[field] = value
        if note:
            updates["note"] = _merge_notes(row["note"], note)
        assignments = ", ".join(f"{field} = ?" for field in updates)
        self.conn.execute(
            f"UPDATE pages SET {assignments} WHERE id = ?",
            [*updates.values(), row["id"]],
        )
        self.conn.commit()
        return int(row["id"])

    def upsert_model(
        self,
        slug: str,
        region: str,
        *,
        model_code: str | None,
        source: str,
        evidence_tier: str,
        notes: str | None = None,
    ) -> int:
        now = utcnow()
        row = self.conn.execute(
            "SELECT * FROM models WHERE slug = ? AND region = ?", (slug, region)
        ).fetchone()
        if row is None:
            cursor = self.conn.execute(
                """
                INSERT INTO models (slug, region, model_code, source, evidence_tier,
                    first_seen, last_seen, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (slug, region, model_code, source, evidence_tier, now, now, notes),
            )
            self.conn.commit()
            return int(cursor.lastrowid)
        self.conn.execute(
            """
            UPDATE models SET last_seen = ?,
                model_code = COALESCE(model_code, ?),
                evidence_tier = CASE
                    WHEN evidence_tier = 'confirmed' THEN evidence_tier
                    ELSE ? END,
                notes = ?
            WHERE id = ?
            """,
            (
                now,
                model_code,
                evidence_tier,
                _merge_notes(row["notes"], notes),
                row["id"],
            ),
        )
        self.conn.commit()
        return int(row["id"])

    def start_run(
        self,
        *,
        command: str,
        region: str | None,
        strategies: Iterable[str],
        fetcher: str,
        allow_network: bool,
    ) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO runs (started_at, command, region, strategies, fetcher, allow_network)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                utcnow(),
                command,
                region,
                ",".join(strategies),
                fetcher,
                1 if allow_network else 0,
            ),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def finish_run(self, run_id: int, stats: dict[str, Any], notes: str = "") -> None:
        self.conn.execute(
            "UPDATE runs SET finished_at = ?, stats_json = ?, notes = ? WHERE id = ?",
            (utcnow(), json.dumps(stats, sort_keys=True), notes, run_id),
        )
        self.conn.commit()

    # -- reporting -----------------------------------------------------

    def _counts(self, table: str, column: str) -> dict[str, int]:
        rows = self.conn.execute(
            f"SELECT {column} AS key, COUNT(*) AS n FROM {table} GROUP BY {column}"
        ).fetchall()
        return {(row["key"] if row["key"] is not None else "unknown"): row["n"] for row in rows}

    def coverage(self, *, limit_runs: int = 5) -> dict[str, Any]:
        files_total = self.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        pages_total = self.conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        models_total = self.conn.execute("SELECT COUNT(*) FROM models").fetchone()[0]
        sized = self.conn.execute(
            "SELECT COUNT(*) FROM files WHERE size IS NOT NULL"
        ).fetchone()[0]
        hashed = self.conn.execute(
            "SELECT COUNT(*) FROM files WHERE sha256 IS NOT NULL"
        ).fetchone()[0]

        # The filename pattern can only be *proven* by a live observation.
        # An offline fixture is useful for tests, but must never be presented
        # as evidence about the real vendor site.
        has_live_run = (
            self.conn.execute(
                "SELECT 1 FROM runs WHERE allow_network = 1 LIMIT 1"
            ).fetchone()
            is not None
        )

        proven: list[str] = []
        for row in self.conn.execute(
            "SELECT url_canonical, filename FROM files WHERE evidence_tier = 'confirmed'"
        ):
            filename = row["filename"] or ""
            path = urllib.parse.urlsplit(row["url_canonical"]).path
            if (
                "/wp-content/uploads/firmwares/" in path
                and PACKAGE_RE.match(filename)
                and is_archive_filename(filename, (".tar.gz", ".tgz", ".zip"))
            ):
                proven.append(row["url_canonical"])

        regions = sorted(
            {
                row[0]
                for row in self.conn.execute("SELECT region FROM files")
                if row[0]
            }
            | {
                row[0]
                for row in self.conn.execute("SELECT region FROM pages")
                if row[0]
            }
            | {
                row[0]
                for row in self.conn.execute("SELECT region FROM models")
                if row[0]
            }
        )
        region_rows: list[dict[str, Any]] = []
        for region in regions:
            counts = {}
            for field in ("files", "pages", "models"):
                counts[field] = self.conn.execute(
                    f"SELECT COUNT(*) FROM {field} WHERE region = ?", (region,)
                ).fetchone()[0]
            tiers = {
                row[0]: row[1]
                for row in self.conn.execute(
                    "SELECT evidence_tier, COUNT(*) FROM files WHERE region = ? GROUP BY evidence_tier",
                    (region,),
                )
            }
            region_rows.append({"region": region, **counts, "files_by_tier": tiers})

        runs = [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit_runs,)
            ).fetchall()
        ]
        for run in runs:
            raw = run.pop("stats_json", None)
            run["stats"] = json.loads(raw) if raw else None

        return {
            "generated_at": utcnow(),
            "files_total": files_total,
            "files_by_region": self._counts("files", "region"),
            "files_by_evidence_tier": self._counts("files", "evidence_tier"),
            "files_by_source_kind": self._counts("files", "source_kind"),
            "files_with_size": sized,
            "files_with_sha256": hashed,
            "unique_model_codes": self.conn.execute(
                "SELECT COUNT(DISTINCT model_code) FROM files WHERE model_code IS NOT NULL"
            ).fetchone()[0],
            "unique_model_slugs": self.conn.execute(
                "SELECT COUNT(DISTINCT model_slug) FROM files WHERE model_slug IS NOT NULL"
            ).fetchone()[0],
            "pages_total": pages_total,
            "pages_by_classification": self._counts("pages", "classification"),
            "pages_by_region": self._counts("pages", "region"),
            "models_total": models_total,
            "models_by_evidence_tier": self._counts("models", "evidence_tier"),
            "filename_pattern_proven": bool(proven) and has_live_run,
            "filename_pattern_matching_files": len(proven),
            "filename_pattern_confirmed_files": len(proven) if has_live_run else 0,
            "filename_pattern_evidence": (
                "live_run" if has_live_run else "offline_or_unverified"
            ),
            "filename_pattern_example": proven[0] if proven else None,
            "regions": region_rows,
            "runs": runs,
            "disclaimer": (
                "Coverage describes publicly linked files observed on the configured "
                "sites during this crawl. It is not a claim about all firmware that "
                "exists (OTA/service-only, factory and paid-mirror images are excluded)."
            ),
        }

    def export_json(self, path: Path) -> Path:
        payload = {
            "tool": "fwmap",
            "generated_at": utcnow(),
            "coverage": self.coverage(),
            "files": self.list_files(),
            "pages": [
                dict(row)
                for row in self.conn.execute(
                    "SELECT * FROM pages ORDER BY id"
                ).fetchall()
            ],
            "models": [
                dict(row)
                for row in self.conn.execute(
                    "SELECT * FROM models ORDER BY id"
                ).fetchall()
            ],
        }
        path = Path(path)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def export_csv(self, path: Path) -> Path:
        path = Path(path)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        rows = self.list_files()
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(FILE_FIELDS))
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field) for field in FILE_FIELDS})
        return path
