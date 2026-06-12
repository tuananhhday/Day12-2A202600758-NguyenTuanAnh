"""Production-ready AI agent for Day 12 final project."""
import json
import logging
import signal
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import cost_guard
from app.rate_limiter import rate_limiter
from utils.mock_llm import ask as llm_ask

try:
    import redis
except Exception:  # pragma: no cover - dependency is present in Docker
    redis = None


logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0
_redis_client = None
_memory_history: dict[str, list[dict]] = {}


def _json_log(event: str, **fields):
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False))


def _get_redis():
    if redis is None or not settings.redis_url:
        return None
    return redis.from_url(settings.redis_url, decode_responses=True)


def _history_key(user_id: str) -> str:
    return f"history:{user_id}"


def _load_history(user_id: str) -> list[dict]:
    key = _history_key(user_id)
    if _redis_client is not None:
        raw_items = _redis_client.lrange(key, 0, -1)
        return [json.loads(item) for item in raw_items]
    return _memory_history.get(user_id, [])


def _append_history(user_id: str, role: str, content: str):
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    key = _history_key(user_id)
    if _redis_client is not None:
        _redis_client.rpush(key, json.dumps(message, ensure_ascii=False))
        _redis_client.ltrim(key, -20, -1)
        _redis_client.expire(key, 3600)
        return

    history = _memory_history.setdefault(user_id, [])
    history.append(message)
    if len(history) > 20:
        _memory_history[user_id] = history[-20:]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready, _redis_client
    _json_log(
        "startup",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
    _redis_client = _get_redis()
    if _redis_client is not None:
        _redis_client.ping()
        _json_log("redis_connected")
    else:
        _json_log("redis_unavailable_using_memory")
    _is_ready = True
    yield
    _is_ready = False
    _json_log("shutdown")
    if _redis_client is not None:
        _redis_client.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if "server" in response.headers:
            del response.headers["server"]
        _json_log(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=round((time.time() - start) * 1000, 1),
        )
        return response
    except Exception:
        _error_count += 1
        raise


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str = Field("default", min_length=1, max_length=100)


class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    model: str
    history_count: int
    timestamp: str


@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "ask": "POST /ask",
            "history": "GET /history/{user_id}",
            "health": "GET /health",
            "ready": "GET /ready",
        },
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    api_key: str = Depends(verify_api_key),
):
    rate_info = rate_limiter.check(body.user_id, api_key)
    input_tokens = len(body.question.split()) * 2
    cost_guard.check(body.user_id, input_tokens, 0)

    _append_history(body.user_id, "user", body.question)
    answer = llm_ask(body.question)
    output_tokens = len(answer.split()) * 2
    cost_guard.record(body.user_id, input_tokens, output_tokens)
    _append_history(body.user_id, "assistant", answer)
    history = _load_history(body.user_id)

    _json_log(
        "agent_response",
        user_id=body.user_id,
        question_length=len(body.question),
        history_count=len(history),
        rate_remaining=rate_info["remaining"],
        client=str(request.client.host) if request.client else "unknown",
    )
    return AskResponse(
        user_id=body.user_id,
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        history_count=len(history),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/history/{user_id}", tags=["Agent"])
def history(user_id: str, _api_key: str = Depends(verify_api_key)):
    messages = _load_history(user_id)
    return {"user_id": user_id, "messages": messages, "count": len(messages)}


@app.delete("/history/{user_id}", tags=["Agent"])
def clear_history(user_id: str, _api_key: str = Depends(verify_api_key)):
    if _redis_client is not None:
        _redis_client.delete(_history_key(user_id))
    else:
        _memory_history.pop(user_id, None)
    return {"deleted": user_id}


@app.get("/health", tags=["Operations"])
def health():
    redis_status = "not_configured"
    if _redis_client is not None:
        try:
            _redis_client.ping()
            redis_status = "ok"
        except Exception:
            redis_status = "error"
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": {
            "llm": "mock" if not settings.openai_api_key else "configured",
            "redis": redis_status,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    if _redis_client is not None:
        try:
            _redis_client.ping()
        except Exception:
            raise HTTPException(503, "Redis not ready")
    return {"ready": True}


@app.get("/metrics", tags=["Operations"])
def metrics(_api_key: str = Depends(verify_api_key)):
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "cost": cost_guard.stats(),
        "rate_limit_per_minute": settings.rate_limit_per_minute,
    }


def _handle_signal(signum, _frame):
    _json_log("signal", signum=signum)


signal.signal(signal.SIGTERM, _handle_signal)
