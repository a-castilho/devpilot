from __future__ import annotations

from typing import Any


AUTONOMOUS_BUILD_REPORT = (
    "\n\nAUTONOMOUS BUILD CONTRACT. This is an implementation task, not a planning-only request. "
    "Do not ask the client to authorize normal development work that is already inside the task scope. "
    "Create missing project structure, files, configuration, tests, migrations, Dockerfile and documentation when they are "
    "required to complete the requested feature. A missing implementation is work to perform, not a reason to stop. "
    "Only report a blocker when it is genuinely external and cannot be fixed by changing repository files or configuration. "
    "In the final section 'Próximo passo', report the next automatic pipeline step or a concrete external blocker; never use "
    "'autorizar o início do desenvolvimento', 'iniciar o desenvolvimento da estrutura' or equivalent for work already authorized."
)

EMPTY_REPOSITORY_BOOTSTRAP = (
    "\n\nMANDATORY EMPTY-REPOSITORY BOOTSTRAP. The repository has no deployable application revision yet. "
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


def _remote_default_exists(executor, repository, project) -> bool:
    branch = str(getattr(project, "default_branch", "") or "main").strip() or "main"
    result = executor.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"],
        cwd=repository,
    )
    return result.returncode == 0


def _prepare_empty_branch(executor, repository, task) -> str:
    branch = task.branch_name or f"devpilot/{task.id[:8]}"
    current = executor.run(["git", "branch", "--show-current"], cwd=repository)
    if current.returncode == 0 and current.stdout.strip() == branch:
        return branch

    switch = executor.run(["git", "switch", "--orphan", branch], cwd=repository)
    if switch.returncode:
        switch = executor.run(["git", "checkout", "--orphan", branch], cwd=repository)
    if switch.returncode:
        raise RuntimeError(switch.stderr.strip() or "Unable to initialize empty repository task branch")
    return branch


def _bootstrap_prompt(executor, task) -> str:
    return executor.development_prompt(task) + EMPTY_REPOSITORY_BOOTSTRAP


def _execute_empty_repository(executor, project, task, repository) -> dict[str, Any]:
    branch = _prepare_empty_branch(executor, repository, task)
    if project.agents_md:
        (repository / "AGENTS.md").write_text(project.agents_md, encoding="utf-8")

    result = executor.run(
        executor.codex_command(project, _bootstrap_prompt(executor, task)),
        cwd=repository,
        timeout=executor.task_timeout(project),
    )
    client_report = executor.extract_client_report(result.stdout)
    return {
        "mode": "execute",
        "empty_repository_bootstrap": True,
        "exit_code": result.returncode,
        "summary": (
            "Repositório vazio inicializado e execução concluída; o fluxo seguirá para validação automática."
            if result.returncode == 0
            else "A inicialização automática do repositório começou, mas a execução terminou com falha técnica."
        ),
        "client_report": client_report,
        "stdout": result.stdout[-100_000:],
        "stderr": result.stderr[-20_000:],
        "branch": branch,
    }


def install_empty_repository_bootstrap() -> None:
    from app.services import alternating_flow, executor

    if getattr(executor.execute_task, "_devpilot_empty_repo_bootstrap", False):
        return

    original_development_prompt = executor.development_prompt
    original_execute_task = executor.execute_task
    original_execute_action = alternating_flow._execute_action

    def development_prompt(task):
        return original_development_prompt(task) + AUTONOMOUS_BUILD_REPORT

    development_prompt._devpilot_autonomous_build = True
    executor.development_prompt = development_prompt

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

    def execute_action(project, task):
        if not executor.get_settings().execution_enabled:
            return original_execute_action(project, task)
        repository = executor.ensure_repository(project)
        if _remote_default_exists(executor, repository, project):
            return original_execute_action(project, task)
        return _execute_empty_repository(executor, project, task, repository)

    execute_action._devpilot_empty_repo_bootstrap = True
    alternating_flow._execute_action = execute_action


install_empty_repository_bootstrap()
