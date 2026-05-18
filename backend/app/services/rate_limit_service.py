from time import time

from fastapi import HTTPException, status

from app.core.config import settings
from app.services.cache_service import CacheService

_memory_buckets: dict[str, tuple[int, float]] = {}


class RateLimitService:
    def __init__(self) -> None:
        self.cache = CacheService()

    def check(self, *, key: str, limit: int, window_seconds: int) -> None:
        if not settings.rate_limit_enabled:
            return

        redis_count = self.cache.increment(f"rate_limit:{key}", ttl_seconds=window_seconds)
        count = redis_count if redis_count is not None else self._increment_memory(key, window_seconds)
        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again shortly.",
            )

    def _increment_memory(self, key: str, window_seconds: int) -> int:
        now = time()
        count, reset_at = _memory_buckets.get(key, (0, now + window_seconds))
        if now >= reset_at:
            count, reset_at = 0, now + window_seconds
        count += 1
        _memory_buckets[key] = (count, reset_at)
        return count
