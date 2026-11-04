#!/usr/bin/env python3
"""Portable static inventory for a local firmware archive.

The archive is never executed. Supported inputs: .zip, .tar, .tar.gz, .tgz
and raw .bin blobs. Extraction is confined to the output directory and
rejects absolute paths, traversal and archive links.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

DEFAULT_MAX_BYTES = 4 * 1024 * 1024 * 1024
CHUNK = 1024 * 1024
ELF_MAGIC = b"\x7fELF"
MAX_ELF_FILES = 200
TOOL_TIMEOUT = 15
SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".zip", ".tar", ".bin")


class InventoryError(Exception):
    """Expected inventory failure."""


class UnsafeMember(InventoryError):
    """Archive member would escape the extraction directory."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_tool(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=TOOL_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def file_description(path: Path, file_tool: str | None) -> str | None:
    if file_tool is None:
        return None
    output = _run_tool([file_tool, "-b", str(path)])
    return output.strip() if output else None


def archive_type(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".tar.gz") or name.endswith(".tgz"):
        return "tar.gz"
    if name.endswith(".tar.bz2"):
        return "tar.bz2"
    if name.endswith(".tar.xz"):
        return "tar.xz"
    if name.endswith(".tar"):
        return "tar"
    if name.endswith(".zip"):
        return "zip"
    if name.endswith(".bin"):
        return "bin"
    if zipfile.is_zipfile(path):
        return "zip"
    if tarfile.is_tarfile(path):
        return "tar"
    return "unknown"


def output_name(path: Path) -> str:
    name = path.name
    lowered = name.lower()
    for suffix in SUFFIXES:
        if lowered.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem or "archive"


def safe_member_path(root: Path, member: str) -> Path:
    normalized = member.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or re.match(r"^[A-Za-z]:", normalized):
        raise UnsafeMember(f"absolute path in archive: {member!r}")
    parts = tuple(part for part in pure.parts if part not in ("", "."))
    if not parts or any(part == ".." for part in parts):
        raise UnsafeMember(f"path traversal in archive: {member!r}")
    target = (root / Path(*parts)).resolve()
    if not target.is_relative_to(root.resolve()):
        raise UnsafeMember(f"member escapes output directory: {member!r}")
    return target


def _write_member(target: Path, source, size: int, mode: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with target.open("wb") as handle:
        for chunk in iter(lambda: source.read(CHUNK), b""):
            written += len(chunk)
            if written > size:
                raise InventoryError(f"member larger than declared size: {target}")
            handle.write(chunk)
    os.chmod(target, mode & 0o777)


def extract_zip(
    archive: Path, destination: Path, max_bytes: int
) -> tuple[list[dict[str, Any]], list[str]]:
    files: list[dict[str, Any]] = []
    notes: list[str] = []
    total = 0
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            if info.is_dir():
                continue
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                notes.append(f"skipped symlink member: {info.filename}")
                continue
            total += info.file_size
            if total > max_bytes:
                raise InventoryError(f"archive exceeds --max-bytes {max_bytes}")
            target = safe_member_path(destination, info.filename)
            with bundle.open(info, "r") as source:
                _write_member(target, source, info.file_size, mode or 0o644)
            files.append(
                {
                    "path": target.relative_to(destination).as_posix(),
                    "size": info.file_size,
                    "mode": f"{(mode or 0o644) & 0o777:04o}",
                }
            )
    return files, notes


def extract_tar(
    archive: Path, destination: Path, max_bytes: int
) -> tuple[list[dict[str, Any]], list[str]]:
    files: list[dict[str, Any]] = []
    notes: list[str] = []
    total = 0
    with tarfile.open(archive, mode="r:*") as bundle:
        for member in bundle.getmembers():
            if member.isdir():
                continue
            if member.issym() or member.islnk():
                notes.append(f"skipped link member: {member.name}")
                continue
            if member.isdev() or member.isfifo():
                notes.append(f"skipped special member: {member.name}")
                continue
            if not member.isfile():
                notes.append(f"skipped non-regular member: {member.name}")
                continue
            total += member.size
            if total > max_bytes:
                raise InventoryError(f"archive exceeds --max-bytes {max_bytes}")
            target = safe_member_path(destination, member.name)
            source = bundle.extractfile(member)
            if source is None:
                notes.append(f"could not read member: {member.name}")
                continue
            _write_member(target, source, member.size, member.mode)
            files.append(
                {
                    "path": target.relative_to(destination).as_posix(),
                    "size": member.size,
                    "mode": f"{member.mode & 0o777:04o}",
                }
            )
    return files, notes


def _is_elf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) == ELF_MAGIC
    except OSError:
        return False


def _elf_entry(
    path: Path,
    relative: str,
    readelf: str | None,
    file_tool: str | None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "path": relative,
        "arch": None,
        "bits": None,
        "needed": [],
    }
    if readelf is not None:
        header = _run_tool([readelf, "-h", str(path)])
        if header:
            for line in header.splitlines():
                stripped = line.strip()
                if stripped.startswith("Class:"):
                    entry["bits"] = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("Machine:"):
                    entry["arch"] = stripped.split(":", 1)[1].strip()
        dynamic = _run_tool([readelf, "-d", str(path)])
        if dynamic:
            needed = []
            for line in dynamic.splitlines():
                if "(NEEDED)" not in line:
                    continue
                match = re.search(r"\[([^\]]+)\]", line)
                if match:
                    needed.append(match.group(1))
            entry["needed"] = needed
    if entry["arch"] is None and file_tool is not None:
        description = file_description(path, file_tool)
        if description:
            entry["file_description"] = description
    return entry


def collect_elf(
    destination: Path,
    files: Iterable[dict[str, Any]],
    readelf: str | None,
    file_tool: str | None,
) -> dict[str, Any]:
    available = readelf is not None or file_tool is not None
    entries: list[dict[str, Any]] = []
    if available:
        for item in files:
            if len(entries) >= MAX_ELF_FILES:
                break
            target = destination / item["path"]
            if not _is_elf(target):
                continue
            entries.append(_elf_entry(target, item["path"], readelf, file_tool))
    return {
        "available": available,
        "readelf": readelf,
        "file": file_tool,
        "entries": entries,
        "reason": None if available else "neither readelf nor file is installed",
    }


def inventory(archive: Path, out_dir: Path, max_bytes: int, force: bool) -> dict[str, Any]:
    if not archive.is_file():
        raise InventoryError(f"archive not found: {archive}")
    archive_size = archive.stat().st_size
    kind = archive_type(archive)
    destination = (out_dir / output_name(archive)).resolve()
    if destination.exists() and not destination.is_dir():
        raise InventoryError(f"output path is not a directory: {destination}")
    if destination.is_dir() and any(destination.iterdir()) and not force:
        raise InventoryError(
            f"output directory is not empty: {destination} (use --force)"
        )
    destination.mkdir(parents=True, exist_ok=True)

    file_tool = shutil.which("file")
    readelf = shutil.which("readelf")
    notes: list[str] = []
    files: list[dict[str, Any]] = []
    extracted = False

    if kind in ("zip", "tar", "tar.gz", "tar.bz2", "tar.xz"):
        try:
            if kind == "zip":
                files, notes = extract_zip(archive, destination, max_bytes)
            else:
                files, notes = extract_tar(archive, destination, max_bytes)
        except (zipfile.BadZipFile, tarfile.TarError, EOFError) as exc:
            raise InventoryError(f"cannot read {kind} archive: {exc}") from exc
        extracted = True
    elif kind == "bin":
        files = [{"path": archive.name, "size": archive_size, "mode": None}]
        notes.append("raw binary blob: not extracted")
    else:
        notes.append(f"unknown archive type: {kind}; not extracted")

    for item in files:
        item["elf"] = False
    elf = collect_elf(destination, files, readelf, file_tool)
    elf_paths = {entry["path"] for entry in elf["entries"]}
    for item in files:
        item["elf"] = item["path"] in elf_paths

    result: dict[str, Any] = {
        "archive": str(archive),
        "archive_type": kind,
        "size": archive_size,
        "sha256": sha256_file(archive),
        "file_type": file_description(archive, file_tool) or kind,
        "out_dir": str(destination),
        "extracted": extracted,
        "file_count": len(files),
        "total_bytes": sum(int(item["size"]) for item in files),
        "files": files,
        "elf": elf,
        "tools": {"file": file_tool, "readelf": readelf},
        "notes": notes,
    }
    (destination / "inventory.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fwinv",
        description=(
            "Static inventory of a local firmware archive (hash, type, file list, "
            "ELF architecture/NEEDED). The archive is never executed."
        ),
    )
    parser.add_argument("archive", type=Path, help="archive to inspect")
    parser.add_argument(
        "--out",
        type=Path,
        help="output directory (default: ./fwinv-out/<archive-name>)",
    )
    parser.add_argument("--json", action="store_true", help="print JSON to stdout")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help="maximum extracted bytes (default: 4 GiB)",
    )
    parser.add_argument(
        "--force", action="store_true", help="write into a non-empty output directory"
    )
    return parser


def print_human(result: dict[str, Any]) -> None:
    print(f"archive:  {result['archive']}")
    print(f"type:     {result['archive_type']}")
    print(f"size:     {result['size']} bytes")
    print(f"sha256:   {result['sha256']}")
    print(f"out:      {result['out_dir']}")
    print(f"files:    {result['file_count']} ({result['total_bytes']} bytes)")
    for item in result["files"][:50]:
        print(f"  {item['size']:>12}  {item['path']}")
    if result["file_count"] > 50:
        print(f"  ... {result['file_count'] - 50} more")
    elf = result["elf"]
    print(f"ELF:      available={elf['available']}")
    for entry in elf["entries"][:20]:
        needed = ", ".join(entry["needed"]) or "-"
        print(f"  {entry['path']}  arch={entry['arch']} needed={needed}")
    for note in result["notes"]:
        print(f"note:     {note}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out_dir = args.out or Path("fwinv-out")
    try:
        result = inventory(args.archive, out_dir, args.max_bytes, args.force)
    except (InventoryError, OSError) as exc:
        print(f"fwinv: error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_human(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
