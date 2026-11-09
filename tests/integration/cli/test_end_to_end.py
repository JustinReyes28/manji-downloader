"""End-to-end CLI tests against local mock adapters."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from manji.adapters import AdapterRegistry
from manji.app import RangeSelection, Services
from manji.cli.app import app, set_services_factory
from manji.config import load_config
from tests.adapters.mock_html import MockHtmlAdapter
from tests.adapters.mock_json import MockJsonAdapter
from tests.conftest import build_client, load_fixture
from tests.helpers import MockSite

pytestmark = [pytest.mark.integration, pytest.mark.compliance]

runner = CliRunner()
FIXTURES = Path(__file__).parents[2] / "fixtures" / "adapters"


def ranges(episodes: str, ovas: str, movies: str, specials: str) -> RangeSelection:
    return RangeSelection(episodes=episodes, ovas=ovas, movies=movies, specials=specials)


def write_config(tmp_path: Path) -> Path:
    path = tmp_path / "manji-config.yaml"
    path.write_text(
        f"""
version: "1.0"
storage:
  base_output_directory: "{(tmp_path / "Anime").as_posix()}"
  batch_export:
    links_file_path: "{(tmp_path / "links.txt").as_posix()}"
    generate_rename_manifest: true
    manifest_file_path: "{(tmp_path / "links-manifest.json").as_posix()}"
""",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def wired(
    mock_json_site: MockSite, mock_html_site: MockSite
) -> Iterator[tuple[AdapterRegistry, object, object]]:
    """Register mock adapters through the CLI's service factory (loopback only)."""

    routes = {
        "mock-json.test": mock_json_site.base_url,
        "mock-html.test": mock_html_site.base_url,
    }
    shared = build_client(mock_json_site.base_url, routes=routes)
    registry = AdapterRegistry()
    registry.register(MockJsonAdapter(shared))
    registry.register(MockHtmlAdapter(shared))

    def factory(loaded) -> Services:  # type: ignore[no-untyped-def]
        return Services.build(loaded, registry=registry, client=shared, configure=False)

    set_services_factory(factory)
    try:
        yield registry, shared, shared
    finally:
        set_services_factory(None)
        shared.close()


def test_documented_six_url_export_flow(wired, tmp_path: Path) -> None:
    """Episodes 1-5 plus OVA 1 at 1080p, biggest size, yields exactly six ordered URLs."""

    registry, _, _ = wired
    config_path = write_config(tmp_path)
    services = Services.build(
        load_config(explicit=config_path, cwd=tmp_path, env={}),
        registry=registry,
        configure=False,
    )
    try:
        plan = services.resolve_plan(
            "https://mock-json.test/series/example",
            ranges=ranges("1-5", "1", "0", "0"),
            quality="1080p",
        )
        assert plan.total == 6
        links, manifest, warnings = services.export(plan)
    finally:
        services.close()

    expected = [
        *[f"https://mock-json.test/media/example/ep-0{n}-1080p.mkv" for n in range(1, 6)],
        "https://mock-json.test/media/example/ova-01-1080p.mkv",
    ]
    text = links.read_text(encoding="utf-8")
    assert text.splitlines() == expected
    assert text.endswith("\n")
    assert warnings == ()

    assert manifest is not None
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert [entry["url"] for entry in payload["entries"]] == expected
    assert payload["entries"][0]["filename"].startswith("Example Mock Series/Episodes/")
    assert payload["entries"][-1]["filename"].startswith("Example Mock Series/OVAs/")


def test_export_links_cli_command(wired, tmp_path: Path) -> None:
    config_path = write_config(tmp_path)
    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "export-links",
            "https://mock-json.test/series/example",
            "--episodes",
            "1-5",
            "--ovas",
            "1",
            "--quality",
            "1080p",
            "--sort",
            "biggest-size",
            "--export-file",
            str(tmp_path / "out-links.txt"),
        ],
    )
    assert result.exit_code == 0, result.output
    lines = (tmp_path / "out-links.txt").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 6
    assert lines[0].endswith("ep-01-1080p.mkv")
    assert lines[-1].endswith("ova-01-1080p.mkv")


def test_info_cli_command(wired, tmp_path: Path) -> None:
    config_path = write_config(tmp_path)
    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "info",
            "https://mock-json.test/series/example",
            "--episodes",
            "1-2",
            "--quality",
            "720p",
            "-v",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Example Mock Series" in result.output
    assert "720p" in result.output


def test_html_adapter_flow_is_site_agnostic(wired, tmp_path: Path) -> None:
    registry, _, _ = wired
    services = Services.build(load_config(cwd=tmp_path, env={}), registry=registry, configure=False)
    try:
        plan = services.resolve_plan(
            "https://mock-html.test/series/example",
            ranges=ranges("1-2", "0", "0", "0"),
            quality="1080p",
        )
    finally:
        services.close()

    assert plan.catalog.site_id == "mock_html"
    assert plan.total == 2
    assert plan.selection[0].variant.url.endswith("ep-01-1080p.mkv")


def test_retrieve_cli_downloads_and_writes_sidecars(
    wired, mock_json_site: MockSite, tmp_path: Path
) -> None:
    payload = b"episode-bytes" * 500
    original = json.loads((FIXTURES / "mock_json" / "variants.json").read_text(encoding="utf-8"))
    variant = dict(original["variants"][0])
    variant["size_bytes"] = len(payload)
    variant["url"] = "https://mock-json.test/media/example/ep-01-1080p.mkv"
    mock_json_site.json("/series/example/episodes/1", {"item_id": "ep-01", "variants": [variant]})
    mock_json_site.static(
        "/media/example/ep-01-1080p.mkv",
        body=payload,
        headers={"Content-Type": "video/x-matroska", "ETag": '"v1"'},
    )

    config_path = write_config(tmp_path)
    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "retrieve",
            "https://mock-json.test/series/example",
            "--episodes",
            "1-1",
            "--quality",
            "1080p",
        ],
    )
    assert result.exit_code == 0, result.output

    output_dir = tmp_path / "Anime"
    downloaded = list(output_dir.rglob("*.mkv"))
    assert downloaded, "retrieve should have produced a media file"
    assert downloaded[0].read_bytes() == payload
    assert not list(output_dir.rglob("*.tmp"))
    assert list(output_dir.rglob("episode.yaml")), "episode sidecar should be written"


def test_non_tty_without_command_errors(wired, tmp_path: Path) -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 2
    assert "not a terminal" in result.output


def test_unknown_sort_is_rejected(wired, tmp_path: Path) -> None:
    config_path = write_config(tmp_path)
    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "info",
            "https://mock-json.test/series/example",
            "--sort",
            "nonsense",
        ],
    )
    assert result.exit_code == 2
    assert "Unknown sort criterion" in result.output


def test_unsupported_site_exits_three(wired, tmp_path: Path) -> None:
    config_path = write_config(tmp_path)
    result = runner.invoke(
        app, ["--config", str(config_path), "info", "https://unknown.test/series/x"]
    )
    assert result.exit_code == 3


def test_invalid_range_exits_two(wired, tmp_path: Path) -> None:
    config_path = write_config(tmp_path)
    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "info",
            "https://mock-json.test/series/example",
            "--episodes",
            "1-999",
        ],
    )
    assert result.exit_code == 2
    assert "outside the available range" in result.output


def test_challenge_halts_export(wired, tmp_path: Path, mock_json_site: MockSite) -> None:
    mock_json_site.static(
        "/series/example",
        status=403,
        body=load_fixture("mock_json", "challenge.html"),
        headers={"Content-Type": "text/html"},
    )
    config_path = write_config(tmp_path)
    result = runner.invoke(
        app,
        ["--config", str(config_path), "export-links", "https://mock-json.test/series/example"],
    )
    assert result.exit_code == 4
    assert "browser" in result.output
    assert mock_json_site.hits("/series/example") == 1


def test_429_then_success(mock_json_site: MockSite, tmp_path: Path) -> None:
    attempts = {"count": 0}
    payload = load_fixture("mock_json", "catalog.json")

    def handler(_method: str, _path: str):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return 429, {"Retry-After": "0"}, b"slow down"
        return 200, {"Content-Type": "application/json"}, payload.encode()

    mock_json_site.route("/series/example", handler)
    client = build_client(mock_json_site.base_url)
    registry = AdapterRegistry()
    registry.register(MockJsonAdapter(client))
    services = Services.build(load_config(cwd=tmp_path, env={}), registry=registry, configure=False)
    try:
        plan = services.resolve_plan(
            "https://mock-json.test/series/example", ranges=ranges("1-1", "0", "0", "0")
        )
    finally:
        services.close()
        client.close()

    assert plan.total == 1
    assert attempts["count"] == 2


def test_cli_never_contacts_non_loopback_hosts(wired, tmp_path: Path) -> None:
    """Every mock-site request must arrive on the loopback server only."""

    from tests.helpers.transport import is_loopback_host

    config_path = write_config(tmp_path)
    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "info",
            "https://mock-json.test/series/example",
            "--episodes",
            "1-1",
        ],
    )
    assert result.exit_code == 0, result.output
    assert is_loopback_host("127.0.0.1")
    assert not is_loopback_host("mock-json.test")
