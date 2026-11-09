from __future__ import annotations

import pytest

from manji.errors import AccessDeniedError, ChallengeDetectedError
from manji.net.challenge import is_challenge, raise_for_challenge
from tests.conftest import load_fixture

pytestmark = [pytest.mark.unit, pytest.mark.compliance]

CHALLENGE_HTML = load_fixture("mock_json", "challenge.html")


@pytest.mark.parametrize(
    ("status", "headers", "body", "expected"),
    [
        (403, {}, CHALLENGE_HTML, True),
        (503, {}, CHALLENGE_HTML, True),
        (403, {"cf-mitigated": "challenge"}, "", True),
        (403, {}, "<html>Forbidden</html>", False),
        (200, {}, CHALLENGE_HTML, False),
        (500, {}, CHALLENGE_HTML, False),
        (403, {}, "<div class='g-recaptcha'></div>", True),
        (403, {"Server": "cloudflare"}, "", True),
    ],
)
def test_challenge_detection(
    status: int, headers: dict[str, str], body: str, expected: bool
) -> None:
    assert is_challenge(status, headers, body) is expected


def test_challenge_error_contains_handoff_message() -> None:
    with pytest.raises(ChallengeDetectedError) as excinfo:
        raise_for_challenge(
            status_code=403,
            headers={},
            body=CHALLENGE_HTML,
            url="https://mock-json.test/series/example",
            domain="mock-json.test",
        )
    message = str(excinfo.value)
    assert "mock-json.test" in message
    assert "browser" in message
    assert excinfo.value.exit_code == 4


def test_plain_denial_is_not_a_challenge() -> None:
    with pytest.raises(AccessDeniedError, match="not retried"):
        raise_for_challenge(
            status_code=403,
            headers={},
            body="<html>Forbidden</html>",
            url="https://mock-json.test/series/example",
            domain="mock-json.test",
        )
