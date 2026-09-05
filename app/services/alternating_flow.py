from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from app.config import get_settings
from app.db import SessionLocal
from app.models import Project, Task
from app.project_provisioning_routes import provision_repository_in_background
from app.services import executor as executor_service
from app.services.task_flow import execution_branch, is_analysis_action_task, is_verification_analysis


REPOSITORY_NOT_READY = "REPOSITORY_NOT_READY"


def _disabled_result(mode: str) -> dict:
    return {
        "mode": mode,
        "exit_code": 78,
        "summary": "A execução automática está desativada; o fluxo foi interrompido sem simular sucesso.",
        "client_report": (
            "Resumo para o cliente\nA etapa automática não foi executada porque a execução está desativada.\n\n"
            "O que encontramos\nO DevPilot interrompeu o encadeamento antes de alterar ou validar o projeto.\n\n"
            "Impacto\nNenhuma etapa seguinte será criada com base em uma execução que não aconteceu.\n\n"
            "Recomendações\nHabilitar a execução automática antes de retomar o fluxo.\n\n"
            "Próximo passo\nHabilite a execução e tente novamente a tarefa bloqueada."
        ),
    }


def _repository_not_ready_result() -> dict:
    message = (
        "O repositório do projeto ainda não está pronto. O DevPilot interrompeu a etapa antes de iniciar "
        "Git ou Codex e tentará novamente somente depois que repository_url existir."
    )
    return {
        "mode": "repository-preflight",
        "exit_code": 78,
        "summary": message,
        "stderr": f"{REPOSITORY_NOT_READY}: repository_url is empty",
        "client_report": (
            "Resumo para o cliente\n"
            "A etapa não foi iniciada porque o repositório do projeto ainda não está disponível.\n\n"
            "O que encontramos\nrepository_url continua vazio após a tentativa automática de provisionamento.\n\n"
            "Impacto\nNenhum comando Git, Codex ou alteração de código foi executado com um repositório inválido.\n\n"
            "Recomendações\nConcluir o provisionamento GitHub do próprio projeto e manter a mesma tarefa para reteste.\n\n"
            "Próximo passo\nAtualize o diagnóstico; o DevPilot retomará a mesma etapa quando o repositório estiver pronto."
        ),
        "self_healing": {
            "status": "needs_attention",
            "category": "repository_not_ready",
            "requires_authorization": False,
            "strategy": "repository_provision_preflight",
            "message": message,
            "steps": [
                {
                    "state": "detected",
                    "category": "repository_not_ready",
                    "message": f"{REPOSITORY_NOT_READY}: repository_url is empty",
                }
            ],
        },
    }


def _ensure_project_repository(project: Project) -> bool:
    if str(project.repository_url or "").strip():
        return True

    provision_repository_in_background(
        project.id,
        project.workspace_id,
        "worker",
    )

    with SessionLocal() as db:
        refreshed = db.get(Project, project.id)
        if not refreshed or not str(refreshed.repository_url or "").strip():
            return False
        project.repository_url = refreshed.repository_url
        project.default_branch = refreshed.default_branch
        project.organization_id = refreshed.organization_id
    return True


def _execute_action(project: Project, task: Task) -> dict:
    if not get_settings().execution_enabled:
        return _disabled_result("flow-execution-disabled")

    path = executor_service.ensure_repository(project)
    if project.agents_md:
        (path / "AGENTS.md").write_text(project.agents_md, encoding="utf-8")

    target_branch = execution_branch(task)
    if target_branch:
        current = executor_service.run(["git", "branch", "--show-current"], cwd=path)
        current_branch = current.stdout.strip() if current.returncode == 0 else ""
        if current_branch != target_branch:
            checkout = executor_service.run(["git", "switch", target_branch], cwd=path)
            if checkout.returncode:
                raise RuntimeError(
                    checkout.stderr.strip()
                    or f"Unable to continue correction on execution branch {target_branch}"
                )
        branch = target_branch
    else:
        branch = task.branch_name or f"devpilot/{task.id[:8]}"
        checkout = executor_service.run(
            ["git", "switch", "-C", branch, f"origin/{project.default_branch}"],
            cwd=path,
        )
        if checkout.returncode:
            raise RuntimeError(checkout.stderr.strip() or "Unable to create task branch")

    result = executor_service.run(
        executor_service.codex_command(project, executor_service.development_prompt(task)),
        cwd=path,
        timeout=executor_service.task_timeout(project),
    )
    client_report = executor_service.extract_client_report(result.stdout)
    return {
        "mode": "execute",
        "exit_code": result.returncode,
        "summary": (
            "Execução concluída. O fluxo seguirá para validação automática."
            if result.returncode == 0
            else "A execução terminou com falha; o fluxo automático foi interrompido."
        ),
        "client_report": client_report,
        "stdout": result.stdout[-100_000:],
        "stderr": result.stderr[-20_000:],
        "branch": branch,
    }


def _copy_untracked(repository: Path, analysis_path: Path) -> None:
    untracked = executor_service.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=repository,
    )
    if untracked.returncode:
        raise RuntimeError(untracked.stderr.strip() or "Unable to list untracked execution files")

    for relative in (line.strip() for line in untracked.stdout.splitlines()):
        if not relative:
            continue
        source = repository / relative
        destination = analysis_path / relative
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        elif source.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def _execute_verification(project: Project, task: Task) -> dict:
    if not get_settings().execution_enabled:
        return _disabled_result("analysis-read-only-disabled")

    repository = executor_service.ensure_repository(project)
    target_branch = execution_branch(task)
    if not target_branch:
        raise RuntimeError("Verification task is missing the execution branch marker")

    current = executor_service.run(["git", "branch", "--show-current"], cwd=repository)
    current_branch = current.stdout.strip() if current.returncode == 0 else ""
    if current_branch != target_branch:
        checkout = executor_service.run(["git", "switch", target_branch], cwd=repository)
        if checkout.returncode:
            raise RuntimeError(
                checkout.stderr.strip()
                or f"Unable to inspect execution branch {target_branch}"
            )

    with tempfile.TemporaryDirectory(prefix=f"devpilot-verify-{task.id[:8]}-") as temp_dir:
        analysis_path = Path(temp_dir) / "repository"
        worktree = executor_service.run(
            ["git", "worktree", "add", "--detach", str(analysis_path), "HEAD"],
            cwd=repository,
        )
        if worktree.returncode:
            raise RuntimeError(worktree.stderr.strip() or "Unable to prepare verification workspace")

        try:
            patch = executor_service.run(["git", "diff", "--binary", "HEAD"], cwd=repository)
            if patch.returncode:
                raise RuntimeError(patch.stderr.strip() or "Unable to snapshot execution changes")
            if patch.stdout:
                patch_path = Path(temp_dir) / "execution.patch"
                patch_path.write_text(patch.stdout, encoding="utf-8")
                applied = executor_service.run(
                    ["git", "apply", "--binary", "--whitespace=nowarn", str(patch_path)],
                    cwd=analysis_path,
                )
                if applied.returncode:
                    raise RuntimeError(applied.stderr.strip() or "Unable to apply execution snapshot")

            _copy_untracked(repository, analysis_path)
            rules = (
                f"\n\nProject instructions (reference only):\n{project.agents_md}"
                if project.agents_md
                else ""
            )
            prompt = (
                f"Task: {task.title}\n\n{task.prompt}{rules}\n\n"
                "This is the REQUIRED POST-EXECUTION READ-ONLY VERIFICATION. Inspect the exact working-tree "
                "snapshot produced by the preceding implementation. Verify with concrete evidence that the "
                "original findings were corrected, run non-destructive checks when useful, identify regressions "
                "or remaining gaps, and prioritize only what still needs correction. Do not edit, create, delete, "
                "rename, commit, push, merge, or deploy project files.\n\n"
                f"{executor_service.CLIENT_REPORT_INSTRUCTIONS}"
            )
            result = executor_service.run(
                executor_service.codex_command(project, prompt),
                cwd=analysis_path,
                timeout=executor_service.task_timeout(project),
            )
            client_report = executor_service.extract_client_report(result.stdout)
            return {
                "mode": "analysis-read-only",
                "exit_code": result.returncode,
                "summary": (
                    "Validação pós-execução concluída. O fluxo seguirá para a correção final."
                    if result.returncode == 0
                    else "A validação pós-execução falhou; o fluxo automático foi interrompido."
                ),
                "client_report": client_report,
                "stdout": result.stdout[-100_000:],
                "stderr": result.stderr[-20_000:],
                "persisted_changes": False,
                "branch": target_branch,
            }
        finally:
            executor_service.run(
                ["git", "worktree", "remove", "--force", str(analysis_path)],
                cwd=repository,
            )
            executor_service.run(["git", "worktree", "prune"], cwd=repository)


def execute_task(project: Project, task: Task) -> dict:
    """Execute only after the project has a persisted repository URL."""
    if not _ensure_project_repository(project):
        return _repository_not_ready_result()
    if is_verification_analysis(task):
        return _execute_verification(project, task)
    if is_analysis_action_task(task):
        return _execute_action(project, task)
    return executor_service.execute_task(project, task)
