from __future__ import annotations

from collections.abc import Callable, Iterable
from ipaddress import ip_address
import socket
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx


_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class UnsafeProbeUrl(ValueError):
    """Raised when an outbound delivery probe would cross the allowed public boundary."""


def _matches_allowed_suffix(host: str, suffixes: Iterable[str]) -> bool:
    normalized = host.lower()
    return any(
        normalized.endswith(suffix.lower()) and len(normalized) > len(suffix)
        for suffix in suffixes
    )


def _resolve_public_addresses(
    host: str,
    port: int,
    resolver: Callable[..., list[Any]],
) -> None:
    try:
        addresses = resolver(
            host,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except (OSError, socket.gaierror) as error:
        raise UnsafeProbeUrl("delivery_probe_dns_unavailable") from error

    if not addresses:
        raise UnsafeProbeUrl("delivery_probe_dns_empty")

    seen: set[str] = set()
    for item in addresses:
        try:
            raw_ip = str(item[4][0]).split("%", 1)[0]
            address = ip_address(raw_ip)
        except (IndexError, TypeError, ValueError) as error:
            raise UnsafeProbeUrl("delivery_probe_dns_invalid") from error
        if str(address) in seen:
            continue
        seen.add(str(address))
        if not address.is_global:
            raise UnsafeProbeUrl("delivery_probe_non_public_address")


def _validate_public_https_url(
    value: str,
    *,
    allowed_suffixes: tuple[str, ...],
    resolver: Callable[..., list[Any]],
) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        raise UnsafeProbeUrl("delivery_probe_url_empty")

    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as error:
        raise UnsafeProbeUrl("delivery_probe_url_invalid") from error

    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https":
        raise UnsafeProbeUrl("delivery_probe_https_required")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeProbeUrl("delivery_probe_userinfo_forbidden")
    if not host or host.endswith(".") or not _matches_allowed_suffix(host, allowed_suffixes):
        raise UnsafeProbeUrl("delivery_probe_host_not_allowed")
    if port not in (None, 443):
        raise UnsafeProbeUrl("delivery_probe_port_not_allowed")

    _resolve_public_addresses(host, 443, resolver)
    return candidate


def probe_public_https_url(
    url: str,
    *,
    allowed_suffixes: tuple[str, ...],
    timeout_seconds: float,
    accept: str = "text/html,application/json;q=0.9,*/*;q=0.8",
    max_redirects: int = 3,
    resolver: Callable[..., list[Any]] | None = None,
    client_factory: Callable[..., Any] | None = None,
) -> tuple[bool, int]:
    """Probe a provider URL without allowing redirects to escape its public boundary.

    Every hop must remain HTTPS on the configured provider suffixes and resolve only
    to globally routable addresses. Automatic redirects and environment proxies are
    disabled so redirect targets are validated before another network request occurs.
    """

    dns_resolver = resolver or socket.getaddrinfo
    make_client = client_factory or httpx.Client
    current = str(url or "").strip()

    try:
        with make_client(
            timeout=timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            for redirect_count in range(max_redirects + 1):
                current = _validate_public_https_url(
                    current,
                    allowed_suffixes=allowed_suffixes,
                    resolver=dns_resolver,
                )
                response = client.get(current, headers={"Accept": accept})
                status_code = int(response.status_code)
                if status_code not in _REDIRECT_STATUSES:
                    return 200 <= status_code < 400, status_code

                location = str(response.headers.get("location") or "").strip()
                if not location or redirect_count >= max_redirects:
                    return False, status_code
                current = urljoin(current, location)
    except (httpx.HTTPError, OSError, UnsafeProbeUrl, ValueError):
        return False, 0

    return False, 0
