from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from app.models import Project, Run, Task

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
    """Build a compact, durable incident snapshot for the repair task.

    The snapshot intentionally stores identifiers and sanitized failure metadata only;
    raw secrets and complete terminal output remain in the run log where the existing
    sanitizer/authorization rules apply.
    """
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
    payload = json.dumps(
        incident_context(task=task, run=run, failure=failure),
        ensure_ascii=False,
        sort_keys=True,
    )
    return f"{REPAIR_PIPELINE_MARKER}\n[repair-incident:{payload}]"


def _result_text(result: Any) -> str:
    return f"{getattr(result, 'stdout', '')}\n{getattr(result, 'stderr', '')}".strip()


def _run(executor_module: Any, args: list[str], *, cwd, timeout: int = 120, env: dict[str, str] | None = None):
    return executor_module.run(args, cwd=cwd, timeout=timeout, env_overrides=env)


def finalize_repair_delivery(
    *,
    executor_module: Any,
    project: Project,
    repair_task: Task,
    run: Run,
    ci_timeout: int = 600,
) -> RepairDelivery:
    """Materialize a successful repair as commit + PR + CI evidence when possible.

    Environmental repairs may legitimately leave no repository diff; those are marked
    ``no_changes`` so the original task can be retested. Repository changes are never
    merged here. A created PR is watched until checks finish when GitHub CLI can do so.
    """
    repository = executor_module.repository_path(project)
    git_env = executor_module.git_environment(project)

    status = _run(executor_module, ["git", "status", "--porcelain"], cwd=repository, env=git_env)
    if status.returncode:
        return RepairDelivery(status="delivery_failed", message=_result_text(status)[-2000:])
    if not str(status.stdout or "").strip():
        return RepairDelivery(
            status="no_changes",
            ci_status="not_applicable",
            message="Recuperação sem alteração de código; reteste da tarefa original é a prova final.",
        )

    add = _run(executor_module, ["git", "add", "-A"], cwd=repository, env=git_env)
    if add.returncode:
        return RepairDelivery(status="delivery_failed", message=_result_text(add)[-2000:])

    staged = _run(executor_module, ["git", "diff", "--cached", "--quiet"], cwd=repository, env=git_env)
    if staged.returncode == 0:
        return RepairDelivery(status="no_changes", ci_status="not_applicable", message="Nenhuma mudança staged após a recuperação.")
    if staged.returncode not in {0, 1}:
        return RepairDelivery(status="delivery_failed", message=_result_text(staged)[-2000:])

    commit = _run(
        executor_module,
        ["git", "commit", "-m", f"fix(repair): recover task {repair_task.id[:8]}"],
        cwd=repository,
        env=git_env,
    )
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
        "A correção foi produzida pelo agente de recuperação após diagnóstico de causa raiz. "
        "O merge permanece fora deste fluxo automático."
    )
    pr = _run(
        executor_module,
        ["gh", "pr", "create", "--base", project.default_branch, "--head", branch, "--title", title, "--body", body],
        cwd=repository,
        timeout=180,
    )
    if pr.returncode:
        return RepairDelivery(status="delivery_failed", commit_sha=commit_sha, message=_result_text(pr)[-2000:])

    match = _URL_RE.search(_result_text(pr))
    pr_url = match.group(0) if match else str(pr.stdout or "").strip().splitlines()[-1].strip()

    checks = _run(
        executor_module,
        ["gh", "pr", "checks", pr_url, "--watch", "--fail-fast"],
        cwd=repository,
        timeout=ci_timeout,
    )
    if checks.returncode == 0:
        return RepairDelivery(status="ready_to_retest", commit_sha=commit_sha, pull_request_url=pr_url, ci_status="passed")

    text = _result_text(checks)
    normalized = text.casefold()
    no_checks = "no checks" in normalized or "no checks reported" in normalized
    if no_checks:
        return RepairDelivery(
            status="ready_to_retest",
            commit_sha=commit_sha,
            pull_request_url=pr_url,
            ci_status="not_configured",
            message=text[-2000:],
        )
    return RepairDelivery(
        status="ci_failed",
        commit_sha=commit_sha,
        pull_request_url=pr_url,
        ci_status="failed",
        message=text[-4000:],
    )
