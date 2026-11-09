from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from manji.domain import Category, MediaItem, MediaVariant, SeriesCatalog
from manji.errors import ConfigError, DownloadError
from manji.organize.filenames import (
    MAX_SEGMENT_LENGTH,
    FilenameContext,
    build_destination,
    render_relative_path,
    validate_template,
)

pytestmark = pytest.mark.unit

TEMPLATE = "{series_title}/{category}/{series_title} - Episode {episode_number} [{quality}].{ext}"


def make_catalog(title: str = "Example Series") -> SeriesCatalog:
    return SeriesCatalog(title=title, site_id="mock_json", source_url="https://x/series")


def make_item(number: int = 1, title: str = "Episode 1") -> MediaItem:
    return MediaItem(id=f"ep-{number}", number=number, title=title, url="https://x/ep")


def make_variant(
    *, quality: str = "1080p", container: str = "mkv", variant_id: str = "v1"
) -> MediaVariant:
    return MediaVariant(
        id=variant_id,
        quality=quality,
        container=container,
        size_bytes=100,
        uploaded_at=datetime(2024, 5, 6, tzinfo=UTC),
        download_count=1,
        url="https://x/media",
    )


def context(
    *, title: str = "Example Series", number: int = 1, quality: str = "1080p", ext: str = "mkv"
) -> FilenameContext:
    return FilenameContext(
        series_title=title,
        site_id="mock_json",
        category=Category.EPISODES,
        episode_number=number,
        quality=quality,
        id="v1",
        date=date(2024, 5, 6),
        ext=ext,
    )


def test_template_renders_relative_path() -> None:
    rendered = render_relative_path(TEMPLATE, context(number=7))
    assert rendered == "Example Series/Episodes/Example Series - Episode 07 [1080p].mkv"


def test_episode_number_is_zero_padded() -> None:
    assert "Episode 01" in render_relative_path(TEMPLATE, context(number=1))
    assert "Episode 12" in render_relative_path(TEMPLATE, context(number=12))
    assert "Episode 105" in render_relative_path(TEMPLATE, context(number=105))


def test_date_and_other_variables() -> None:
    template = "{site_id}/{date}/{id}.{ext}"
    assert render_relative_path(template, context()) == "mock_json/2024-05-06/v1.mkv"


def test_validate_template_accepts_documented_variables() -> None:
    names = validate_template(TEMPLATE)
    assert set(names) == {"series_title", "category", "episode_number", "quality", "ext"}


def test_unknown_variable_is_an_error() -> None:
    with pytest.raises(ConfigError, match="Unknown filename template variable"):
        validate_template("{series_title}/{nope}.mkv")


def test_malformed_braces_error() -> None:
    with pytest.raises(ConfigError, match="Malformed"):
        validate_template("{series_title}/{oops.mkv")


def test_empty_template_rejected() -> None:
    with pytest.raises(ConfigError, match="must not be empty"):
        validate_template("   ")


def test_absolute_template_rejected() -> None:
    with pytest.raises(ConfigError, match="must be relative"):
        validate_template("/etc/{series_title}")


@pytest.mark.parametrize("char", list('<>:"/\\|?*'))
def test_control_and_illegal_characters_sanitized(char: str) -> None:
    if char in {"/", "\\"}:
        pytest.skip("separators are handled as path structure")
    rendered = render_relative_path("{series_title}.mkv", context(title=f"a{char}b"))
    assert char not in rendered
    assert rendered.startswith("a_b")


def test_trailing_dots_and_spaces_trimmed() -> None:
    rendered = render_relative_path("{series_title}/{series_title}.{ext}", context(title="Name. "))
    assert rendered.split("/")[0] == "Name"


def test_reserved_windows_names_rejected() -> None:
    for name in ("CON", "PRN", "AUX", "NUL", "COM1", "COM9", "LPT1", "LPT9"):
        with pytest.raises(DownloadError, match="reserved Windows device name"):
            render_relative_path("{series_title}.mkv", context(title=name))


def test_reserved_name_with_extension_rejected() -> None:
    with pytest.raises(DownloadError, match="reserved Windows device name"):
        render_relative_path("{series_title}.{ext}", context(title="con", ext="mkv"))


def test_long_segment_rejected() -> None:
    with pytest.raises(DownloadError, match="exceeds"):
        render_relative_path("{series_title}.mkv", context(title="a" * (MAX_SEGMENT_LENGTH + 1)))


def test_traversal_template_rejected() -> None:
    with pytest.raises(DownloadError, match="traversal"):
        render_relative_path("../{series_title}.mkv", context())


def test_empty_segment_from_double_slash() -> None:
    with pytest.raises(DownloadError, match="empty path segment"):
        render_relative_path("{series_title}//{ext}", context())


def test_build_destination_stays_under_base(tmp_path) -> None:
    destination = build_destination(tmp_path, TEMPLATE, context())
    assert destination.is_relative_to(tmp_path.resolve())
    assert destination.name == "Example Series - Episode 01 [1080p].mkv"


def test_build_destination_rejects_escape(tmp_path) -> None:
    with pytest.raises(DownloadError):
        build_destination(tmp_path, "../{series_title}.mkv", context())


def test_context_build_uses_variant_upload_date() -> None:
    ctx = FilenameContext.build(make_catalog(), Category.EPISODES, make_item(), make_variant())
    assert ctx.date == date(2024, 5, 6)
    assert ctx.ext == "mkv"
    assert ctx.category is Category.EPISODES


def test_context_build_falls_back_when_no_upload_date() -> None:
    variant = MediaVariant(
        id="v",
        quality="720p",
        container="MP4",
        size_bytes=1,
        uploaded_at=None,
        download_count=0,
        url="https://x/m",
    )
    ctx = FilenameContext.build(
        make_catalog(),
        Category.OVAS,
        make_item(2),
        variant,
        retrieved_at=datetime(2025, 1, 2, tzinfo=UTC),
    )
    assert ctx.date == date(2025, 1, 2)
    assert ctx.ext == "mp4"


def test_category_display_name_used_not_enum_value() -> None:
    for category, expected in (
        (Category.EPISODES, "Episodes"),
        (Category.OVAS, "OVAs"),
        (Category.MOVIES, "Movies"),
        (Category.SPECIALS, "Specials"),
    ):
        ctx = FilenameContext(
            series_title="S",
            site_id="s",
            category=category,
            episode_number=1,
            quality="1080p",
            id="i",
            date=date(2024, 1, 1),
            ext="mkv",
        )
        assert render_relative_path("{category}", ctx) == expected
