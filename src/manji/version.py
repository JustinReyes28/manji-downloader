"""Package version and optional build metadata."""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError, version

_DISTRIBUTION_NAME = "manji-downloader"


def _detect_version() -> str:
    try:
        return version(_DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return "0.0.0+dev"


__version__ = _detect_version()
COMMIT: str | None = os.environ.get("COMMIT") or None
BUILD_DATE: str | None = os.environ.get("BUILD_DATE") or None
