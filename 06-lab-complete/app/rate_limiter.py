"""Redis-backed rate limiter with in-memory fallback."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException

from app.config import settings

try:
    import redis
except Exception:  # pragma: no cover
    redis = None


class RateLimiter:
    def __init__(self):
        self.limit = settings.rate_limit_per_minute
        self.window_seconds = 60
        self._windows: dict[str, deque] = defaultdict(deque)
        self._redis = None
        if redis is not None and settings.redis_url:
            try:
                self._redis = redis.from_url(settings.redis_url, decode_responses=True)
                self._redis.ping()
            except Exception:
                self._redis = None

    def check(self, user_id: str, api_key: str) -> dict:
        bucket = f"{user_id}:{api_key[:8]}"
        if self._redis is not None:
            return self._check_redis(bucket)
        return self._check_memory(bucket)

    def _check_redis(self, bucket: str) -> dict:
        now = time.time()
        key = f"rate:{bucket}"
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - self.window_seconds)
        pipe.zcard(key)
        _, current = pipe.execute()
        if current >= self.limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": self.limit,
                    "window_seconds": self.window_seconds,
                },
            )
        self._redis.zadd(key, {str(now): now})
        self._redis.expire(key, self.window_seconds)
        return {"limit": self.limit, "remaining": self.limit - current - 1}

    def _check_memory(self, bucket: str) -> dict:
        now = time.time()
        window = self._windows[bucket]
        while window and window[0] < now - self.window_seconds:
            window.popleft()
        if len(window) >= self.limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": self.limit,
                    "window_seconds": self.window_seconds,
                },
            )
        window.append(now)
        return {"limit": self.limit, "remaining": self.limit - len(window)}


rate_limiter = RateLimiter()
