"""Anti-bot challenge detection for safe halting."""

from __future__ import annotations

from collections.abc import Mapping

from manji.errors import AccessDeniedError, ChallengeDetectedError

_CHALLENGE_MARKERS = (
    "cf-chl-",
    "cf_chl_",
    "challenge-platform",
    "cf-browser-verification",
    "attention required! | cloudflare",
    "just a moment...",
    "checking your browser",
    "captcha",
    "g-recaptcha",
    "h-captcha",
    "hcaptcha",
    "ddos-guard",
    "sucuri website firewall",
)

_CHALLENGE_STATUSES = frozenset({403, 503})

MANUAL_HANDOFF_MESSAGE = (
    "A verification challenge was detected on {domain}. Manji Downloader does not bypass "
    "anti-bot challenges. Open {url} in your normal browser, complete the challenge or sign in "
    "manually, then update your local session cookies and rerun the command."
)


def is_challenge(status_code: int, headers: Mapping[str, str], body: str = "") -> bool:
    """Return ``True`` when a response looks like an anti-bot challenge page."""

    lowered_headers = {key.lower(): value for key, value in headers.items()}
    if "cf-mitigated" in lowered_headers:
        return True
    if status_code not in _CHALLENGE_STATUSES:
        return False
    haystack = body.lower()
    if any(marker in haystack for marker in _CHALLENGE_MARKERS):
        return True
    server = lowered_headers.get("server", "").lower()
    return "cloudflare" in server and status_code == 403


def raise_for_challenge(
    *, status_code: int, headers: Mapping[str, str], body: str, url: str, domain: str
) -> None:
    """Raise the challenge error when detected; otherwise raise a plain denial."""

    if is_challenge(status_code, headers, body):
        raise ChallengeDetectedError(MANUAL_HANDOFF_MESSAGE.format(domain=domain, url=url))
    raise AccessDeniedError(
        f"Access denied by {domain} with HTTP {status_code}. "
        "Verify your credentials or permissions; this request was not retried."
    )
