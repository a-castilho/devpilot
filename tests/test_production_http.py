import asyncio

from starlette.requests import Request

from app.production_http import ProductionHttpConfig, ProductionHttpMiddleware


def _request(path: str, method: str = "GET", authorization: str | None = None) -> Request:
    headers = []
    if authorization:
        headers.append((b"authorization", authorization.encode("utf-8")))
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


def _middleware(**overrides) -> ProductionHttpMiddleware:
    config = ProductionHttpConfig(redis_url="", key_prefix="test", **overrides)
    return ProductionHttpMiddleware(lambda scope, receive, send: None, config=config)


def test_cache_key_is_isolated_by_authorization():
    middleware = _middleware()
    first = middleware._cache_key(_request("/api/projects", authorization="Bearer first"), 1)
    second = middleware._cache_key(_request("/api/projects", authorization="Bearer second"), 1)

    assert first != second
    assert "first" not in first
    assert "second" not in second


def test_sensitive_and_health_routes_are_not_cached():
    middleware = _middleware()

    assert middleware._cacheable_request(_request("/api/projects")) is True
    assert middleware._cacheable_request(_request("/auth/login")) is False
    assert middleware._cacheable_request(_request("/api/token-usage/me")) is False
    assert middleware._cacheable_request(_request("/health")) is False
    assert middleware._cacheable_request(_request("/api/projects", method="POST")) is False


def test_auth_rate_limit_uses_stricter_limit():
    middleware = _middleware(
        rate_limit_requests=20,
        auth_rate_limit_requests=2,
        rate_limit_window_seconds=60,
    )
    request = _request("/auth/login", method="POST")

    async def exercise():
        first = await middleware._rate_limit(request)
        second = await middleware._rate_limit(request)
        third = await middleware._rate_limit(request)
        return first, second, third

    first, second, third = asyncio.run(exercise())

    assert first["limit"] == 2
    assert first["count"] == 1
    assert second["count"] == 2
    assert third["count"] == 3


def test_write_invalidation_clears_memory_cache_generation():
    middleware = _middleware(cache_ttl_seconds=60)
    request = _request("/api/projects", authorization="Bearer user")

    async def exercise():
        generation = await middleware._cache_generation()
        key = middleware._cache_key(request, generation)
        await middleware._cache_set(key, b"cached")
        assert await middleware._cache_get(key) == b"cached"

        await middleware._bump_cache_generation()
        new_generation = await middleware._cache_generation()
        return key, generation, new_generation, await middleware._cache_get(key)

    key, old_generation, new_generation, old_value = asyncio.run(exercise())

    assert key
    assert new_generation == old_generation + 1
    assert old_value is None
