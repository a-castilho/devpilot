from __future__ import annotations

import hashlib
import hmac
import time


class AgentAuthError(ValueError):
    """Raised when a signed DevPilot Linux Agent request is invalid."""


def canonical_target(path: str, query: str = "") -> str:
    if not query:
        return path
    return f"{path}?{query}"


def body_sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def signing_payload(
    *,
    timestamp: str,
    nonce: str,
    method: str,
    target: str,
    body: bytes,
) -> bytes:
    return "\n".join(
        [
            timestamp,
            nonce,
            method.upper(),
            target,
            body_sha256(body),
        ]
    ).encode("utf-8")


def sign_request(
    secret: str,
    *,
    timestamp: str,
    nonce: str,
    method: str,
    target: str,
    body: bytes,
) -> str:
    if len(secret) < 32:
        raise AgentAuthError("Linux Agent secret must contain at least 32 characters")
    payload = signing_payload(
        timestamp=timestamp,
        nonce=nonce,
        method=method,
        target=target,
        body=body,
    )
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_request(
    secret: str,
    *,
    timestamp: str,
    nonce: str,
    method: str,
    target: str,
    body: bytes,
    signature: str,
    now: int | None = None,
    max_skew_seconds: int = 30,
) -> None:
    try:
        sent_at = int(timestamp)
    except (TypeError, ValueError) as error:
        raise AgentAuthError("Invalid request timestamp") from error

    current = int(time.time()) if now is None else int(now)
    if abs(current - sent_at) > max_skew_seconds:
        raise AgentAuthError("Expired signed request")

    if not nonce or len(nonce) < 16:
        raise AgentAuthError("Invalid request nonce")

    expected = sign_request(
        secret,
        timestamp=timestamp,
        nonce=nonce,
        method=method,
        target=target,
        body=body,
    )
    if not signature or not hmac.compare_digest(signature, expected):
        raise AgentAuthError("Invalid request signature")
