"""Configuration path discovery and loading."""

from __future__ import annotations

import os
import re
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from manji.config.models import AppConfig
from manji.errors import ConfigError

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True, slots=True)
class LoadedConfig:
    """A validated configuration plus provenance and non-fatal warnings."""

    config: AppConfig
    path: Path | None
    warnings: tuple[str, ...] = ()


def user_config_directory(
    env: Mapping[str, str] | None = None, *, platform: str | None = None
) -> Path:
    lookup = os.environ if env is None else env
    current = sys.platform if platform is None else platform
    if current == "win32":
        appdata = lookup.get("APPDATA")
        if appdata:
            return Path(appdata) / "ManjiDownloader"
        home = lookup.get("USERPROFILE") or lookup.get("HOME")
        if home:
            return Path(home) / "AppData" / "Roaming" / "ManjiDownloader"
        return Path.home() / "AppData" / "Roaming" / "ManjiDownloader"
    xdg = lookup.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "manji"
    home = lookup.get("HOME")
    if home:
        return Path(home) / ".config" / "manji"
    return Path.home() / ".config" / "manji"


def _local_candidates(cwd: Path) -> list[Path]:
    return [cwd / "manji-config.yaml", cwd / "manji-config.toml"]


def find_config_path(
    *,
    explicit: str | Path | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Path | None:
    """Resolve the configuration path following the documented search order."""

    if explicit is not None:
        candidate = Path(explicit).expanduser()
        if not candidate.is_file():
            raise ConfigError(f"Configuration file not found: {candidate}")
        return candidate

    working_dir = Path.cwd() if cwd is None else Path(cwd)
    local = [path for path in _local_candidates(working_dir) if path.is_file()]
    if len(local) > 1:
        raise ConfigError(
            "Both manji-config.yaml and manji-config.toml exist in the working directory. "
            "Keep one or pass --config <path>."
        )
    if local:
        return local[0]

    user_dir = user_config_directory(env)
    for name in ("config.yaml", "config.toml"):
        candidate = user_dir / name
        if candidate.is_file():
            return candidate
    return None


def _expand_env(value: object, env: Mapping[str, str], source: Path) -> object:
    if isinstance(value, str):

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in env:
                raise ConfigError(
                    f"{source}: environment variable {name!r} is referenced but not set."
                )
            return env[name]

        return _ENV_PATTERN.sub(replace, value)
    if isinstance(value, dict):
        return {key: _expand_env(item, env, source) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env(item, env, source) for item in value]
    return value


def _read_document(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ConfigError(f"Cannot read configuration file {path}: {error}") from error

    try:
        if path.suffix.lower() in {".toml"}:
            document = tomllib.loads(raw.decode("utf-8"))
        else:
            document = yaml.safe_load(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, yaml.YAMLError, UnicodeDecodeError) as error:
        raise ConfigError(f"Cannot parse configuration file {path}: {error}") from error

    if document is None:
        return {}
    if not isinstance(document, dict):
        raise ConfigError(f"{path}: the top-level configuration value must be a mapping.")
    return document


def _check_cookie_file(path_text: str, warnings: list[str]) -> None:
    path = Path(path_text)
    if not path.exists():
        raise ConfigError(f"Cookie file not found: {path}")
    if sys.platform == "win32":
        warnings.append(
            f"Cookie file {path} cannot be permission-checked on Windows; "
            "restrict access with file-system ACLs."
        )
        return
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        raise ConfigError(
            f"Cookie file {path} is accessible by other users (mode {mode:o}). "
            "Run: chmod 600 <cookie-file>"
        )


def _expand_home(text: str, env: Mapping[str, str]) -> str:
    if not text.startswith("~"):
        return text
    if text != "~" and not text.startswith(("~/", "~\\")):
        return text
    home = env.get("HOME") or env.get("USERPROFILE")
    if not home:
        return str(Path(text).expanduser())
    if text == "~":
        return home
    return str(Path(home) / text[2:])


def _expand_runtime_paths(config: AppConfig, env: Mapping[str, str]) -> None:
    config.cache.directory = _expand_home(config.cache.directory, env)
    config.storage.base_output_directory = _expand_home(config.storage.base_output_directory, env)
    config.storage.batch_export.links_file_path = _expand_home(
        config.storage.batch_export.links_file_path, env
    )
    config.storage.batch_export.manifest_file_path = _expand_home(
        config.storage.batch_export.manifest_file_path, env
    )
    if config.logging.file_path:
        config.logging.file_path = _expand_home(config.logging.file_path, env)
    for adapter in config.site_adapters.values():
        if adapter.cookie_file:
            adapter.cookie_file = _expand_home(adapter.cookie_file, env)


def load_config(
    *,
    explicit: str | Path | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> LoadedConfig:
    """Load, expand, and validate the configuration."""

    lookup = dict(os.environ) if env is None else dict(env)
    path = find_config_path(explicit=explicit, cwd=cwd, env=lookup)
    if path is None:
        return LoadedConfig(config=AppConfig(), path=None)

    document = _read_document(path)
    expanded = _expand_env(document, lookup, path)
    if not isinstance(expanded, dict):  # pragma: no cover - guarded by _read_document
        raise ConfigError(f"{path}: the top-level configuration value must be a mapping.")

    try:
        config = AppConfig.model_validate(expanded)
    except ValidationError as error:
        raise ConfigError(f"Invalid configuration in {path}:\n{_format_validation(error)}") from (
            error
        )

    warnings: list[str] = []
    _expand_runtime_paths(config, lookup)
    for name, adapter in config.site_adapters.items():
        if adapter.cookie_file:
            try:
                _check_cookie_file(adapter.cookie_file, warnings)
            except ConfigError as error:
                raise ConfigError(f"site_adapters.{name}: {error}") from error

    return LoadedConfig(config=config, path=path, warnings=tuple(warnings))


def _format_validation(error: ValidationError) -> str:
    lines: list[str] = []
    for issue in error.errors():
        location = ".".join(str(part) for part in issue["loc"]) or "<root>"
        lines.append(f"  {location}: {issue['msg']}")
    return "\n".join(lines)


def expand_path(path_text: str) -> Path:
    """Expand ``~`` and environment variables for a runtime path."""

    return Path(os.path.expandvars(path_text)).expanduser()
