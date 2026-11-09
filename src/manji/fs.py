"""Atomic filesystem writes and safe path joins."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from manji.errors import DownloadError


def safe_join(base: Path | str, relative: str | Path) -> Path:
    """Join ``relative`` under ``base``, rejecting escapes and absolute paths."""

    base_path = Path(base).expanduser().resolve()
    candidate = Path(relative)
    if candidate.is_absolute() or candidate.drive or str(relative).startswith(("\\", "/")):
        raise DownloadError(f"Refusing absolute path {candidate} outside {base_path}.")
    if not candidate.parts:
        raise DownloadError("Refusing an empty relative path.")

    target = (base_path / candidate).resolve()
    if target == base_path or base_path not in target.parents:
        raise DownloadError(f"Refusing path traversal: {candidate} escapes {base_path}.")
    return target


def atomic_write_bytes(path: Path | str, data: bytes) -> Path:
    """Write ``data`` to ``path`` via a temporary sibling and ``os.replace``."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle_fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle_fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, destination)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return destination


def atomic_write_text(path: Path | str, text: str, *, encoding: str = "utf-8") -> Path:
    return atomic_write_bytes(path, text.encode(encoding))


def atomic_write_json(path: Path | str, payload: object, *, indent: int = 2) -> Path:
    serialized = json.dumps(payload, indent=indent, ensure_ascii=False, default=str)
    return atomic_write_text(path, serialized + "\n")
