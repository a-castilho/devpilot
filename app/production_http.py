from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import hashlib
import json
import logging
import os
import time
from urllib.parse import parse_qsl, urlencode

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from redis import asyncio as redis_async
from starlette.middleware.base import BaseHTTPMiddleware


logger = logging.getLogger(__name__)

_BYPASS_PREFIXES = ("/assets/", "/static/", "/docs", "/redoc", "/openapi.json")
_SENSITIVE_TOKENS = ("/auth", "/login", "/logout", "/password", "/token", "/bootstrap", "/reset")
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(value or default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True, slots=True)
class ProductionHttpConfig:
    redis_url: str
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    auth_rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 60
    cache_enabled: bool = True
    cache_ttl_seconds: int = 30
    cache_max_body_bytes: int = 1_048_576
    trust_proxy_headers: bool = False
    key_prefix: str = "app"

    @classmethod
    def from_env(cls, prefix: str, key_prefix: str) -> "ProductionHttpConfig":
        env = os.environ.get
        return cls(
            redis_url=env(f"{prefix}_REDIS_URL", "").strip(),
            rate_limit_enabled=_as_bool(env(f"{prefix}_RATE_LIMIT_ENABLED"), True),
            rate_limit_requests=_as_int(env(f"{prefix}_RATE_LIMIT_REQUESTS"), 120),
            auth_rate_limit_requests=_as_int(env(f"{prefix}_AUTH_RATE_LIMIT_REQUESTS"), 10),
            rate_limit_window_seconds=_as_int(env(f"{prefix}_RATE_LIMIT_WINDOW_SECONDS"), 60),
            cache_enabled=_as_bool(env(f"{prefix}_CACHE_ENABLED"), True),
            cache_ttl_seconds=_as_int(env(f"{prefix}_CACHE_TTL_SECONDS"), 30),
            cache_max_body_bytes=_as_int(env(f"{prefix}_CACHE_MAX_BODY_BYTES"), 1_048_576),
            trust_proxy_headers=_as_bool(env(f"{prefix}_TRUST_PROXY_HEADERS"), False),
            key_prefix=key_prefix,
        )


class ProductionHttpMiddleware(BaseHTTPMiddleware):
    """Shared rate limiting and short-lived server cache for production HTTP traffic.

    Redis is used when configured so limits/cache are shared across replicas. If Redis is
    temporarily unavailable, the middleware degrades to bounded in-process memory instead of
    taking the API down.
    """

    def __init__(self, app, config: ProductionHttpConfig):
        super().__init__(app)
        self.config = config
        self._redis = (
            redis_async.from_url(
                config.redis_url,
                decode_responses=False,
                socket_connect_timeout=0.25,
                socket_timeout=0.25,
                health_check_interval=30,
            )
            if config.redis_url
            else None
        )
        self._memory_lock = asyncio.Lock()
        self._memory_rates: dict[str, tuple[int, float]] = {}
        self._memory_cache: dict[str, tuple[float, bytes]] = {}
        self._memory_generation = 1
        self._redis_warning_emitted = False

    async def dispatch(self, request: Request, call_next):
        rate = None
        if self.config.rate_limit_enabled and self._should_rate_limit(request):
            rate = await self._rate_limit(request)
            if rate["count"] > rate["limit"]:
                retry_after = max(1, rate["reset"] - int(time.time()))
                return JSONResponse(
                    status_code=429,
                    content={"detail": "rate_limit_exceeded", "retry_after": retry_after},
                    headers=self._rate_headers(rate, retry_after=retry_after),
                )

        cache_key = None
        if self.config.cache_enabled and self._cacheable_request(request):
            generation = await self._cache_generation()
            cache_key = self._cache_key(request, generation)
            cached = await self._cache_get(cache_key)
            if cached is not None:
                response = self._decode_cached_response(cached)
                response.headers["X-Cache"] = "HIT"
                if rate:
                    self._apply_rate_headers(response, rate)
                return response

        response = await call_next(request)

        if (
            request.method.upper() in _MUTATING_METHODS
            and response.status_code < 400
            and self.config.cache_enabled
        ):
            await self._bump_cache_generation()

        if rate:
            self._apply_rate_headers(response, rate)

        if cache_key is not None:
            cached_response = await self._maybe_cache_response(response, cache_key)
            if cached_response is not None:
                cached_response.headers["X-Cache"] = "MISS"
                return cached_response
            response.headers["X-Cache"] = "BYPASS"

        return response

    def _should_rate_limit(self, request: Request) -> bool:
        path = request.url.path.lower()
        if request.method.upper() == "OPTIONS":
            return False
        if path in {"/", "/health"}:
            return False
        return not path.startswith(_BYPASS_PREFIXES)

    def _cacheable_request(self, request: Request) -> bool:
        if request.method.upper() != "GET":
            return False
        path = request.url.path.lower()
        if path in {"/", "/health"} or path.startswith(_BYPASS_PREFIXES):
            return False
        return not any(token in path for token in _SENSITIVE_TOKENS)

    def _is_auth_sensitive(self, request: Request) -> bool:
        path = request.url.path.lower()
        return request.method.upper() in _MUTATING_METHODS and any(
            token in path for token in _SENSITIVE_TOKENS
        )

    def _client_ip(self, request: Request) -> str:
        if self.config.trust_proxy_headers:
            forwarded = request.headers.get("x-forwarded-for", "")
            if forwarded:
                return forwarded.split(",", 1)[0].strip()
        return request.client.host if request.client else "unknown"

    def _identity(self, request: Request, *, auth_sensitive: bool = False) -> str:
        if auth_sensitive:
            raw = self._client_ip(request)
            kind = "ip"
        else:
            authorization = request.headers.get("authorization", "").strip()
            cookie = request.headers.get("cookie", "").strip()
            if authorization:
                raw, kind = authorization, "auth"
            elif cookie:
                raw, kind = cookie, "cookie"
            else:
                raw, kind = self._client_ip(request), "ip"
        digest = hashlib.sha256(raw.encode("utf-8", "ignore")).hexdigest()[:24]
        return f"{kind}:{digest}"

    async def _rate_limit(self, request: Request) -> dict[str, int]:
        window = self.config.rate_limit_window_seconds
        now = int(time.time())
        bucket = now // window
        reset = (bucket + 1) * window
        auth_sensitive = self._is_auth_sensitive(request)
        limit = (
            self.config.auth_rate_limit_requests
            if auth_sensitive
            else self.config.rate_limit_requests
        )
        identity = self._identity(request, auth_sensitive=auth_sensitive)
        scope = "auth" if auth_sensitive else "api"
        key = f"{self.config.key_prefix}:rate:{scope}:{identity}:{bucket}"

        count = None
        if self._redis is not None:
            try:
                pipe = self._redis.pipeline(transaction=True)
                pipe.incr(key)
                pipe.expire(key, window * 2)
                result = await pipe.execute()
                count = int(result[0])
                self._redis_warning_emitted = False
            except Exception as exc:  # pragma: no cover - depends on external Redis
                self._warn_redis(exc)

        if count is None:
            count = await self._memory_rate_count(key, reset + window)

        return {"limit": limit, "count": count, "reset": reset}

    async def _memory_rate_count(self, key: str, expires_at: float) -> int:
        async with self._memory_lock:
            self._cleanup_memory_locked()
            current, current_expiry = self._memory_rates.get(key, (0, expires_at))
            if current_expiry <= time.time():
                current = 0
            current += 1
            self._memory_rates[key] = (current, expires_at)
            self._trim_memory_locked(self._memory_rates, 4096)
            return current

    def _rate_headers(self, rate: dict[str, int], retry_after: int | None = None) -> dict[str, str]:
        headers = {
            "X-RateLimit-Limit": str(rate["limit"]),
            "X-RateLimit-Remaining": str(max(0, rate["limit"] - rate["count"])),
            "X-RateLimit-Reset": str(rate["reset"]),
        }
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        return headers

    def _apply_rate_headers(self, response: Response, rate: dict[str, int]) -> None:
        for name, value in self._rate_headers(rate).items():
            response.headers[name] = value

    async def _cache_generation(self) -> int:
        key = f"{self.config.key_prefix}:cache:generation"
        if self._redis is not None:
            try:
                value = await self._redis.get(key)
                if value is None:
                    await self._redis.set(key, b"1", nx=True)
                    return 1
                self._redis_warning_emitted = False
                return int(value)
            except Exception as exc:  # pragma: no cover - depends on external Redis
                self._warn_redis(exc)
        return self._memory_generation

    async def _bump_cache_generation(self) -> None:
        key = f"{self.config.key_prefix}:cache:generation"
        if self._redis is not None:
            try:
                await self._redis.incr(key)
                self._redis_warning_emitted = False
                return
            except Exception as exc:  # pragma: no cover - depends on external Redis
                self._warn_redis(exc)
        async with self._memory_lock:
            self._memory_generation += 1
            self._memory_cache.clear()

    def _cache_key(self, request: Request, generation: int) -> str:
        query = urlencode(sorted(parse_qsl(request.url.query, keep_blank_values=True)))
        authorization = request.headers.get("authorization", "").strip()
        cookie = request.headers.get("cookie", "").strip()
        principal = authorization or cookie or "public"
        principal_hash = hashlib.sha256(principal.encode("utf-8", "ignore")).hexdigest()[:24]
        raw = f"{generation}|{request.url.path}|{query}|{principal_hash}"
        digest = hashlib.sha256(raw.encode()).hexdigest()
        return f"{self.config.key_prefix}:cache:response:{digest}"

    async def _cache_get(self, key: str) -> bytes | None:
        if self._redis is not None:
            try:
                value = await self._redis.get(key)
                self._redis_warning_emitted = False
                return value
            except Exception as exc:  # pragma: no cover - depends on external Redis
                self._warn_redis(exc)

        async with self._memory_lock:
            self._cleanup_memory_locked()
            item = self._memory_cache.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= time.time():
                self._memory_cache.pop(key, None)
                return None
            return value

    async def _cache_set(self, key: str, payload: bytes) -> None:
        if self._redis is not None:
            try:
                await self._redis.set(key, payload, ex=self.config.cache_ttl_seconds)
                self._redis_warning_emitted = False
                return
            except Exception as exc:  # pragma: no cover - depends on external Redis
                self._warn_redis(exc)

        async with self._memory_lock:
            self._cleanup_memory_locked()
            self._memory_cache[key] = (time.time() + self.config.cache_ttl_seconds, payload)
            self._trim_memory_locked(self._memory_cache, 2048)

    async def _maybe_cache_response(self, response: Response, key: str) -> Response | None:
        content_type = response.headers.get("content-type", "").lower()
        cache_control = response.headers.get("cache-control", "").lower()
        if (
            response.status_code != 200
            or "application/json" not in content_type
            or "no-store" in cache_control
            or "set-cookie" in response.headers
            or not hasattr(response, "body_iterator")
        ):
            return None

        body = b"".join([bytes(chunk) async for chunk in response.body_iterator])
        if len(body) > self.config.cache_max_body_bytes:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                background=getattr(response, "background", None),
            )

        safe_headers = {
            name: value
            for name, value in response.headers.items()
            if name.lower() not in {"date", "server", "set-cookie", "transfer-encoding", "connection"}
        }
        payload = json.dumps(
            {
                "status": response.status_code,
                "headers": safe_headers,
                "body": base64.b64encode(body).decode("ascii"),
                "created_at": int(time.time()),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        await self._cache_set(key, payload)
        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            background=getattr(response, "background", None),
        )

    def _decode_cached_response(self, payload: bytes) -> Response:
        data = json.loads(payload.decode("utf-8"))
        headers = dict(data.get("headers") or {})
        created_at = int(data.get("created_at") or time.time())
        headers["Age"] = str(max(0, int(time.time()) - created_at))
        return Response(
            content=base64.b64decode(data["body"]),
            status_code=int(data.get("status", 200)),
            headers=headers,
        )

    def _cleanup_memory_locked(self) -> None:
        now = time.time()
        for key, (_, expires_at) in list(self._memory_rates.items()):
            if expires_at <= now:
                self._memory_rates.pop(key, None)
        for key, (expires_at, _) in list(self._memory_cache.items()):
            if expires_at <= now:
                self._memory_cache.pop(key, None)

    @staticmethod
    def _trim_memory_locked(mapping: dict, maximum: int) -> None:
        while len(mapping) > maximum:
            mapping.pop(next(iter(mapping)), None)

    def _warn_redis(self, exc: Exception) -> None:
        if not self._redis_warning_emitted:
            logger.warning("Redis unavailable; using in-process HTTP protection fallback: %s", exc)
            self._redis_warning_emitted = True
