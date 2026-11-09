"""Filename templating and metadata sidecars."""

from manji.organize.filenames import (
    ALLOWED_VARIABLES,
    MAX_SEGMENT_LENGTH,
    FilenameContext,
    build_destination,
    render_relative_path,
    validate_template,
)
from manji.organize.sidecars import (
    SIDECAR_VERSION,
    episode_payload,
    series_payload,
    write_episode_sidecar,
    write_series_sidecar,
)

__all__ = [
    "ALLOWED_VARIABLES",
    "MAX_SEGMENT_LENGTH",
    "SIDECAR_VERSION",
    "FilenameContext",
    "build_destination",
    "episode_payload",
    "render_relative_path",
    "series_payload",
    "validate_template",
    "write_episode_sidecar",
    "write_series_sidecar",
]
