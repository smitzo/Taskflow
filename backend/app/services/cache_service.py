import json
from typing import Any

from app.core.config import settings


class CacheService:
    def __init__(self) -> None:
        self._client = None
        if not settings.cache_enabled:
            return
        try:
            import redis

            self._client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=0.1,
                socket_timeout=0.1,
            )
        except Exception:
            self._client = None

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def get_json(self, key: str) -> dict[str, Any] | list[Any] | None:
        if self._client is None:
            return None
        try:
            value = self._client.get(key)
        except Exception:
            return None
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    def set_json(self, key: str, value: dict[str, Any] | list[Any], ttl_seconds: int | None = None) -> None:
        if self._client is None:
            return
        try:
            self._client.setex(key, ttl_seconds or settings.cache_ttl_seconds, json.dumps(value, default=str))
        except Exception:
            return

    def delete(self, *keys: str) -> None:
        if self._client is None or not keys:
            return
        try:
            self._client.delete(*keys)
        except Exception:
            return

    def delete_pattern(self, pattern: str) -> None:
        if self._client is None:
            return
        try:
            keys = list(self._client.scan_iter(match=pattern))
            if keys:
                self._client.delete(*keys)
        except Exception:
            return
