from pathlib import Path


WORKFLOW = Path('.github/workflows/preview-environment.yml')


def test_preview_environment_is_temporary_isolated_and_non_executing():
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert 'name: DevPilot Preview Environment' in workflow
    assert 'workflow_dispatch:' in workflow
    assert "contains(github.event.pull_request.labels.*.name, 'preview')" in workflow
    assert "github.event.pull_request.head.repo.full_name == github.repository" in workflow
    assert "DEVPILOT_EXECUTION_ENABLED=false" in workflow
    assert "DEVPILOT_EMBEDDED_WORKER=false" in workflow
    assert "--host 127.0.0.1" in workflow
    assert "sqlite:///" in workflow
    assert "trycloudflare.com" in workflow
    assert "TTL > 90" in workflow
    assert "RUNNER_TRACKING_ID" in workflow
    assert "retention-days: 1" in workflow


def test_preview_access_is_authenticated_and_not_a_permanent_deploy():
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert '/api/auth/bootstrap' in workflow
    assert 'preview-admin@devpilot.local' in workflow
    assert 'secrets.token_urlsafe' in workflow
    assert 'sleep $((TTL * 60))' in workflow
    assert 'rm -rf' in workflow
    assert 'Ambiente temporário, banco isolado e execução automática desativada.' in workflow
