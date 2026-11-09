from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from manji.domain import Category, MediaItem, MediaVariant, SeriesCatalog
from manji.organize.sidecars import (
    episode_payload,
    series_payload,
    write_episode_sidecar,
    write_series_sidecar,
)

pytestmark = pytest.mark.unit

MOMENT = datetime(2024, 5, 6, 12, 0, tzinfo=UTC)


def catalog() -> SeriesCatalog:
    item = MediaItem(id="ep-1", number=1, title="Episode 1", url="https://mock.test/e/1")
    return SeriesCatalog(
        title="Example",
        site_id="mock_json",
        source_url="https://mock.test/series/example?token=supersecret",
        episodes=(item,),
    )


def item() -> MediaItem:
    return MediaItem(id="ep-1", number=1, title="Episode 1", url="https://mock.test/e/1")


def variant() -> MediaVariant:
    return MediaVariant(
        id="v1",
        quality="1080p",
        container="mkv",
        size_bytes=1234,
        uploaded_at=MOMENT,
        download_count=42,
        url="https://mock.test/media/e1.mkv?sig=verysecret",
    )


def test_series_payload_contains_counts_and_redacts() -> None:
    payload = series_payload(catalog(), retrieved_at=MOMENT)
    assert payload["adapter"] == "mock_json"
    assert payload["title"] == "Example"
    assert payload["counts"] == {
        "episodes": 1,
        "ovas": 0,
        "movies": 0,
        "specials": 0,
    }
    serialized = json.dumps(payload)
    assert "supersecret" not in serialized
    assert "REDACTED" in serialized
    assert payload["generated_at"] == "2024-05-06T12:00:00Z"


def test_episode_payload_has_variant_metrics_and_no_secrets() -> None:
    payload = episode_payload(
        Category.EPISODES,
        item(),
        variant(),
        site_id="mock_json",
        source_url="https://mock.test/series/example",
        retrieved_at=MOMENT,
    )
    assert payload["adapter"] == "mock_json"
    assert payload["category"] == "episodes"
    assert payload["episode_number"] == 1
    metrics = payload["variant"]
    assert isinstance(metrics, dict)
    assert metrics["quality"] == "1080p"
    assert metrics["size_bytes"] == 1234
    assert metrics["download_count"] == 42
    serialized = json.dumps(payload)
    assert "verysecret" not in serialized


def test_write_series_sidecar_is_json(tmp_path: Path) -> None:
    target = write_series_sidecar(tmp_path, catalog(), retrieved_at=MOMENT)
    assert target.name == "series.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["version"] == "1.0"
    assert payload["adapter"] == "mock_json"


def test_write_episode_sidecar_is_yaml(tmp_path: Path) -> None:
    target = write_episode_sidecar(
        tmp_path,
        Category.EPISODES,
        item(),
        variant(),
        site_id="mock_json",
        source_url="https://mock.test/series/example",
        retrieved_at=MOMENT,
    )
    assert target.name == "episode.yaml"
    payload = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert payload["variant"]["id"] == "v1"
    assert payload["category"] == "episodes"


def test_sidecars_are_written_atomically(tmp_path: Path) -> None:
    write_series_sidecar(tmp_path, catalog(), retrieved_at=MOMENT)
    leftovers = [path for path in tmp_path.iterdir() if path.name.endswith(".tmp")]
    assert leftovers == []


def test_sidecar_custom_filename(tmp_path: Path) -> None:
    target = write_series_sidecar(tmp_path, catalog(), filename="meta.json")
    assert target.name == "meta.json"
    assert target.is_file()
