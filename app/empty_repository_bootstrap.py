from __future__ import annotations

from typing import Any


def _remote_default_exists(executor, repository, project) -> bool:
    branch = str(getattr(project, "default_branch", "") or "main").strip() or "main"
    result = executor.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"],
        cwd=repository,
    )
    return result.returncode == 0


def _bootstrap_prompt(executor, task) -> str:
    base = executor.development_prompt(task)
    return (
        base
        + "\n\nMANDATORY EMPTY-REPOSITORY BOOTSTRAP. The repository has no deployable application revision yet. "
        "This is NOT a blocker and does NOT require user approval. You are explicitly authorized by this build task "
        "to create the initial application structure needed to satisfy the requested objective. Bootstrap a minimal, "
        "production-sensible project using the technologies implied by the task/project context; when none are specified, "
        "choose a simple maintainable stack that can be tested and containerized. Implement the requested feature completely, "
        "including configuration, validation, tests, README/run instructions and a Dockerfile when the application is intended "
        "for web deployment. Do not stop merely because files, framework structure, database schema or authentication code do "
        "not exist yet. Create them. Do not ask the client to authorize creation of the base project: this execution already is "
        "that authorization. Only stop for a genuine external blocker that cannot be solved by writing code, such as an invalid "
        "credential or denied external permission. Your final client report must describe what you actually implemented and "
        "validated; it must not recommend 'iniciar o desenvolvimento', 'autorizar o início' or equivalent when the repository "
        "was empty."
    )


def _execute_empty_repository(executor, project, task, repository) -> dict[str, Any]:
    branch = task.branch_name or f"devpilot/{task.id[:8]}"

    # An empty GitHub repository has no origin/<default_branch>. Create a local
    # unborn task branch and let the normal agent build the first revision.
    switch = executor.run(["git", "switch", "--orphan", branch], cwd=repository)
    if switch.returncode:
        # Git versions differ in their orphan-switch behavior after cloning an
        # empty repository; checkout --orphan is the portable fallback.
        switch = executor.run(["git", "checkout", "--orphan", branch], cwd=repository)
    if switch.returncode:
        raise RuntimeError(switch.stderr.strip() or "Unable to initialize empty repository task branch")

    if project.agents_md:
        (repository / "AGENTS.md").write_text(project.agents_md, encoding="utf-8")

    result = executor.run(
        executor.codex_command(project, _bootstrap_prompt(executor, task)),
        cwd=repository,
        timeout=executor.task_timeout(project),
    )
    client_report = executor.extract_client_report(result.stdout)
    return {
        "mode": "execute-empty-repository-bootstrap",
        "empty_repository_bootstrap": True,
        "exit_code": result.returncode,
        "summary": (
            "Repositório vazio inicializado e execução concluída. Veja o resultado abaixo."
            if result.returncode == 0
            else "A inicialização automática do repositório começou, mas a execução terminou com falha técnica."
        ),
        "client_report": client_report,
        "stdout": result.stdout[-100_000:],
        "stderr": result.stderr[-20_000:],
        "branch": branch,
    }


def install_empty_repository_bootstrap() -> None:
    from app.services import executor

    if getattr(executor.execute_task, "_devpilot_empty_repo_bootstrap", False):
        return

    original_execute_task = executor.execute_task

    def execute_task(project, task):
        settings = executor.get_settings()
        if executor.is_read_only_task(task) or not settings.execution_enabled:
            return original_execute_task(project, task)

        repository = executor.ensure_repository(project)
        if _remote_default_exists(executor, repository, project):
            return original_execute_task(project, task)
        return _execute_empty_repository(executor, project, task, repository)

    execute_task._devpilot_empty_repo_bootstrap = True
    execute_task._devpilot_original_execute_task = original_execute_task
    executor.execute_task = execute_task


install_empty_repository_bootstrap()
