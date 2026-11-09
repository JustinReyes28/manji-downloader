from __future__ import annotations

import json
from pathlib import Path

import pytest

from manji.errors import DownloadError
from manji.fs import atomic_write_bytes, atomic_write_json, atomic_write_text, safe_join

pytestmark = pytest.mark.unit


def test_atomic_write_bytes(tmp_path: Path) -> None:
    target = atomic_write_bytes(tmp_path / "nested" / "file.bin", b"payload")
    assert target.read_bytes() == b"payload"
    assert not [path for path in target.parent.iterdir() if path.suffix == ".tmp"]


def test_atomic_write_text_uses_utf8(tmp_path: Path) -> None:
    target = atomic_write_text(tmp_path / "file.txt", "héllo")
    assert target.read_text(encoding="utf-8") == "héllo"


def test_atomic_write_json_round_trip(tmp_path: Path) -> None:
    target = atomic_write_json(tmp_path / "data.json", {"a": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}


def test_atomic_write_replaces_existing(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("old", encoding="utf-8")
    atomic_write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_atomic_write_failure_leaves_no_temp(tmp_path: Path, monkeypatch) -> None:
    import os

    def boom(*_args, **_kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        atomic_write_bytes(tmp_path / "file.bin", b"data")
    assert list(tmp_path.iterdir()) == []


def test_safe_join_basic(tmp_path: Path) -> None:
    assert safe_join(tmp_path, "a/b.txt") == (tmp_path / "a" / "b.txt").resolve()


def test_safe_join_rejects_absolute(tmp_path: Path) -> None:
    with pytest.raises(DownloadError, match="absolute"):
        safe_join(tmp_path, Path("/etc/passwd"))


def test_safe_join_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(DownloadError, match="traversal"):
        safe_join(tmp_path, "../escape.txt")


def test_safe_join_rejects_nested_traversal(tmp_path: Path) -> None:
    with pytest.raises(DownloadError, match="traversal"):
        safe_join(tmp_path, "a/../../escape.txt")


def test_safe_join_rejects_empty(tmp_path: Path) -> None:
    with pytest.raises(DownloadError, match="empty"):
        safe_join(tmp_path, "")


def test_safe_join_allows_sibling_prefix_name(tmp_path: Path) -> None:
    # A directory named like the base plus a suffix must not be treated as inside.
    (tmp_path / "base").mkdir()
    with pytest.raises(DownloadError):
        safe_join(tmp_path / "base", "../base-other/file.txt")
