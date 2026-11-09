"""Adapter registry and URL routing."""

from __future__ import annotations

import threading
from urllib.parse import urlsplit

from manji.adapters.base import SiteMetadata, SourceAdapter
from manji.errors import UnsupportedSiteError

_ALLOWED_SCHEMES = frozenset({"http", "https"})


def _read_metadata(adapter: SourceAdapter) -> SiteMetadata:
    metadata = adapter.get_site_metadata()
    if not isinstance(metadata, SiteMetadata):
        raise ValueError("Adapter get_site_metadata() must return SiteMetadata.")
    return metadata


class AdapterRegistry:
    """Ordered collection of site adapters with URL routing."""

    def __init__(self) -> None:
        self._adapters: list[SourceAdapter] = []
        self._lock = threading.Lock()

    def register(self, adapter: SourceAdapter) -> None:
        metadata = _read_metadata(adapter)
        with self._lock:
            for existing in self._adapters:
                if _read_metadata(existing).id == metadata.id:
                    raise ValueError(f"Adapter {metadata.id!r} is already registered.")
            self._adapters.append(adapter)

    def resolve_for_url(self, url: str) -> SourceAdapter:
        parsed = urlsplit(url.strip())
        if parsed.scheme.lower() not in _ALLOWED_SCHEMES or not parsed.netloc:
            raise UnsupportedSiteError(
                f"Unsupported URL {url!r}. Provide a complete http or https URL."
            )
        with self._lock:
            adapters = tuple(self._adapters)
        for adapter in adapters:
            if adapter.can_handle(url):
                return adapter
        raise UnsupportedSiteError(
            f"No adapter supports {url!r}. Run 'manji adapters list' to see supported sites."
        )

    def list_supported_sites(self) -> tuple[SiteMetadata, ...]:
        with self._lock:
            adapters = tuple(self._adapters)
        return tuple(
            sorted((_read_metadata(adapter) for adapter in adapters), key=lambda meta: meta.id)
        )

    def get(self, site_id: str) -> SourceAdapter | None:
        with self._lock:
            adapters = tuple(self._adapters)
        for adapter in adapters:
            if _read_metadata(adapter).id == site_id:
                return adapter
        return None

    def clear(self) -> None:
        with self._lock:
            self._adapters.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._adapters)


_registry = AdapterRegistry()
_registry_lock = threading.Lock()


def get_registry() -> AdapterRegistry:
    """Return the process-wide registry used by the CLI."""

    return _registry


def reset_registry() -> None:
    """Clear the process-wide registry. Intended for tests and app wiring."""

    global _registry
    with _registry_lock:
        _registry = AdapterRegistry()


def register(adapter: SourceAdapter) -> None:
    get_registry().register(adapter)


def resolve_for_url(url: str) -> SourceAdapter:
    return get_registry().resolve_for_url(url)


def list_supported_sites() -> tuple[SiteMetadata, ...]:
    return get_registry().list_supported_sites()
