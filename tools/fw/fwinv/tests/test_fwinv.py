from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fwinv  # noqa: E402


def make_zip(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("a.txt", b"hello\n")
        bundle.writestr("dir/b.txt", b"world\n")
    return path


def make_tar(path: Path) -> Path:
    with tarfile.open(path, "w:gz") as bundle:
        for name, data in (("a.txt", b"hello\n"), ("dir/b.txt", b"world\n")):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            bundle.addfile(info, io.BytesIO(data))
    return path


def run_json(archive: Path, out: Path, capsys) -> dict:
    exit_code = fwinv.main([str(archive), "--out", str(out), "--json"])
    assert exit_code == 0
    return json.loads(capsys.readouterr().out)


def test_zip_inventory(tmp_path: Path, capsys) -> None:
    archive = make_zip(tmp_path / "fw.zip")
    payload = run_json(archive, tmp_path / "out", capsys)

    assert payload["archive_type"] == "zip"
    assert payload["size"] == archive.stat().st_size
    assert payload["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert payload["file_count"] == 2
    assert {item["path"] for item in payload["files"]} == {"a.txt", "dir/b.txt"}
    assert payload["extracted"] is True
    assert isinstance(payload["elf"]["available"], bool)
    assert "available" in payload["elf"]
    assert Path(payload["out_dir"]).name == "fw"


def test_tar_gz_inventory(tmp_path: Path, capsys) -> None:
    archive = make_tar(tmp_path / "fw.tar.gz")
    payload = run_json(archive, tmp_path / "out", capsys)

    assert payload["archive_type"] == "tar.gz"
    assert payload["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert payload["file_count"] == 2
    assert {item["path"] for item in payload["files"]} == {"a.txt", "dir/b.txt"}
    assert payload["total_bytes"] == 12
    assert (Path(payload["out_dir"]) / "dir" / "b.txt").read_bytes() == b"world\n"


def test_bin_blob_is_listed_not_extracted(tmp_path: Path, capsys) -> None:
    archive = tmp_path / "fw.bin"
    archive.write_bytes(b"\x00\x01\x02payload")
    payload = run_json(archive, tmp_path / "out", capsys)

    assert payload["archive_type"] == "bin"
    assert payload["extracted"] is False
    assert payload["file_count"] == 1
    assert payload["files"][0]["path"] == "fw.bin"
    assert payload["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()


def test_zip_slip_is_rejected(tmp_path: Path, capsys) -> None:
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escape.txt", b"nope")

    exit_code = fwinv.main([str(archive), "--out", str(tmp_path / "out")])
    assert exit_code == 1
    assert not (tmp_path / "escape.txt").exists()
    assert "error" in capsys.readouterr().err.lower()


def test_non_empty_output_requires_force(tmp_path: Path) -> None:
    archive = make_zip(tmp_path / "fw.zip")
    out = tmp_path / "out" / "fw"
    out.mkdir(parents=True)
    (out / "existing.txt").write_text("x", encoding="utf-8")

    assert fwinv.main([str(archive), "--out", str(tmp_path / "out")]) == 1
    assert fwinv.main([str(archive), "--out", str(tmp_path / "out"), "--force"]) == 0
