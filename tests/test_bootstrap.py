from app.models import Project
from app.services.bootstrap import build_bootstrap_prompt
from app import worker


def project() -> Project:
    return Project(
        workspace_id="workspace",
        name="Tela Viva",
        slug="telaviva",
        description="Plataforma de aprendizado ao vivo",
        repository_url="https://github.com/acastilho/telaviva.git",
    )


def test_bootstrap_prompt_generates_project_specific_agents_file():
    prompt = build_bootstrap_prompt(project(), generate_agents_md=True)

    assert "Tela Viva" in prompt
    assert "AGENTS.md" in prompt
    assert "actual project" in prompt


def test_bootstrap_prompt_preserves_git_safety_boundaries():
    prompt = build_bootstrap_prompt(project(), generate_agents_md=False)

    assert "Do not push, merge, deploy" in prompt
    assert "isolated task branch" in prompt


def test_worker_keeps_tasks_queued_while_execution_is_disabled(monkeypatch):
    disabled = type("Settings", (), {"execution_enabled": False})()
    monkeypatch.setattr(worker, "get_settings", lambda: disabled)

    assert worker.process_one() is False
