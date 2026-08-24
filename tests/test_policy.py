import os

os.environ.setdefault("DEVPILOT_BOOTSTRAP_TOKEN", "test-token-with-at-least-32-characters")

import pytest

from app.services.intent import interpret_voice
from app.services.policy import evaluate_task, normalize_repository_url, validate_repository_url


def test_git_url_rejects_embedded_credentials():
    with pytest.raises(ValueError):
        validate_repository_url("https://token@github.com/company/project.git")


def test_git_url_rejects_unapproved_host():
    with pytest.raises(ValueError):
        validate_repository_url("https://example.com/company/project.git")


@pytest.mark.parametrize(
    "repository",
    [
        "a-castilho/devpilot",
        "github.com/a-castilho/devpilot",
        "https://github.com/a-castilho/devpilot",
        "https://github.com/a-castilho/devpilot.git",
        "git@github.com:a-castilho/devpilot.git",
        "www.github.com/a-castilho/devpilot/",
        "` https://github.com / a-castilho / devpilot.git `",
    ],
)
def test_git_url_normalizes_supported_github_forms(repository):
    assert normalize_repository_url(repository) == "https://github.com/a-castilho/devpilot.git"


def test_git_url_normalizes_github_shorthand():
    assert (
        normalize_repository_url("a-castilho/regulaai")
        == "https://github.com/a-castilho/regulaai.git"
    )


def test_git_url_normalizes_ssh_form_without_credentials():
    assert (
        normalize_repository_url("git@github.com:a-castilho/devpilot.git")
        == "https://github.com/a-castilho/devpilot.git"
    )


def test_git_url_rejects_nested_repository_path():
    with pytest.raises(ValueError):
        normalize_repository_url("https://github.com/company/project/tree/main")


def test_git_url_uses_portuguese_format_error():
    with pytest.raises(ValueError, match="Informe o repositório no formato organização/repositório"):
        normalize_repository_url("github.com/company/project/tree/main")


def test_high_risk_task_requires_approval():
    decision = evaluate_task("Faça deploy em produção", requested_approval=False)
    assert decision.requires_approval is True
    assert "deploy" in decision.reasons


def test_spoken_deploy_synonym_requires_approval():
    decision = evaluate_task("Implante a versão atual", requested_approval=False)
    assert decision.requires_approval is True
    assert "implante" in decision.reasons


def test_regular_fix_can_enter_execution_queue_without_manual_approval():
    decision = evaluate_task("Corrija o layout mobile", requested_approval=False)
    assert decision.requires_approval is False
    assert decision.reasons == ()


def test_voice_intent_preserves_transcript_and_project_hint():
    result = interpret_voice("No regulaai analise falhas de segurança")
    assert result["project_hint"] == "regulaai"
    assert result["action"] == "analyze"
    assert result["operational"] is True
    assert result["prompt"] == "No regulaai analise falhas de segurança"
