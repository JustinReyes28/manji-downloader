"""Public adapter contract and registry imports."""

from manji.adapters.base import AuthMode, SiteMetadata, SourceAdapter, Target
from manji.adapters.registry import (
    AdapterRegistry,
    get_registry,
    list_supported_sites,
    register,
    reset_registry,
    resolve_for_url,
)

__all__ = [
    "AdapterRegistry",
    "AuthMode",
    "SiteMetadata",
    "SourceAdapter",
    "Target",
    "get_registry",
    "list_supported_sites",
    "register",
    "reset_registry",
    "resolve_for_url",
]
