from app.services.project_context import _redact_text


def test_redact_text_removes_opaque_bearer_token():
    token = "opaque-sensitive-bearer-token-1234567890"
    redacted = _redact_text(f"Authorization: Bearer {token}\n")
    assert token not in redacted
    assert "[REDACTED]" in redacted


def test_redact_text_removes_common_secret_formats():
    github_token = "ghp_123456789012345678901234567890"
    openai_style = "sk-123456789012345678901234567890"
    redacted = _redact_text(
        "\n".join(
            [
                'password="my-long-secret-password"',
                f"GITHUB_TOKEN={github_token}",
                f"api_key={openai_style}",
            ]
        )
    )
    assert "my-long-secret-password" not in redacted
    assert github_token not in redacted
    assert openai_style not in redacted
    assert redacted.count("[REDACTED]") >= 3
