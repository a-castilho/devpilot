from __future__ import annotations

import subprocess
from types import SimpleNamespace

from app.models import Project, Task
from app.services import executor, local_executor
from app.services.local_executor import is_allowed_repository_path, is_read_only_task


def project(*, agents_md: str = "") -> Project:
    return Project(
        id="project-1",
        workspace_id="workspace-1",
        name="RegulaAI",
        slug="regulaai",
        description="",
        repository_url="https://github.com/a-castilho/regulaai.git",
        default_branch="main",
        agents_md=agents_md,
        codex_config="{}",
    )


def task(prompt: str, *, title: str = "Task") -> Task:
    return Task(
        id="task-12345678",
        workspace_id="workspace-1",
        project_id="project-1",
        title=title,
        prompt=prompt,
        source="dashboard",
        priority=50,
        requires_approval=False,
    )


def settings(**overrides):
    values = {
        "execution_enabled": True,
        "task_executor": "auto",
        "local_readonly_enabled": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_read_only_markers_are_explicit():
    assert is_read_only_task(task("Faça auditoria somente leitura. Não modifique arquivos."))
    assert is_read_only_task(task("READ-ONLY architecture review"))
    assert not is_read_only_task(task("Implemente a correção encontrada na auditoria"))


def test_repository_path_filter_excludes_common_secret_files():
    assert is_allowed_repository_path("README.md")
    assert is_allowed_repository_path("app/main.py")
    assert not is_allowed_repository_path(".env")
    assert not is_allowed_repository_path("config/.env.production")
    assert not is_allowed_repository_path("certs/private.key")
    assert not is_allowed_repository_path("node_modules/pkg/index.js")
    assert not is_allowed_repository_path("../outside.py")


def test_git_ref_context_does_not_touch_worktree_and_skips_env(monkeypatch, tmp_path):
    # Keep this fixture compatible with Git 2.25 (Ubuntu 20.04), where `git init -b`
    # is not available yet.
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "devpilot@example.test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "DevPilot Tests"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("# Safe project\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=do-not-index\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md", "main.py", ".env"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "untracked.txt").write_text("leave me alone\n", encoding="utf-8")
    before = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    ).stdout

    monkeypatch.setattr(
        local_executor,
        "get_settings",
        lambda: SimpleNamespace(
            local_readonly_max_files=10,
            local_readonly_max_file_chars=8_000,
            local_readonly_max_context_chars=40_000,
        ),
    )
    context = local_executor.collect_repository_context(tmp_path, ref="HEAD")
    after = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    ).stdout

    assert "README.md" in context.text
    assert "main.py" in context.text
    assert "SECRET=do-not-index" not in context.text
    assert before == after


def test_read_only_task_routes_to_agentos_without_writing_agents(monkeypatch, tmp_path):
    item = project(agents_md="# policy")
    work = task("Leia o projeto em modo somente leitura. Não altere nenhum arquivo.")
    monkeypatch.setattr(executor, "get_settings", lambda: settings())
    monkeypatch.setattr(executor, "ensure_repository", lambda _: tmp_path)
    called = {}

    def local(project_arg, task_arg, *, path):
        called.update(project=project_arg, task=task_arg, path=path)
        return {"mode": "execute", "executor": "agentos-read-only", "exit_code": 0}

    monkeypatch.setattr(executor, "execute_read_only_agentos", local)
    result = executor.execute_task(item, work)

    assert result["executor"] == "agentos-read-only"
    assert called["path"] == tmp_path
    assert not (tmp_path / "AGENTS.md").exists()


def test_codex_receives_project_instructions_without_creating_agents_file(monkeypatch, tmp_path):
    item = project(agents_md="# Preserve regulatory history")
    work = task("Implemente uma pequena correção com testes.", title="Implement fix")
    monkeypatch.setattr(executor, "get_settings", lambda: settings())
    monkeypatch.setattr(executor, "ensure_repository", lambda _: tmp_path)
    calls: list[list[str]] = []

    def fake_run(args, cwd=None, timeout=900):
        calls.append(args)
        if args[:2] == ["git", "switch"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(
            args,
            0,
            stdout='{"type":"turn.completed"}\n',
            stderr="",
        )

    monkeypatch.setattr(executor, "run", fake_run)
    result = executor.execute_task(item, work)

    assert result["executor"] == "codex"
    assert result["exit_code"] == 0
    assert not (tmp_path / "AGENTS.md").exists()
    codex = next(call for call in calls if call[:3] == ["codex", "exec", "--json"])
    prompt = codex[-1]
    assert "# Preserve regulatory history" in prompt
    assert "do not write these into the repository" in prompt


def test_codex_jsonl_error_becomes_run_summary():
    stdout = "\n".join(
        [
            '{"type":"thread.started"}',
            '{"type":"error","message":"You have hit your usage limit."}',
            '{"type":"turn.failed","error":{"message":"You have hit your usage limit."}}',
        ]
    )
    assert executor._extract_codex_message(stdout, "") == "You have hit your usage limit."
