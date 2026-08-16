from pathlib import Path

from app.models import Project
from app.services import executor


def project() -> Project:
    return Project(
        workspace_id="workspace",
        name="Novo Produto",
        slug="novo-produto",
        repository_url="https://github.com/example/novo-produto.git",
        default_branch="main",
    )


def test_empty_repository_uses_orphan_development_branch(monkeypatch, tmp_path: Path):
    commands: list[list[str]] = []

    def fake_run(args, **kwargs):
        commands.append(args)
        return type("Result", (), {"returncode": 1 if "show-ref" in args else 0, "stderr": ""})()

    monkeypatch.setattr(executor, "run", fake_run)

    executor.prepare_branch(tmp_path, project(), "devpilot/bootstrap")

    assert commands[-1] == ["git", "switch", "--orphan", "devpilot/bootstrap"]


def test_existing_repository_branches_from_configured_remote(monkeypatch, tmp_path: Path):
    commands: list[list[str]] = []

    def fake_run(args, **kwargs):
        commands.append(args)
        return type("Result", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(executor, "run", fake_run)

    executor.prepare_branch(tmp_path, project(), "devpilot/task")

    assert commands[-1] == [
        "git", "switch", "-C", "devpilot/task", "refs/remotes/origin/main",
    ]
