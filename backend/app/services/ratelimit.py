"""A small in-memory sliding-window limiter.

The join code is four digits: ten thousand of them, which an authenticated
client can walk in under a minute and read every bill that happens to be open.
Counting lookups per user is what makes that walk take longer than any bill
stays open.

State lives in the process — the API runs as a single uvicorn worker, and a
counter that resets on deploy is still the difference between ten thousand
tries and a few dozen.
"""

import time
from collections import deque

# Stop tracking a key once its window has been empty this long, so a bot
# hammering with fresh ids can't grow the map without bound.
_SWEEP_EVERY_SECONDS = 300.0


class SlidingWindowLimiter:
    """Allow `limit` hits per key per `window_seconds`."""

    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[object, deque[float]] = {}
        self._last_sweep = time.monotonic()

    def hit(self, key: object) -> bool:
        """Record one attempt. Returns False once the key is over its limit."""
        now = time.monotonic()
        self._sweep(now)

        window = self._hits.setdefault(key, deque())
        cutoff = now - self.window
        while window and window[0] <= cutoff:
            window.popleft()

        if len(window) >= self.limit:
            return False

        window.append(now)
        return True

    def _sweep(self, now: float) -> None:
        if now - self._last_sweep < _SWEEP_EVERY_SECONDS:
            return
        self._last_sweep = now
        cutoff = now - self.window
        for key in [k for k, w in self._hits.items() if not w or w[-1] <= cutoff]:
            del self._hits[key]
