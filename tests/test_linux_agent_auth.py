import pytest

from app.linux_agent.auth import AgentAuthError, sign_request, verify_request


SECRET = "x" * 48


def test_signed_request_round_trip():
    signature = sign_request(
        SECRET,
        timestamp="1000",
        nonce="1234567890abcdef1234567890abcdef",
        method="POST",
        target="/v1/terminal/sessions",
        body=b'{"actor":"user:1"}',
    )
    verify_request(
        SECRET,
        timestamp="1000",
        nonce="1234567890abcdef1234567890abcdef",
        method="POST",
        target="/v1/terminal/sessions",
        body=b'{"actor":"user:1"}',
        signature=signature,
        now=1000,
    )


def test_signature_rejects_body_tampering():
    signature = sign_request(
        SECRET,
        timestamp="1000",
        nonce="1234567890abcdef1234567890abcdef",
        method="POST",
        target="/v1/terminal/sessions",
        body=b"safe",
    )
    with pytest.raises(AgentAuthError, match="signature"):
        verify_request(
            SECRET,
            timestamp="1000",
            nonce="1234567890abcdef1234567890abcdef",
            method="POST",
            target="/v1/terminal/sessions",
            body=b"changed",
            signature=signature,
            now=1000,
        )


def test_signature_rejects_expired_timestamp():
    signature = sign_request(
        SECRET,
        timestamp="1000",
        nonce="1234567890abcdef1234567890abcdef",
        method="GET",
        target="/v1/system",
        body=b"",
    )
    with pytest.raises(AgentAuthError, match="Expired"):
        verify_request(
            SECRET,
            timestamp="1000",
            nonce="1234567890abcdef1234567890abcdef",
            method="GET",
            target="/v1/system",
            body=b"",
            signature=signature,
            now=1100,
        )
