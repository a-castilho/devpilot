from app.services.recovery import AutoRecoveryService, RecoveryDecision


def test_classifies_github_403_as_auth_failure():
    service = AutoRecoveryService()

    category = service.classify(
        "remote: Write access to repository not granted.\n"
        "fatal: unable to access 'https://github.com/a-castilho/devpilot.git/': "
        "The requested URL returned error: 403"
    )

    assert category == "github_auth"


def test_classifies_transient_git_network_failure():
    service = AutoRecoveryService()

    assert service.classify("fatal: unable to access repository: Could not resolve host: github.com") == "git_network"


def test_classifies_codex_login_failure():
    service = AutoRecoveryService()

    assert service.classify("Not logged in. Run codex login") == "codex_auth"


def test_failure_result_requests_intervention_without_exposing_secret():
    service = AutoRecoveryService()
    decision = RecoveryDecision(
        category="github_auth",
        status="needs_authorization",
        message="Nenhuma credencial possui acesso ao repositório.",
        requires_authorization=True,
        strategy="request_github_authorization",
        steps=[],
    )

    result = service.failure_result(
        decision,
        "fatal: Authorization: Bearer ghp_123456789012345678901234567890 denied",
    )

    assert result["exit_code"] == 1
    assert result["self_healing"]["requires_authorization"] is True
    assert "Intervenção necessária" in result["summary"]
    assert "ghp_123456789012345678901234567890" not in result["stderr"]
    assert "[REDACTED]" in result["stderr"]
