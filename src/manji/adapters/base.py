"""Source adapter contract shared by every site integration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from manji.domain.catalog import MediaItem, MediaVariant, SeriesCatalog


class AuthMode(StrEnum):
    """How an adapter authenticates against its site."""

    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    COOKIE_SESSION = "cookie_session"


@dataclass(frozen=True, slots=True)
class SiteMetadata:
    """Static description of a site adapter."""

    id: str
    display_name: str
    domains: tuple[str, ...]
    default_min_request_delay_seconds: float
    auth_mode: AuthMode
    url_patterns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Site metadata id must not be empty.")
        if not self.display_name.strip():
            raise ValueError(f"Site metadata {self.id!r} must have a display name.")
        if not self.domains:
            raise ValueError(f"Site metadata {self.id!r} must declare at least one domain.")
        if any(not domain.strip() for domain in self.domains):
            raise ValueError(f"Site metadata {self.id!r} contains an empty domain.")
        if self.default_min_request_delay_seconds < 0:
            raise ValueError(f"Site metadata {self.id!r} cannot have a negative request delay.")
        if not isinstance(self.auth_mode, AuthMode):
            raise ValueError(f"Site metadata {self.id!r} has an invalid auth mode.")


@dataclass(frozen=True, slots=True)
class Target:
    """A resolved request target handed to ``validate_access``."""

    url: str
    site_id: str
    auth_mode: AuthMode

    @classmethod
    def for_url(cls, url: str, metadata: SiteMetadata) -> Target:
        return cls(url=url, site_id=metadata.id, auth_mode=metadata.auth_mode)


class SourceAdapter(Protocol):
    """Synchronous contract implemented by every site adapter."""

    def get_site_metadata(self) -> SiteMetadata: ...

    def can_handle(self, url: str) -> bool: ...

    def validate_access(self, target: Target) -> None: ...

    def resolve_series_catalog(self, series_url: str) -> SeriesCatalog: ...

    def resolve_episode_variants(self, item: MediaItem) -> tuple[MediaVariant, ...]: ...
