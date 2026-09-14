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
    assert "necessária" in result["summary"]
    assert "ghp_123456789012345678901234567890" not in result["stderr"]
    assert "[REDACTED]" in result["stderr"]


def test_exhausted_non_destructive_failures_can_continue_pipeline():
    service = AutoRecoveryService()
    should_continue = getattr(service, "should_continue_pipeline", None)
    assert callable(should_continue), "AutoRecoveryService precisa decidir continuidade degradada"

    for category, status, requires_authorization in (
        ("github_auth", "needs_attention", False),
        ("git_network", "needs_attention", False),
        ("repository_state", "needs_attention", False),
        ("codex_auth", "needs_authorization", True),
        ("filesystem_permission", "needs_authorization", True),
        ("database", "needs_attention", False),
        ("unknown", "diagnosis_required", False),
    ):
        decision = RecoveryDecision(
            category=category,
            status=status,
            message="falha esgotada",
            retry=False,
            requires_authorization=requires_authorization,
        )
        assert should_continue(decision) is True, category


def test_retry_and_resolved_decisions_do_not_become_degraded_completion():
    service = AutoRecoveryService()
    should_continue = getattr(service, "should_continue_pipeline", None)
    assert callable(should_continue)

    assert should_continue(RecoveryDecision("git_network", "retrying", "retry", retry=True)) is False
    assert should_continue(RecoveryDecision("github_auth", "resolved", "ok")) is False


def test_explicit_integrity_risk_is_hard_stop():
    service = AutoRecoveryService()
    error = "sqlite3.DatabaseError: database disk image is malformed; data corruption detected"

    assert service.classify(error) == "safety_integrity"
    decision = service.recover(None, None, error, service.MAX_ATTEMPTS)

    assert getattr(decision, "hard_stop", False) is True
    assert service.should_continue_pipeline(decision) is False


def test_degraded_result_is_successful_but_does_not_claim_full_delivery_or_leak_secret():
    service = AutoRecoveryService()
    degraded_result = getattr(service, "degraded_result", None)
    assert callable(degraded_result), "AutoRecoveryService precisa materializar resultado degradado"

    decision = RecoveryDecision(
        category="github_auth",
        status="needs_attention",
        message="Credenciais administrativas esgotadas.",
        strategy="github_credentials_exhausted_admin",
    )
    result = degraded_result(
        decision,
        "fatal: Authorization: Bearer ghp_123456789012345678901234567890 denied",
        existing_result={"exit_code": 1, "stdout": "trabalho parcial preservado"},
    )

    assert result["exit_code"] == 0
    assert result["mode"] == "self-healing-degraded"
    assert result["degraded"] is True
    assert result["self_healing"]["status"] == "deferred"
    assert result["self_healing"]["pipeline_continued"] is True
    assert "não foi concluída integralmente" in result["summary"].lower()
    assert result["stdout"] == "trabalho parcial preservado"
    assert "ghp_123456789012345678901234567890" not in result["stderr"]
    assert "[REDACTED]" in result["stderr"]
