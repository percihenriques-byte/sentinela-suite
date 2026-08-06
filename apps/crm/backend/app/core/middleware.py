"""HTTP middleware: request IDs + in-memory token-bucket rate limiting.

Rate limiter is intentionally simple (in-process, per-worker) — good enough for
single-node deployments and dev. For horizontal scaling swap in Redis.
"""
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Callable, Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging import request_id_var, user_id_var

logger = logging.getLogger("jarvis.http")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming = request.headers.get("x-request-id")
        rid = incoming if incoming and len(incoming) <= 64 else uuid.uuid4().hex
        rid_token = request_id_var.set(rid)
        user_token = None

        # Best-effort: read user id from JWT so log lines carry it. Auth still
        # runs through the dependency chain — we never trust this for authz.
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            try:
                from app.core.security import decode_token
                payload = decode_token(auth.split(" ", 1)[1])
                if payload.get("sub"):
                    user_token = user_id_var.set(payload["sub"])
            except Exception:
                pass

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled_exception path=%s", request.url.path)
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "http path=%s method=%s ms=%.1f",
                request.url.path,
                request.method,
                elapsed_ms,
            )
            if user_token is not None:
                user_id_var.reset(user_token)
            request_id_var.reset(rid_token)
        response.headers["x-request-id"] = rid
        return response


@dataclass
class _Bucket:
    tokens: float
    updated_at: float | None  # None until first hit — avoids ambiguity with 0.0


@dataclass
class TokenBucketConfig:
    """`capacity` tokens refilled at `refill_per_sec` per second."""
    capacity: float
    refill_per_sec: float


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-key token bucket, keyed by (client_ip, first_matching_prefix).

    Skips paths that don't match any rule. Returns 429 when the bucket is empty.
    """

    def __init__(self, app, rules: Iterable[tuple[str, TokenBucketConfig]]):
        super().__init__(app)
        self._rules = list(rules)
        self._buckets: dict[tuple[str, str], _Bucket] = defaultdict(lambda: _Bucket(0.0, None))
        self._lock = Lock()

    def _match(self, path: str) -> tuple[str, TokenBucketConfig] | None:
        for prefix, cfg in self._rules:
            if path.startswith(prefix):
                return prefix, cfg
        return None

    def _consume(self, key: tuple[str, str], cfg: TokenBucketConfig) -> tuple[bool, float]:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets[key]
            # Sentinel: `updated_at is None` means "never seen this key".
            # Previously we used 0.0 which is theoretically indistinguishable
            # from a real early-boot monotonic value.
            if bucket.updated_at is None:
                bucket.tokens = cfg.capacity
                bucket.updated_at = now
            else:
                elapsed = now - bucket.updated_at
                bucket.tokens = min(cfg.capacity, bucket.tokens + elapsed * cfg.refill_per_sec)
                bucket.updated_at = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True, bucket.tokens
            deficit = 1.0 - bucket.tokens
            retry_after = deficit / cfg.refill_per_sec if cfg.refill_per_sec > 0 else 60.0
            return False, retry_after

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        match = self._match(request.url.path)
        if match is None:
            return await call_next(request)
        prefix, cfg = match
        # Prefer the leftmost X-Forwarded-For entry when present (common behind
        # nginx/gunicorn/Cloudflare). Falls back to the direct peer address.
        # Without this, every request coming through a reverse proxy would share
        # the proxy's IP and hit the rate limit almost immediately in prod.
        xff = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        client_ip = xff or (request.client.host if request.client else "unknown")
        key = (client_ip, prefix)
        allowed, info = self._consume(key, cfg)
        if not allowed:
            return JSONResponse(
                {"detail": "Rate limit exceeded", "retry_after_seconds": round(info, 2)},
                status_code=429,
                headers={"Retry-After": str(max(1, int(round(info))))},
            )
        response = await call_next(request)
        return response


def default_rate_limits() -> list[tuple[str, TokenBucketConfig]]:
    """Baseline limits — deliberately generous; tighten per deployment.

    Auth endpoints get a stricter bucket to slow brute-force attempts.
    Jarvis endpoints get a moderate cap to keep one runaway client from
    monopolising the local engine.
    """
    return [
        ("/api/v1/auth/login", TokenBucketConfig(capacity=10, refill_per_sec=10 / 60)),
        ("/api/v1/auth/register", TokenBucketConfig(capacity=5, refill_per_sec=5 / 300)),
        ("/api/v1/jarvis", TokenBucketConfig(capacity=30, refill_per_sec=30 / 60)),
        # Restore endpoint — allow bursts (undo-click after delete) but cap sustained abuse
        ("/api/v1/restore", TokenBucketConfig(capacity=20, refill_per_sec=20 / 60)),
        # Sentinela ingestion — the only route reachable without a login (it
        # authenticates with the ingest token and only from loopback). A burst
        # of 60 covers "send the whole backlog" (200 events per request) while
        # capping a flood from a local process guessing tokens.
        ("/api/v1/sentinela/eventos", TokenBucketConfig(capacity=60, refill_per_sec=60 / 60)),
    ]
