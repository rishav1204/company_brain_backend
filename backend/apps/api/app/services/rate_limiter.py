from dataclasses import dataclass
from time import time


@dataclass
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class FixedWindowRateLimiter:
    def __init__(self, limit_per_minute: int = 1000) -> None:
        self.limit_per_minute = limit_per_minute
        self._windows: dict[str, tuple[int, int]] = {}

    def check(self, key: str) -> RateLimitDecision:
        now = int(time())
        window = now // 60
        stored = self._windows.get(key)
        if stored is None or stored[0] != window:
            self._windows[key] = (window, 1)
            return RateLimitDecision(allowed=True, remaining=self.limit_per_minute - 1, retry_after_seconds=0)

        _, count = stored
        if count >= self.limit_per_minute:
            retry_after = 60 - (now % 60)
            return RateLimitDecision(allowed=False, remaining=0, retry_after_seconds=retry_after)

        count += 1
        self._windows[key] = (window, count)
        return RateLimitDecision(allowed=True, remaining=self.limit_per_minute - count, retry_after_seconds=0)


rate_limiter = FixedWindowRateLimiter(limit_per_minute=1000)
