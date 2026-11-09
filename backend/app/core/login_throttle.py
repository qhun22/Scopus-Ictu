"""Limit on failed password logins (NFR-15).

After ``MAX_FAILURES`` wrong attempts for one email inside ``WINDOW_SECONDS``, further password
attempts for that email are refused until the oldest failure ages out, even with the right
password; otherwise the limit would not slow down guessing at all.

Keyed by email alone: behind the Vite proxy and Cloudflare Tunnel every request reaches this
process from 127.0.0.1, and forwarded-IP headers can be forged when the proxy is bypassed.
The cost is that someone can hold off password login for a given email for a few minutes;
Google Sign-In does not go through this limit.

State lives in this process, so it resets on restart and is per-worker: enough for the
single-worker deployment here, but a multi-worker deployment would need shared storage.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable

MAX_FAILURES = 5
WINDOW_SECONDS = 300
MAX_TRACKED_EMAILS = 10_000


class LoginThrottle:
    def __init__(
        self,
        *,
        max_failures: int = MAX_FAILURES,
        window_seconds: float = WINDOW_SECONDS,
        max_tracked: int = MAX_TRACKED_EMAILS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_failures = max_failures
        self._window = window_seconds
        self._max_tracked = max_tracked
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(email: str) -> str:
        return email.strip().lower()

    def retry_after(self, email: str) -> int:
        """Seconds until ``email`` may try again; 0 when it may try now."""

        with self._lock:
            failures = self._failures.get(self._key(email))
            if failures is None or len(failures) < self._max_failures:
                return 0
            remaining = failures[0] + self._window - self._clock()
            return math.ceil(remaining) if remaining > 0 else 0

    def record_failure(self, email: str) -> None:
        with self._lock:
            key = self._key(email)
            failures = self._failures.get(key)
            if failures is None:
                self._make_room()
                failures = self._failures[key] = deque(maxlen=self._max_failures)
            failures.append(self._clock())

    def clear(self, email: str) -> None:
        with self._lock:
            self._failures.pop(self._key(email), None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()

    def _make_room(self) -> None:
        """Keep guesses at random emails from growing this table without bound."""

        if len(self._failures) < self._max_tracked:
            return
        now = self._clock()
        expired = [k for k, f in self._failures.items() if now - f[-1] >= self._window]
        for key in expired:
            del self._failures[key]
        while len(self._failures) >= self._max_tracked:
            del self._failures[next(iter(self._failures))]


login_throttle = LoginThrottle()
