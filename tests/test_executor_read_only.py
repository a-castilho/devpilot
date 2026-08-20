from pathlib import Path
from types import SimpleNamespace

from app.services import executor


def test_read_only_mode_marker_is_detected():
    task = SimpleNamespace(prompt=f"{executor.READ_ONLY_MODE_MARKER}\nAnalise a arquitetura.")
    assert executor.is_read_only_task(task) is True


def test_legacy_analysis_prompt_remains_read_only():
    task = SimpleNamespace(prompt="Faça uma auditoria somente leitura. Não modifique arquivos.")
    assert executor.is_read_only_task(task) is True


def test_regular_development_task_is_not_read_only():
    task = SimpleNamespace(prompt="Implemente a tela e execute os testes.")
    assert executor.is_read_only_task(task) is False


def test_read_only_analysis_uses_disposable_worktree(monkeypatch):
    calls = []

    def fake_run(args, cwd=None, timeout=900, env_overrides=None):
        calls.append((list(args), cwd, timeout))
        if args[:3] == ["git", "status", "--porcelain"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args[:2] == ["codex", "exec"]:
            return SimpleNamespace(returncode=0, stdout='{"result":"ok"}', stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(executor, "run", fake_run)

    project = SimpleNamespace(default_branch="main", agents_md="", codex_config="{}")
    task = SimpleNamespace(
        id="12345678-0000-0000-0000-000000000000",
        title="Auditoria técnica",
        prompt=f"{executor.READ_ONLY_MODE_MARKER}\nAnalise o projeto.",
    )

    result = executor.execute_read_only_analysis(project, task, Path("/tmp/devpilot-test-repository"))

    commands = [args for args, _, _ in calls]
    assert any(command[:3] == ["git", "worktree", "add"] for command in commands)
    assert any(command[:2] == ["codex", "exec"] for command in commands)
    assert any(command[:3] == ["git", "worktree", "remove"] for command in commands)
    assert not any(command[:2] == ["git", "switch"] for command in commands)
    assert result["mode"] == "analysis-read-only"
    assert result["persisted_changes"] is False
    assert result["attempted_changes"] is False
