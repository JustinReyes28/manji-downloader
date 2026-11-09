from __future__ import annotations

import pytest

from manji.net.limiter import DomainLimiter, FakeClock

pytestmark = pytest.mark.unit


def test_limiter_enforces_delay_between_requests() -> None:
    clock = FakeClock()
    limiter = DomainLimiter(max_concurrency=2, default_delay=1.5, clock=clock)

    limiter.acquire("a.test")
    limiter.release("a.test")
    limiter.acquire("a.test")
    limiter.release("a.test")

    assert clock.sleeps == [1.5]


def test_domains_are_independent() -> None:
    clock = FakeClock()
    limiter = DomainLimiter(max_concurrency=2, default_delay=2.0, clock=clock)

    limiter.acquire("a.test")
    limiter.release("a.test")
    limiter.acquire("b.test")
    limiter.release("b.test")

    assert clock.sleeps == []


def test_crawl_delay_overrides_when_larger() -> None:
    clock = FakeClock()
    limiter = DomainLimiter(max_concurrency=2, default_delay=1.0, clock=clock)
    limiter.set_crawl_delay("a.test", 3.0)
    assert limiter.get_delay("a.test") == 3.0

    limiter.acquire("a.test")
    limiter.release("a.test")
    limiter.acquire("a.test")
    limiter.release("a.test")
    assert clock.sleeps == [3.0]


def test_configured_delay_wins_when_larger() -> None:
    limiter = DomainLimiter(max_concurrency=2, default_delay=5.0, clock=FakeClock())
    limiter.set_crawl_delay("a.test", 1.0)
    assert limiter.get_delay("a.test") == 5.0


def test_block_prevents_requests_until_expiry() -> None:
    clock = FakeClock()
    limiter = DomainLimiter(max_concurrency=2, default_delay=0.0, clock=clock)
    limiter.block("a.test", 10.0)

    assert limiter.blocked_for("a.test") == 10.0
    limiter.acquire("a.test")
    limiter.release("a.test")
    assert clock.sleeps == [10.0]
    assert limiter.blocked_for("a.test") == 0.0


def test_block_extends_to_the_later_deadline() -> None:
    clock = FakeClock()
    limiter = DomainLimiter(default_delay=0.0, clock=clock)
    limiter.block("a.test", 5.0)
    limiter.block("a.test", 2.0)
    assert limiter.blocked_for("a.test") == 5.0

    limiter.block("a.test", 7.0)
    assert limiter.blocked_for("a.test") == 7.0


def test_non_blocking_acquire_reports_contention() -> None:
    limiter = DomainLimiter(max_concurrency=1, default_delay=0.0, clock=FakeClock())
    assert limiter.acquire("a.test", wait=False) is True
    assert limiter.acquire("a.test", wait=False) is False
    limiter.release("a.test")
    assert limiter.acquire("a.test", wait=False) is True
    limiter.release("a.test")


def test_release_without_acquire_is_rejected() -> None:
    limiter = DomainLimiter(max_concurrency=1, default_delay=0.0, clock=FakeClock())
    limiter.acquire("a.test")
    limiter.release("a.test")
    with pytest.raises(ValueError, match=r"[Ss]emaphore"):
        limiter.release("a.test")


def test_invalid_construction() -> None:
    with pytest.raises(ValueError, match="max_concurrency"):
        DomainLimiter(max_concurrency=0)
    with pytest.raises(ValueError, match="default_delay"):
        DomainLimiter(default_delay=-1)


def test_invalid_delay_setters() -> None:
    limiter = DomainLimiter(default_delay=0.0, clock=FakeClock())
    with pytest.raises(ValueError, match="delay"):
        limiter.set_delay("a.test", -1)
    with pytest.raises(ValueError, match="crawl_delay"):
        limiter.set_crawl_delay("a.test", -1)


def test_slot_context_manager_releases() -> None:
    limiter = DomainLimiter(max_concurrency=1, default_delay=0.0, clock=FakeClock())
    with limiter.slot("a.test"):
        pass
    with limiter.slot("a.test"):
        pass
