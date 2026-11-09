"""Compliant streaming downloader with atomic writes and Range resume."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import httpx

from manji.config.models import ConflictResolution
from manji.errors import DownloadError
from manji.fs import atomic_write_json
from manji.log import get_logger
from manji.net.client import CompliantClient

logger = get_logger("download")

CHUNK_SIZE = 64 * 1024
RESUME_SUFFIX = ".resume.json"


class DownloadOutcome(StrEnum):
    """What a download attempt did."""

    DOWNLOADED = "downloaded"
    RESUMED = "resumed"
    SKIPPED = "skipped"
    RENAMED = "renamed"


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Outcome of one download."""

    destination: Path
    outcome: DownloadOutcome
    bytes_written: int
    total_bytes: int | None
    resumed_from: int = 0

    @property
    def skipped(self) -> bool:
        return self.outcome is DownloadOutcome.SKIPPED


@dataclass(frozen=True, slots=True)
class ResumeState:
    """Resume metadata stored next to the temporary file."""

    url: str
    etag: str | None = None
    last_modified: str | None = None
    total_bytes: int | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "version": "1.0",
            "url": self.url,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "total_bytes": self.total_bytes,
            "updated_at": self.updated_at or _now(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ResumeState:
        def text(key: str) -> str | None:
            value = payload.get(key)
            return value if isinstance(value, str) else None

        total = payload.get("total_bytes")
        return cls(
            url=text("url") or "",
            etag=text("etag"),
            last_modified=text("last_modified"),
            total_bytes=total if isinstance(total, int) else None,
            updated_at=text("updated_at"),
        )


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def temp_path_for(destination: Path) -> Path:
    return destination.with_name(destination.name + ".tmp")


def resume_path_for(destination: Path) -> Path:
    return destination.with_name(destination.name + RESUME_SUFFIX)


def read_resume_state(destination: Path) -> ResumeState | None:
    path = resume_path_for(destination)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return ResumeState.from_dict(payload)


def _conflict_target(destination: Path) -> Path:
    stem, suffix = destination.stem, destination.suffix
    index = 1
    while True:
        candidate = destination.with_name(f"{stem} ({index}){suffix}")
        if not candidate.exists() and not temp_path_for(candidate).exists():
            return candidate
        index += 1


class Downloader:
    """Stream remote media to disk through the shared compliant client."""

    def __init__(
        self,
        client: CompliantClient,
        *,
        conflict_resolution: ConflictResolution = ConflictResolution.RENAME,
        chunk_size: int = CHUNK_SIZE,
    ) -> None:
        self.client = client
        self.conflict_resolution = conflict_resolution
        self.chunk_size = chunk_size

    def download(
        self,
        url: str,
        destination: Path | str,
        *,
        stop_event: threading.Event | None = None,
        expected_size: int | None = None,
    ) -> DownloadResult:
        requested = Path(destination)
        requested.parent.mkdir(parents=True, exist_ok=True)

        target = self._resolve_conflict(requested)
        if target is None:
            return DownloadResult(
                destination=requested,
                outcome=DownloadOutcome.SKIPPED,
                bytes_written=0,
                total_bytes=expected_size,
            )

        renamed = target != requested
        temp = temp_path_for(target)
        offset = self._resume_offset(url, target, temp)

        total: int | None = None
        written = 0
        restarted = False
        attempt_offset = offset

        for _attempt in range(2):
            headers = self._range_headers(target, attempt_offset)
            with self.client.stream(url, headers=headers) as response:
                if response.status_code == 416 and attempt_offset:
                    restart = self._handle_range_not_satisfiable(
                        response, target, temp, attempt_offset
                    )
                    if restart is False:
                        # The file was already complete and has been finalized.
                        return DownloadResult(
                            destination=target,
                            outcome=DownloadOutcome.RESUMED,
                            bytes_written=0,
                            total_bytes=attempt_offset,
                            resumed_from=attempt_offset,
                        )
                    attempt_offset = 0
                    restarted = True
                    continue

                if response.status_code == 416:
                    raise DownloadError(
                        f"Server rejected the download range for {target.name} with HTTP 416."
                    )

                if response.status_code == 200 and attempt_offset:
                    logger.info(
                        "Server ignored the resume range for %s; restarting from zero.",
                        target.name,
                    )
                    attempt_offset = 0
                    restarted = True
                    temp.unlink(missing_ok=True)

                if response.status_code not in (200, 206):
                    raise DownloadError(
                        f"Unexpected HTTP {response.status_code} while downloading {target.name}."
                    )

                total = expected_size or _response_total(response, attempt_offset)
                self._write_resume_state(target, response, total)
                written = self._write_stream(
                    response, temp, attempt_offset, stop_event=stop_event, destination=target
                )
            break

        self._finalize(temp, target, total)

        resumed_from = 0 if restarted else offset
        if resumed_from:
            outcome = DownloadOutcome.RESUMED
        elif renamed:
            outcome = DownloadOutcome.RENAMED
        else:
            outcome = DownloadOutcome.DOWNLOADED

        return DownloadResult(
            destination=target,
            outcome=outcome,
            bytes_written=written,
            total_bytes=total,
            resumed_from=resumed_from,
        )

    def _resolve_conflict(self, destination: Path) -> Path | None:
        if not destination.exists():
            return destination
        match self.conflict_resolution:
            case ConflictResolution.OVERWRITE:
                return destination
            case ConflictResolution.SKIP:
                return None
            case ConflictResolution.RENAME:
                return _conflict_target(destination)
        raise DownloadError(f"Unsupported conflict resolution {self.conflict_resolution!r}.")

    def _resume_offset(self, url: str, target: Path, temp: Path) -> int:
        if not temp.exists():
            return 0
        state = read_resume_state(target)
        if state is not None and state.url and _origin_and_path(state.url) != _origin_and_path(url):
            logger.info("Ignoring resume data for %s: source URL changed.", target.name)
            temp.unlink(missing_ok=True)
            resume_path_for(target).unlink(missing_ok=True)
            return 0
        return temp.stat().st_size

    def _range_headers(self, target: Path, offset: int) -> dict[str, str]:
        if not offset:
            return {}
        state = read_resume_state(target)
        headers = {"Range": f"bytes={offset}-"}
        if state is not None:
            validator = state.etag or state.last_modified
            if validator:
                headers["If-Range"] = validator
        return headers

    def _handle_range_not_satisfiable(
        self, response: httpx.Response, target: Path, temp: Path, offset: int
    ) -> bool:
        """Return ``False`` when the file was finalized, ``True`` to restart from zero."""

        total = _total_from_content_range(response.headers.get("content-range"))
        state = read_resume_state(target)
        known_total = total if total is not None else (state.total_bytes if state else None)
        if known_total is not None and offset >= known_total:
            self._finalize(temp, target, known_total)
            raise DownloadError(
                f"{target.name} was already complete at {offset} bytes; it has been finalized."
            )
        logger.info("Server rejected the resume range for %s; restarting from zero.", target.name)
        temp.unlink(missing_ok=True)
        resume_path_for(target).unlink(missing_ok=True)
        return True

    def _write_stream(
        self,
        response: httpx.Response,
        temp: Path,
        offset: int,
        *,
        stop_event: threading.Event | None,
        destination: Path,
    ) -> int:
        written = 0
        with temp.open("ab" if offset else "wb") as handle:
            for chunk in response.iter_bytes(chunk_size=self.chunk_size):
                if stop_event is not None and stop_event.is_set():
                    handle.flush()
                    os.fsync(handle.fileno())
                    raise DownloadError(
                        f"Download of {destination.name} was cancelled; "
                        "the temporary file is kept so a later run can resume."
                    )
                handle.write(chunk)
                written += len(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        return written

    def _write_resume_state(
        self, destination: Path, response: httpx.Response, total: int | None
    ) -> None:
        state = ResumeState(
            url=str(response.request.url),
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
            total_bytes=total,
        )
        try:
            atomic_write_json(resume_path_for(destination), state.to_dict())
        except OSError:
            logger.debug("Could not persist resume metadata for %s.", destination.name)

    def _finalize(self, temp: Path, target: Path, total: int | None) -> None:
        if not temp.exists():
            raise DownloadError(f"Temporary file for {target.name} disappeared.")
        actual = temp.stat().st_size
        if total is not None and actual != total:
            raise DownloadError(
                f"Size mismatch for {target.name}: expected {total} bytes, got {actual}. "
                "The temporary file is kept for resume."
            )
        os.replace(temp, target)
        resume_path_for(target).unlink(missing_ok=True)


def _origin_and_path(url: str) -> str:
    parsed = httpx.URL(url)
    return f"{parsed.scheme}://{parsed.host}{parsed.path}"


def _total_from_content_range(value: str | None) -> int | None:
    if not value:
        return None
    _, _, remainder = value.partition("/")
    try:
        return int(remainder.strip())
    except ValueError:
        return None


def _response_total(response: httpx.Response, offset: int) -> int | None:
    total = _total_from_content_range(response.headers.get("content-range"))
    if total is not None:
        return total
    length = response.headers.get("content-length")
    if length is None:
        return None
    try:
        parsed = int(length)
    except ValueError:
        return None
    if response.status_code == 206:
        return parsed + offset
    return parsed
