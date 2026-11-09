"""Per-domain concurrency limit, delay, and blocking."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Protocol


class Clock(Protocol):
    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    """Real clock used in production."""

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


class FakeClock:
    """Deterministic clock for tests. ``sleep`` advances virtual time."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self._now

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            self.sleeps.append(seconds)
            self._now += seconds

    def advance(self, seconds: float) -> None:
        self._now += seconds


@dataclass(slots=True)
class DomainState:
    """Mutable per-host limiter state."""

    next_allowed: float = 0.0
    blocked_until: float = 0.0
    min_delay: float = 0.0
    crawl_delay: float | None = None
    semaphore: threading.BoundedSemaphore = field(
        default_factory=lambda: threading.BoundedSemaphore(2)
    )

    def effective_delay(self) -> float:
        if self.crawl_delay is None:
            return self.min_delay
        return max(self.min_delay, self.crawl_delay)


class DomainLimiter:
    """Independent limiter state per domain with an injectable clock."""

    def __init__(
        self,
        *,
        max_concurrency: int = 2,
        default_delay: float = 1.5,
        clock: Clock | None = None,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1.")
        if default_delay < 0:
            raise ValueError("default_delay must not be negative.")
        self._max_concurrency = max_concurrency
        self._default_delay = default_delay
        self._clock: Clock = clock or SystemClock()
        self._states: dict[str, DomainState] = {}
        self._lock = threading.Lock()

    def _state(self, domain: str) -> DomainState:
        with self._lock:
            state = self._states.get(domain)
            if state is None:
                state = DomainState(
                    min_delay=self._default_delay,
                    semaphore=threading.BoundedSemaphore(self._max_concurrency),
                )
                self._states[domain] = state
            return state

    def set_delay(self, domain: str, delay: float) -> None:
        if delay < 0:
            raise ValueError("delay must not be negative.")
        state = self._state(domain)
        with self._lock:
            state.min_delay = delay

    def get_delay(self, domain: str) -> float:
        return self._state(domain).effective_delay()

    def set_crawl_delay(self, domain: str, crawl_delay: float | None) -> None:
        if crawl_delay is not None and crawl_delay < 0:
            raise ValueError("crawl_delay must not be negative.")
        state = self._state(domain)
        with self._lock:
            state.crawl_delay = crawl_delay

    def block(self, domain: str, seconds: float) -> None:
        """Block every request for this domain until ``seconds`` have passed."""

        state = self._state(domain)
        with self._lock:
            until = self._clock.monotonic() + max(0.0, seconds)
            state.blocked_until = max(state.blocked_until, until)

    def blocked_for(self, domain: str) -> float:
        state = self._state(domain)
        with self._lock:
            remaining = state.blocked_until - self._clock.monotonic()
        return max(0.0, remaining)

    def acquire(self, domain: str, *, wait: bool = True) -> bool:
        """Acquire a concurrency slot and enforce the domain delay."""

        state = self._state(domain)
        acquired = state.semaphore.acquire(timeout=-1 if wait else 0)
        if not acquired:
            return False
        try:
            self._wait_for_slot(state)
        except BaseException:
            state.semaphore.release()
            raise
        return True

    def release(self, domain: str) -> None:
        self._state(domain).semaphore.release()

    def _wait_for_slot(self, state: DomainState) -> None:
        while True:
            now = self._clock.monotonic()
            wait_until = max(state.next_allowed, state.blocked_until)
            if wait_until <= now:
                with self._lock:
                    state.next_allowed = now + state.effective_delay()
                return
            self._clock.sleep(wait_until - now)

    @contextmanager
    def slot(self, domain: str) -> Iterator[None]:
        """Context manager wrapping ``acquire``/``release``."""

        self.acquire(domain)
        try:
            yield
        finally:
            self.release(domain)
