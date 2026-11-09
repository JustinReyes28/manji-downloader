"""Shared test fixtures."""

from __future__ import annotations

import pytest

from manji.adapters.registry import reset_registry


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    reset_registry()
    yield
    reset_registry()
