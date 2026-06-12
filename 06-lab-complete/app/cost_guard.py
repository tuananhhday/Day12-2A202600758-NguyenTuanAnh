"""Daily budget guard for estimated LLM cost."""
import time
from collections import defaultdict

from fastapi import HTTPException

from app.config import settings

try:
    import redis
except Exception:  # pragma: no cover
    redis = None


INPUT_PRICE_PER_1K = 0.00015
OUTPUT_PRICE_PER_1K = 0.0006


class CostGuard:
    def __init__(self):
        self.daily_budget = settings.daily_budget_usd
        self._costs = defaultdict(float)
        self._redis = None
        if redis is not None and settings.redis_url:
            try:
                self._redis = redis.from_url(settings.redis_url, decode_responses=True)
                self._redis.ping()
            except Exception:
                self._redis = None

    def _today(self) -> str:
        return time.strftime("%Y-%m-%d")

    def _key(self, user_id: str) -> str:
        return f"cost:{user_id}:{self._today()}"

    def _estimate(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens / 1000 * INPUT_PRICE_PER_1K
            + output_tokens / 1000 * OUTPUT_PRICE_PER_1K
        )

    def _current(self, user_id: str) -> float:
        key = self._key(user_id)
        if self._redis is not None:
            return float(self._redis.get(key) or 0)
        return self._costs[key]

    def check(self, user_id: str, input_tokens: int, output_tokens: int):
        estimated = self._estimate(input_tokens, output_tokens)
        current = self._current(user_id)
        if current + estimated > self.daily_budget:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "Daily budget exceeded",
                    "used_usd": round(current, 6),
                    "budget_usd": self.daily_budget,
                },
            )

    def record(self, user_id: str, input_tokens: int, output_tokens: int):
        cost = self._estimate(input_tokens, output_tokens)
        key = self._key(user_id)
        if self._redis is not None:
            self._redis.incrbyfloat(key, cost)
            self._redis.expire(key, 32 * 24 * 3600)
        else:
            self._costs[key] += cost
        return self._current(user_id)

    def stats(self) -> dict:
        if self._redis is not None:
            return {"storage": "redis", "daily_budget_usd": self.daily_budget}
        return {
            "storage": "memory",
            "daily_budget_usd": self.daily_budget,
            "tracked_keys": len(self._costs),
        }


cost_guard = CostGuard()
