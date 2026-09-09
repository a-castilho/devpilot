from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from typing import Any, Callable

from app.models import Project, Run, Task, TaskStatus

REPAIR_PIPELINE_MARKER = "[DEVPILOT_REPAIR_PIPELINE_V1]"
_URL_RE = re.compile(r"https://github\.com/[^\s]+/pull/\d+")


@dataclass
class RepairDelivery:
    status: str
    commit_sha: str = ""
    pull_request_url: str = ""
    ci_status: str = "not_checked"
    message: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def incident_context(*, task: Task, run: Run | None, failure: dict) -> dict:
    """Build a compact, durable and secret-minimized incident snapshot."""
    return {
        "version": 1,
        "task_id": task.id,
        "task_title": task.title,
        "run_id": run.id if run else "",
        "project_id": task.project_id,
        "category": str(failure.get("category") or "unknown"),
        "code": str(failure.get("code") or "EXECUTION_FAILED"),
        "message": str(failure.get("message") or "Falha sem mensagem detalhada.")[:2000],
        "requires_authorization": bool(failure.get("requires_authorization")),
    }


def incident_block(*, task: Task, run: Run | None, failure: dict) -> str:
    payload = json.dumps(incident_context(task=task, run=run, failure=failure), ensure_ascii=False, sort_keys=True)
    return f"{REPAIR_PIPELINE_MARKER}\n[repair-incident:{payload}]"


def _result_text(result: Any) -> str:
    return f"{getattr(result, 'stdout', '')}\n{getattr(result, 'stderr', '')}".strip()


def _run(executor_module: Any, args: list[str], *, cwd, timeout: int = 120, env: dict[str, str] | None = None):
    try:
        return executor_module.run(args, cwd=cwd, timeout=timeout, env_overrides=env)
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(args, 127, "", str(error))


def finalize_repair_delivery(
    *,
    executor_module: Any,
    project: Project,
    repair_task: Task,
    run: Run,
    ci_timeout: int = 600,
) -> RepairDelivery:
    """Materialize a successful repair as commit + PR + CI evidence.

    Environmental repairs may leave no repository diff; those are returned as
    ``no_changes`` and the original task becomes the final proof. Code changes are
    committed and pushed on the repair branch, a PR is opened, and checks are watched.
    Merge is deliberately excluded from this autonomous boundary.
    """
    repository = executor_module.repository_path(project)
    git_env = executor_module.git_environment(project)

    status = _run(executor_module, ["git", "status", "--porcelain"], cwd=repository, env=git_env)
    if status.returncode:
        return RepairDelivery(status="delivery_failed", message=_result_text(status)[-2000:])
    if not str(status.stdout or "").strip():
        return RepairDelivery(status="no_changes", ci_status="not_applicable", message="Recuperação sem alteração de código; reteste da tarefa original é a prova final.")

    add = _run(executor_module, ["git", "add", "-A"], cwd=repository, env=git_env)
    if add.returncode:
        return RepairDelivery(status="delivery_failed", message=_result_text(add)[-2000:])

    staged = _run(executor_module, ["git", "diff", "--cached", "--quiet"], cwd=repository, env=git_env)
    if staged.returncode == 0:
        return RepairDelivery(status="no_changes", ci_status="not_applicable", message="Nenhuma mudança staged após a recuperação.")
    if staged.returncode != 1:
        return RepairDelivery(status="delivery_failed", message=_result_text(staged)[-2000:])

    commit = _run(executor_module, ["git", "commit", "-m", f"fix(repair): recover task {repair_task.id[:8]}"], cwd=repository, env=git_env)
    if commit.returncode:
        return RepairDelivery(status="delivery_failed", message=_result_text(commit)[-2000:])

    sha_result = _run(executor_module, ["git", "rev-parse", "HEAD"], cwd=repository, env=git_env)
    commit_sha = str(sha_result.stdout or "").strip() if sha_result.returncode == 0 else ""
    branch = str(repair_task.branch_name or "").strip()
    if not branch:
        branch_result = _run(executor_module, ["git", "branch", "--show-current"], cwd=repository, env=git_env)
        branch = str(branch_result.stdout or "").strip()
    if not branch:
        return RepairDelivery(status="delivery_failed", commit_sha=commit_sha, message="Branch de recuperação não identificada.")

    push = _run(executor_module, ["git", "push", "-u", "origin", branch], cwd=repository, timeout=180, env=git_env)
    if push.returncode:
        return RepairDelivery(status="delivery_failed", commit_sha=commit_sha, message=_result_text(push)[-2000:])

    title = f"fix(repair): {repair_task.title}"[:240]
    body = (
        "PR criada automaticamente pelo DevPilot Repair Pipeline.\n\n"
        f"Tarefa de recuperação: `{repair_task.id}`\n"
        f"Run: `{run.id}`\n\n"
        "A correção foi produzida após diagnóstico de causa raiz. O merge permanece fora do fluxo automático."
    )
    pr = _run(executor_module, ["gh", "pr", "create", "--base", project.default_branch, "--head", branch, "--title", title, "--body", body], cwd=repository, timeout=180)
    if pr.returncode:
        return RepairDelivery(status="delivery_failed", commit_sha=commit_sha, message=_result_text(pr)[-2000:])

    match = _URL_RE.search(_result_text(pr))
    pr_url = match.group(0) if match else str(pr.stdout or "").strip().splitlines()[-1].strip()
    checks = _run(executor_module, ["gh", "pr", "checks", pr_url, "--watch", "--fail-fast"], cwd=repository, timeout=ci_timeout)
    if checks.returncode == 0:
        return RepairDelivery(status="ready_to_retest", commit_sha=commit_sha, pull_request_url=pr_url, ci_status="passed")

    text = _result_text(checks)
    normalized = text.casefold()
    if "no checks" in normalized or "no checks reported" in normalized:
        return RepairDelivery(status="ready_to_retest", commit_sha=commit_sha, pull_request_url=pr_url, ci_status="not_configured", message=text[-2000:])
    return RepairDelivery(status="ci_failed", commit_sha=commit_sha, pull_request_url=pr_url, ci_status="failed", message=text[-4000:])


def install_repair_pipeline() -> None:
    """Attach the autonomous pipeline without changing the public recovery API.

    The existing recovery state machine remains authoritative. The hook adds two
    invariants: every recovery gets a structured incident snapshot, and a repair with
    code changes must produce PR/CI evidence before the original task is requeued.
    """
    from app.services import executor
    from app.services import failure_recovery

    if getattr(failure_recovery, "_devpilot_repair_pipeline_installed", False):
        return

    original_prompt: Callable[..., str] = failure_recovery.recovery_prompt
    original_resume: Callable[..., Task | None] = failure_recovery.resume_original_after_recovery

    def repair_prompt(original_task: Task, run: Run | None, failure: dict) -> str:
        base = original_prompt(original_task, run, failure)
        block = incident_block(task=original_task, run=run, failure=failure)
        instruction = (
            "\n\nREPAIR PIPELINE\n"
            "Trate este incidente como contexto persistente. Corrija a causa raiz, execute os testes focados primeiro, "
            "depois as verificações de integração relevantes, e deixe o repositório em estado verificável. "
            "Não faça push, PR ou merge manualmente: o DevPilot materializará commit, PR e evidência de CI após a execução."
        )
        return f"{block}\n{base}{instruction}"[:100_000]

    def guarded_resume(db, *, recovery_task: Task, recovery_run: Run) -> Task | None:
        if recovery_run.status != "success":
            return None
        project = db.get(Project, recovery_task.project_id)
        if project is None:
            recovery_run.status = "failed"
            recovery_run.summary = "Repair Pipeline: projeto não encontrado para materializar a entrega."
            recovery_task.status = TaskStatus.failed
            return None

        delivery = finalize_repair_delivery(executor_module=executor, project=project, repair_task=recovery_task, run=recovery_run)
        recovery_run.commit_sha = delivery.commit_sha or recovery_run.commit_sha
        recovery_run.pull_request_url = delivery.pull_request_url or recovery_run.pull_request_url
        recovery_run.summary = f"{recovery_run.summary or 'Recuperação concluída.'} Repair Pipeline: {delivery.status} / CI: {delivery.ci_status}."

        if delivery.status not in {"ready_to_retest", "no_changes"}:
            recovery_run.status = "failed"
            recovery_task.status = TaskStatus.failed
            return None
        return original_resume(db, recovery_task=recovery_task, recovery_run=recovery_run)

    failure_recovery.recovery_prompt = repair_prompt
    failure_recovery.resume_original_after_recovery = guarded_resume
    failure_recovery._devpilot_repair_pipeline_installed = True
