"""Logging configuration and redaction integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from manji.config.models import LoggingConfig, LogLevel

if TYPE_CHECKING:
    from manji.net.redaction import Sanitizer

LOGGER_NAME = "manji"

_LEVELS = {
    LogLevel.DEBUG: logging.DEBUG,
    LogLevel.INFO: logging.INFO,
    LogLevel.WARN: logging.WARNING,
    LogLevel.ERROR: logging.ERROR,
}


def configure_logging(
    config: LoggingConfig | None = None,
    *,
    sanitizer: Sanitizer | None = None,
    force: bool = False,
) -> logging.Logger:
    """Configure the ``manji`` logger once and return it."""

    # Imported lazily: ``manji.net`` imports ``get_logger`` from this module.
    from manji.net.redaction import RedactionFilter

    settings = config or LoggingConfig()
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(_LEVELS[settings.level])
    logger.propagate = False

    if logger.handlers and not force:
        return logger

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    redaction = RedactionFilter(sanitizer) if settings.sanitize_secrets else None
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
    )

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    if redaction is not None:
        stream.addFilter(redaction)
    logger.addHandler(stream)

    if settings.file_path:
        path = Path(settings.file_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(path, encoding="utf-8")
        except OSError:
            logger.debug("Could not open log file %s; using stderr only.", path)
        else:
            file_handler.setFormatter(formatter)
            if redaction is not None:
                file_handler.addFilter(redaction)
            logger.addHandler(file_handler)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}" if name else LOGGER_NAME)
