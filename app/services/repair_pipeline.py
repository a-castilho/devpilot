from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Any, Callable

from app.models import Project, Run, Task, TaskStatus

REPAIR_PIPELINE_MARKER = "[DEVPILOT_REPAIR_PIPELINE_V1]"
REPAIR_BASELINE_PREFIX = "[repair-baseline:"
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


def repair_baseline_block(paths: set[str], *, available: bool = True) -> str:
    payload = json.dumps(
        {"version": 1, "available": bool(available), "paths": sorted(paths)},
        ensure_ascii=False,
        sort_keys=True,
    )
    return f"{REPAIR_BASELINE_PREFIX}{payload}]"


def repair_baseline(task: Task) -> tuple[bool, set[str]]:
    for raw_line in str(getattr(task, "prompt", "") or "").splitlines():
        line = raw_line.strip()
        if not line.startswith(REPAIR_BASELINE_PREFIX) or not line.endswith("]"):
            continue
        raw = line[len(REPAIR_BASELINE_PREFIX):-1]
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            return False, set()
        paths = payload.get("paths") if isinstance(payload, dict) else None
        if not isinstance(paths, list):
            return False, set()
        clean = {str(path) for path in paths if isinstance(path, str) and path}
        return bool(payload.get("available", False)), clean
    return False, set()


def _result_text(result: Any) -> str:
    return f"{getattr(result, 'stdout', '')}\n{getattr(result, 'stderr', '')}".strip()


def _run(executor_module: Any, args: list[str], *, cwd, timeout: int = 120, env: dict[str, str] | None = None):
    try:
        return executor_module.run(args, cwd=cwd, timeout=timeout, env_overrides=env)
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(args, 127, "", str(error))


def _status_paths(stdout: str) -> set[str]:
    """Parse `git status --porcelain=v1 -z` without losing spaces in paths."""
    entries = str(stdout or "").split("\0")
    paths: set[str] = set()
    index = 0
    while index < len(entries):
        entry = entries[index]
        if not entry:
            index += 1
            continue
        if len(entry) < 4:
            index += 1
            continue
        code = entry[:2]
        path = entry[3:]
        if path:
            paths.add(path)
        index += 2 if ("R" in code or "C" in code) else 1
    return paths


def capture_repair_baseline(*, executor_module: Any, project: Project) -> tuple[bool, set[str]]:
    repository = executor_module.repository_path(project)
    if not repository.is_dir():
        return False, set()
    git_env = executor_module.git_environment(project)
    status = _run(
        executor_module,
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=repository,
        env=git_env,
    )
    if status.returncode:
        return False, set()
    return True, _status_paths(status.stdout)


def _safe_path(path: str) -> bool:
    value = str(path or "").strip()
    if not value or "\x00" in value:
        return False
    pure = PurePosixPath(value.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        return False
    if pure.parts[0] == ".git":
        return False
    name = pure.name.casefold()
    if name in {".env", ".npmrc", ".pypirc", "auth.json", "credentials.json", "id_rsa", "id_ed25519"}:
        return False
    if name.startswith(".env.") and name not in {".env.example", ".env.sample", ".env.template"}:
        return False
    if pure.suffix.casefold() in {".pem", ".key", ".p12", ".pfx"}:
        return False
    return True


def _pr_url(text: str) -> str:
    match = _URL_RE.search(str(text or ""))
    return match.group(0) if match else ""


def finalize_repair_delivery(
    *,
    executor_module: Any,
    project: Project,
    repair_task: Task,
    run: Run,
    ci_timeout: int = 600,
) -> RepairDelivery:
    """Materialize a successful repair as scoped commit + PR + CI evidence.

    A baseline is captured when the recovery task is created. Only paths that became
    dirty after that baseline are staged, so pre-existing local changes are preserved
    and never swept into an automatic commit. Environmental repairs may leave no new
    diff; those are returned as ``no_changes`` and the original task becomes the final
    proof. Merge is deliberately excluded from this autonomous boundary.
    """
    repository = executor_module.repository_path(project)
    git_env = executor_module.git_environment(project)

    status = _run(
        executor_module,
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=repository,
        env=git_env,
    )
    if status.returncode:
        return RepairDelivery(status="delivery_failed", message=_result_text(status)[-2000:])

    current_paths = _status_paths(status.stdout)
    baseline_available, baseline_paths = repair_baseline(repair_task)
    if not current_paths:
        return RepairDelivery(
            status="no_changes",
            ci_status="not_applicable",
            message="Recuperação sem alteração de código; reteste da tarefa original é a prova final.",
        )
    if not baseline_available:
        return RepairDelivery(
            status="scope_unknown",
            message="Repair Pipeline: baseline do workspace ausente; nenhuma alteração foi staged automaticamente.",
        )

    candidate_paths = sorted(current_paths - baseline_paths)
    if not candidate_paths:
        return RepairDelivery(
            status="no_changes",
            ci_status="not_applicable",
            message="Somente alterações preexistentes permaneceram no workspace; nenhuma foi incluída na recuperação.",
        )

    unsafe = [path for path in candidate_paths if not _safe_path(path)]
    if unsafe:
        return RepairDelivery(
            status="scope_blocked",
            message="Repair Pipeline bloqueou caminhos inseguros: " + ", ".join(unsafe[:20]),
        )

    add = _run(
        executor_module,
        ["git", "add", "-A", "--", *candidate_paths],
        cwd=repository,
        env=git_env,
    )
    if add.returncode:
        return RepairDelivery(status="delivery_failed", message=_result_text(add)[-2000:])

    staged = _run(executor_module, ["git", "diff", "--cached", "--quiet"], cwd=repository, env=git_env)
    if staged.returncode == 0:
        return RepairDelivery(status="no_changes", ci_status="not_applicable", message="Nenhuma mudança nova ficou staged após aplicar o baseline.")
    if staged.returncode != 1:
        return RepairDelivery(status="delivery_failed", message=_result_text(staged)[-2000:])

    staged_names = _run(
        executor_module,
        ["git", "diff", "--cached", "--name-only", "-z"],
        cwd=repository,
        env=git_env,
    )
    if staged_names.returncode:
        return RepairDelivery(status="delivery_failed", message=_result_text(staged_names)[-2000:])
    staged_paths = {path for path in str(staged_names.stdout or "").split("\0") if path}
    unexpected_staged = sorted(staged_paths - set(candidate_paths))
    if unexpected_staged:
        _run(executor_module, ["git", "reset", "HEAD", "--", *unexpected_staged], cwd=repository, env=git_env)
        return RepairDelivery(
            status="scope_blocked",
            message="Repair Pipeline detectou staging fora do escopo: " + ", ".join(unexpected_staged[:20]),
        )

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
        f"Run: `{run.id}`\n"
        f"Arquivos materializados: {len(staged_paths)}\n\n"
        "A correção foi produzida após diagnóstico de causa raiz. O merge permanece fora do fluxo automático."
    )
    pr = _run(
        executor_module,
        ["gh", "pr", "create", "--base", project.default_branch, "--head", branch, "--title", title, "--body", body],
        cwd=repository,
        timeout=180,
    )
    if pr.returncode:
        existing = _run(
            executor_module,
            ["gh", "pr", "view", branch, "--json", "url", "--jq", ".url"],
            cwd=repository,
            timeout=60,
        )
        pr_url = _pr_url(_result_text(existing)) if existing.returncode == 0 else ""
        if not pr_url:
            return RepairDelivery(status="delivery_failed", commit_sha=commit_sha, message=_result_text(pr)[-2000:])
    else:
        pr_url = _pr_url(_result_text(pr))
        if not pr_url:
            return RepairDelivery(status="delivery_failed", commit_sha=commit_sha, message="Pull Request criada sem URL verificável.")

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
    if "no checks" in normalized or "no checks reported" in normalized:
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


def install_repair_pipeline() -> None:
    """Attach the autonomous pipeline without changing the public recovery API."""
    from app.services import executor
    from app.services import failure_recovery

    if getattr(failure_recovery, "_devpilot_repair_pipeline_installed", False):
        return

    original_prompt: Callable[..., str] = failure_recovery.recovery_prompt
    original_ensure: Callable[..., Task | None] = failure_recovery.ensure_failure_recovery_task
    original_resume: Callable[..., Task | None] = failure_recovery.resume_original_after_recovery

    def repair_prompt(original_task: Task, run: Run | None, failure: dict) -> str:
        base = original_prompt(original_task, run, failure)
        block = incident_block(task=original_task, run=run, failure=failure)
        instruction = (
            "\n\nREPAIR PIPELINE\n"
            "Trate este incidente como contexto persistente. Corrija a causa raiz, execute os testes focados primeiro, "
            "depois as verificações de integração relevantes, e deixe o repositório em estado verificável. "
            "Não altere arquivos que já estavam sujos no baseline do workspace. "
            "Não faça push, PR ou merge manualmente: o DevPilot materializará somente as mudanças novas, "
            "abrirá o PR e registrará a evidência de CI após a execução."
        )
        return f"{block}\n{base}{instruction}"[:100_000]

    def guarded_ensure(db, *, original_task: Task, run: Run | None, failure: dict, actor: str = "worker") -> Task | None:
        recovery = original_ensure(
            db,
            original_task=original_task,
            run=run,
            failure=failure,
            actor=actor,
        )
        if recovery is None or REPAIR_BASELINE_PREFIX in str(recovery.prompt or ""):
            return recovery
        project = db.get(Project, original_task.project_id)
        available, paths = capture_repair_baseline(executor_module=executor, project=project) if project else (False, set())
        recovery.prompt = f"{str(recovery.prompt or '').rstrip()}\n{repair_baseline_block(paths, available=available)}"[:100_000]
        return recovery

    def guarded_resume(db, *, recovery_task: Task, recovery_run: Run) -> Task | None:
        if recovery_run.status != "success":
            return None
        project = db.get(Project, recovery_task.project_id)
        if project is None:
            recovery_run.status = "failed"
            recovery_run.summary = "Repair Pipeline: projeto não encontrado para materializar a entrega."
            recovery_task.status = TaskStatus.failed
            return None

        delivery = finalize_repair_delivery(
            executor_module=executor,
            project=project,
            repair_task=recovery_task,
            run=recovery_run,
        )
        recovery_run.commit_sha = delivery.commit_sha or recovery_run.commit_sha
        recovery_run.pull_request_url = delivery.pull_request_url or recovery_run.pull_request_url
        recovery_run.summary = (
            f"{recovery_run.summary or 'Recuperação concluída.'} "
            f"Repair Pipeline: {delivery.status} / CI: {delivery.ci_status}."
        )

        if delivery.status not in {"ready_to_retest", "no_changes"}:
            recovery_run.status = "failed"
            recovery_task.status = TaskStatus.failed
            return None
        return original_resume(db, recovery_task=recovery_task, recovery_run=recovery_run)

    failure_recovery.recovery_prompt = repair_prompt
    failure_recovery.ensure_failure_recovery_task = guarded_ensure
    failure_recovery.resume_original_after_recovery = guarded_resume
    failure_recovery._devpilot_repair_pipeline_installed = True
