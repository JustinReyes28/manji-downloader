"""Configuration schema mirroring ``CONFIGURATION.md``."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from manji.adapters.base import AuthMode
from manji.selection.selector import SortCriterion

DEFAULT_USER_AGENT = (
    "ManjiDownloader/1.0 (+https://example.com/manji-downloader; contact@example.com)"
)
DEFAULT_FILENAME_TEMPLATE = (
    "{series_title}/{category}/{series_title} - Episode {episode_number} [{quality}].{ext}"
)


class OutputMode(StrEnum):
    DIRECT_DOWNLOAD = "direct_download"
    EXPORT_LINKS = "export_links"
    BOTH = "both"


class ConflictResolution(StrEnum):
    OVERWRITE = "overwrite"
    SKIP = "skip"
    RENAME = "rename"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class _ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class NetworkConfig(_ConfigModel):
    user_agent: str = DEFAULT_USER_AGENT
    timeout_seconds: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=3, ge=0)
    respect_robots_txt: Literal[True] = True


class SiteAdapterConfig(_ConfigModel):
    enabled: bool = True
    base_domain: str = Field(min_length=1)
    auth_mode: AuthMode = AuthMode.NONE
    api_key_env: str | None = Field(default=None, repr=False)
    cookie_file: str | None = None
    min_request_delay_seconds: float = Field(default=1.5, ge=1.0)


class DefaultRangesConfig(_ConfigModel):
    episodes: str = "1-12"
    ovas: str = "0"
    movies: str = "0"
    specials: str = "0"


class MediaSelectionConfig(_ConfigModel):
    interactive_prompts: bool = True
    default_ranges: DefaultRangesConfig = Field(default_factory=DefaultRangesConfig)
    preferred_qualities: list[str] = Field(
        default_factory=lambda: ["1080p", "720p", "480p"], min_length=1
    )
    preferred_formats: list[str] = Field(default_factory=lambda: ["mkv", "mp4"], min_length=1)
    sort_criterion: SortCriterion = SortCriterion.BIGGEST_SIZE


class RateLimitConfig(_ConfigModel):
    max_concurrent_requests_per_site: int = Field(default=2, ge=1, le=2)
    default_request_delay_seconds: float = Field(default=1.5, ge=1.0)


class CacheConfig(_ConfigModel):
    directory: str = "~/.cache/manji"
    max_size_mb: int = Field(default=500, ge=1)
    retention_hours: int = Field(default=72, ge=1)
    enabled: bool = True


class BatchExportConfig(_ConfigModel):
    links_file_path: str = "./links.txt"
    generate_rename_manifest: bool = True
    manifest_file_path: str = "./links-manifest.json"


class StorageConfig(_ConfigModel):
    output_mode: OutputMode = OutputMode.DIRECT_DOWNLOAD
    base_output_directory: str = "./Anime_Downloads"
    filename_template: str = DEFAULT_FILENAME_TEMPLATE
    batch_export: BatchExportConfig = Field(default_factory=BatchExportConfig)
    conflict_resolution: ConflictResolution = ConflictResolution.RENAME
    save_metadata_sidecar: bool = True


class LoggingConfig(_ConfigModel):
    level: LogLevel = LogLevel.INFO
    file_path: str = "~/.local/state/manji/manji.log"
    sanitize_secrets: bool = True


class AppConfig(_ConfigModel):
    version: Literal["1.0"] = "1.0"
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    site_adapters: dict[str, SiteAdapterConfig] = Field(default_factory=dict)
    media_selection: MediaSelectionConfig = Field(default_factory=MediaSelectionConfig)
    rate_limits: RateLimitConfig = Field(default_factory=RateLimitConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
