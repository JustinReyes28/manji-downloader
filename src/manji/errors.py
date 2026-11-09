"""Exception hierarchy and CLI exit-code mapping."""

from __future__ import annotations

from typing import ClassVar


class ManjiError(Exception):
    """Base class for expected Manji failures."""

    exit_code: ClassVar[int] = 1


class UnsupportedSiteError(ManjiError):
    """The pasted URL does not match any registered adapter."""

    exit_code = 3


class AccessNotConfiguredError(ManjiError):
    """Credentials required by the adapter have not been supplied."""

    exit_code = 4


class AccessDeniedError(ManjiError):
    """The remote host denied the request with 401 or 403."""

    exit_code = 4


class ChallengeDetectedError(ManjiError):
    """An anti-bot challenge was detected; automated access must stop."""

    exit_code = 4


class RobotsDisallowedError(ManjiError):
    """robots.txt disallows the requested path."""

    exit_code = 4


class RateLimitedError(ManjiError):
    """The remote host rate-limited the request."""

    exit_code = 5

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ConfigError(ManjiError):
    """Configuration could not be found, parsed, or validated."""

    exit_code = 2


class RangeParseError(ManjiError):
    """An episode/item range expression is invalid."""

    exit_code = 2


class SelectionError(ManjiError):
    """A selection could not be resolved."""

    exit_code = 2


class NoVariantsError(ManjiError):
    """No file variants exist for a selected item."""

    exit_code = 6


class NoQualityMatchError(ManjiError):
    """No available quality satisfies the requested preferences."""

    exit_code = 6


class DownloadError(ManjiError):
    """A download failed or could not be written safely."""

    exit_code = 6


class RobotsUnavailableError(ManjiError):
    """robots.txt could not be retrieved, so the client fails closed."""

    exit_code = 5


class NetworkError(ManjiError):
    """A transport-level network failure occurred."""

    exit_code = 5


class HTTPError(ManjiError):
    """The remote host returned an unusable HTTP response."""

    exit_code = 5

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
