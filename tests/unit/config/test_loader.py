from __future__ import annotations

import os
import stat
import sys

import pytest

from manji.config import AppConfig, find_config_path, load_config
from manji.config.models import OutputMode, SortCriterion
from manji.errors import ConfigError

pytestmark = pytest.mark.unit

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def _write(path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


MINIMAL_YAML = """
version: "1.0"
network:
  timeout_seconds: 10
"""

MINIMAL_TOML = """
version = "1.0"

[network]
timeout_seconds = 10
"""


def test_defaults_without_file(tmp_path) -> None:
    loaded = load_config(cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert loaded.path is None
    assert loaded.config.version == "1.0"
    assert loaded.config.network.timeout_seconds == 30
    assert loaded.config.network.max_retries == 3
    assert loaded.config.network.respect_robots_txt is True
    assert loaded.config.media_selection.sort_criterion is SortCriterion.BIGGEST_SIZE
    assert loaded.config.rate_limits.max_concurrent_requests_per_site == 2
    assert loaded.config.rate_limits.default_request_delay_seconds == 1.5
    assert loaded.config.storage.output_mode is OutputMode.DIRECT_DOWNLOAD
    assert loaded.config.storage.conflict_resolution.value == "rename"


def test_yaml_and_toml_parity(tmp_path) -> None:
    yaml_dir = tmp_path / "yaml"
    yaml_dir.mkdir()
    _write(yaml_dir / "manji-config.yaml", MINIMAL_YAML)

    toml_dir = tmp_path / "toml"
    toml_dir.mkdir()
    _write(toml_dir / "manji-config.toml", MINIMAL_TOML)

    yaml_config = load_config(cwd=yaml_dir, env={}).config
    toml_config = load_config(cwd=toml_dir, env={}).config
    assert yaml_config == toml_config


def test_explicit_path_wins(tmp_path) -> None:
    local_dir = tmp_path / "local"
    local_dir.mkdir()
    _write(local_dir / "manji-config.yaml", "version: '1.0'\n")
    explicit = tmp_path / "custom.yaml"
    _write(explicit, MINIMAL_YAML)

    loaded = load_config(explicit=explicit, cwd=local_dir, env={})
    assert loaded.path == explicit
    assert loaded.config.network.timeout_seconds == 10


def test_missing_explicit_path_errors(tmp_path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(explicit=tmp_path / "absent.yaml", cwd=tmp_path, env={})


def test_both_local_files_error(tmp_path) -> None:
    _write(tmp_path / "manji-config.yaml", MINIMAL_YAML)
    _write(tmp_path / "manji-config.toml", MINIMAL_TOML)
    with pytest.raises(ConfigError, match="Both manji-config"):
        find_config_path(cwd=tmp_path, env={})


def test_user_config_directory_fallback(tmp_path) -> None:
    cwd = tmp_path / "empty"
    cwd.mkdir()

    if sys.platform == "win32":
        user_dir = tmp_path / "appdata" / "ManjiDownloader"
        env = {"APPDATA": str(tmp_path / "appdata")}
    else:
        user_dir = tmp_path / "xdg" / "manji"
        env = {"HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "xdg")}

    user_dir.mkdir(parents=True)
    _write(user_dir / "config.yaml", MINIMAL_YAML)

    loaded = load_config(cwd=cwd, env=env)
    assert loaded.path == user_dir / "config.yaml"
    assert loaded.config.network.timeout_seconds == 10


def test_home_expansion_uses_injected_env(tmp_path) -> None:
    path = tmp_path / "manji-config.yaml"
    _write(
        path,
        """
version: "1.0"
site_adapters:
  alpha:
    base_domain: "alpha.test"
    auth_mode: "cookie_session"
    cookie_file: "~/cookies/alpha.txt"
""",
    )
    cookie_dir = tmp_path / "cookies"
    cookie_dir.mkdir()
    _write(cookie_dir / "alpha.txt", "# Netscape HTTP Cookie File\n")

    loaded = load_config(explicit=path, cwd=tmp_path, env={"HOME": str(tmp_path)})
    assert loaded.config.site_adapters["alpha"].cookie_file == str(cookie_dir / "alpha.txt")
    assert loaded.config.cache.directory == str(tmp_path / ".cache" / "manji")


def test_env_expansion(tmp_path) -> None:
    path = tmp_path / "manji-config.yaml"
    _write(
        path,
        """
version: "1.0"
site_adapters:
  alpha:
    base_domain: "alpha.test"
    auth_mode: "api_key"
    api_key_env: "${ALPHA_KEY}"
""",
    )
    loaded = load_config(explicit=path, cwd=tmp_path, env={"ALPHA_KEY": "secret-value"})
    assert loaded.config.site_adapters["alpha"].api_key_env == "secret-value"


def test_missing_env_var_errors(tmp_path) -> None:
    path = tmp_path / "manji-config.yaml"
    _write(
        path,
        """
version: "1.0"
site_adapters:
  alpha:
    base_domain: "alpha.test"
    api_key_env: "${ABSENT_KEY}"
""",
    )
    with pytest.raises(ConfigError, match="ABSENT_KEY"):
        load_config(explicit=path, cwd=tmp_path, env={})


@pytest.mark.parametrize(
    "document",
    [
        "version: '1.0'\nunknown_key: true\n",
        "version: '2.0'\n",
        "version: '1.0'\nrate_limits:\n  default_request_delay_seconds: 0.5\n",
        "version: '1.0'\nrate_limits:\n  max_concurrent_requests_per_site: 5\n",
        "version: '1.0'\nnetwork:\n  respect_robots_txt: false\n",
        "version: '1.0'\nmedia_selection:\n  sort_criterion: 'random'\n",
        "version: '1.0'\nmedia_selection:\n  preferred_qualities: []\n",
    ],
)
def test_invalid_values_rejected(tmp_path, document: str) -> None:
    path = tmp_path / "manji-config.yaml"
    _write(path, document)
    with pytest.raises(ConfigError):
        load_config(explicit=path, cwd=tmp_path, env={})


def test_unparseable_file(tmp_path) -> None:
    path = tmp_path / "manji-config.yaml"
    _write(path, "version: [unclosed\n")
    with pytest.raises(ConfigError, match="Cannot parse"):
        load_config(explicit=path, cwd=tmp_path, env={})


def test_non_mapping_document(tmp_path) -> None:
    path = tmp_path / "manji-config.yaml"
    _write(path, "- a\n- b\n")
    with pytest.raises(ConfigError, match="top-level"):
        load_config(explicit=path, cwd=tmp_path, env={})


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
def test_cookie_file_permissions_enforced(tmp_path) -> None:
    cookie = tmp_path / "cookies.txt"
    _write(cookie, "# Netscape HTTP Cookie File\n")
    cookie.chmod(0o644)
    path = tmp_path / "manji-config.yaml"
    _write(
        path,
        f"""
version: "1.0"
site_adapters:
  alpha:
    base_domain: "alpha.test"
    auth_mode: "cookie_session"
    cookie_file: "{cookie}"
""",
    )
    with pytest.raises(ConfigError, match="chmod 600"):
        load_config(explicit=path, cwd=tmp_path, env={})

    cookie.chmod(0o600)
    loaded = load_config(explicit=path, cwd=tmp_path, env={})
    assert loaded.config.site_adapters["alpha"].cookie_file == str(cookie)


def test_cookie_file_must_exist(tmp_path) -> None:
    path = tmp_path / "manji-config.yaml"
    _write(
        path,
        """
version: "1.0"
site_adapters:
  alpha:
    base_domain: "alpha.test"
    auth_mode: "cookie_session"
    cookie_file: "~/definitely-missing-cookies.txt"
""",
    )
    with pytest.raises(ConfigError, match="Cookie file not found"):
        load_config(explicit=path, cwd=tmp_path, env={"HOME": str(tmp_path)})


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
def test_windows_cookie_warning_not_applicable(tmp_path) -> None:
    pytest.skip("POSIX host: Windows warning path does not apply")


def test_example_configs_load(tmp_path) -> None:
    env = {
        "ENV_SITE01_API_KEY": "placeholder",
        "HOME": str(tmp_path),
    }
    cookie_dir = tmp_path / ".config" / "manji" / "cookies"
    cookie_dir.mkdir(parents=True)
    cookie = cookie_dir / "site02_cookies.txt"
    _write(cookie, "# Netscape HTTP Cookie File\n")
    cookie.chmod(stat.S_IRUSR | stat.S_IWUSR)

    yaml_path = os.path.join(REPO_ROOT, "manji-config.example.yaml")
    toml_path = os.path.join(REPO_ROOT, "manji-config.example.toml")

    yaml_config = load_config(explicit=yaml_path, cwd=tmp_path, env=env).config
    toml_config = load_config(explicit=toml_path, cwd=tmp_path, env=env).config
    assert yaml_config == toml_config
    assert "site_adapter_01" in yaml_config.site_adapters


def test_config_is_frozen_typed() -> None:
    config = AppConfig()
    assert config.version == "1.0"
    assert config.logging.level.value == "INFO"
