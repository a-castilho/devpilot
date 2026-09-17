from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from app.config import get_settings
from app.models import Project, Task
from app.services import executor as executor_service
from app.services.task_flow import execution_branch, is_analysis_action_task, is_verification_analysis


def _disabled_result(mode: str) -> dict:
    return {
        "mode": mode,
        "exit_code": 78,
        "summary": "A execução automática está desativada; o fluxo foi interrompido sem simular sucesso.",
        "client_report": "Resumo para o cliente\nA etapa automática não foi executada porque a execução está desativada.",
    }


def _switch_execution_branch(repository: Path, target_branch: str) -> None:
    current = executor_service.run(["git", "branch", "--show-current"], cwd=repository)
    if current.returncode == 0 and current.stdout.strip() == target_branch:
        return
    checkout = executor_service.run(["git", "switch", target_branch], cwd=repository)
    if checkout.returncode == 0:
        return
    fetch = executor_service.run(["git", "fetch", "origin", target_branch], cwd=repository)
    if fetch.returncode == 0:
        checkout = executor_service.run(["git", "switch", "-C", target_branch, f"origin/{target_branch}"], cwd=repository)
        if checkout.returncode == 0:
            return
    detail = checkout.stderr.strip() or fetch.stderr.strip()
    raise RuntimeError(detail or f"Unable to recover execution branch {target_branch}")


def _execute_action(project: Project, task: Task) -> dict:
    if not get_settings().execution_enabled:
        return _disabled_result("flow-execution-disabled")
    path = executor_service.ensure_repository(project)
    if project.agents_md:
        (path / "AGENTS.md").write_text(project.agents_md, encoding="utf-8")
    target_branch = execution_branch(task)
    if target_branch:
        _switch_execution_branch(path, target_branch)
        branch = target_branch
    else:
        branch = task.branch_name or f"devpilot/{task.id[:8]}"
        checkout = executor_service.run(["git", "switch", "-C", branch, f"origin/{project.default_branch}"], cwd=path)
        if checkout.returncode:
            raise RuntimeError(checkout.stderr.strip() or "Unable to create task branch")
    result = executor_service.run(executor_service.codex_command(project, executor_service.development_prompt(task)), cwd=path, timeout=executor_service.task_timeout(project))
    client_report = executor_service.extract_client_report(result.stdout)
    return {"mode": "execute", "exit_code": result.returncode, "summary": "Execução concluída. O fluxo seguirá para validação automática." if result.returncode == 0 else "A execução terminou com falha; o fluxo automático foi interrompido.", "client_report": client_report, "stdout": result.stdout[-100_000:], "stderr": result.stderr[-20_000:], "branch": branch}


def _copy_untracked(repository: Path, analysis_path: Path) -> None:
    untracked = executor_service.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=repository)
    if untracked.returncode:
        raise RuntimeError(untracked.stderr.strip() or "Unable to list untracked execution files")
    for relative in (line.strip() for line in untracked.stdout.splitlines()):
        if not relative:
            continue
        source = repository / relative
        destination = analysis_path / relative
        if source.is_dir(): shutil.copytree(source, destination, dirs_exist_ok=True)
        elif source.exists():
            destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, destination)


def _execute_verification(project: Project, task: Task) -> dict:
    if not get_settings().execution_enabled:
        return _disabled_result("analysis-read-only-disabled")
    repository = executor_service.ensure_repository(project)
    target_branch = execution_branch(task)
    if not target_branch:
        raise RuntimeError("Verification task is missing the execution branch marker")
    _switch_execution_branch(repository, target_branch)
    with tempfile.TemporaryDirectory(prefix=f"devpilot-verify-{task.id[:8]}-") as temp_dir:
        analysis_path = Path(temp_dir) / "repository"
        worktree = executor_service.run(["git", "worktree", "add", "--detach", str(analysis_path), "HEAD"], cwd=repository)
        if worktree.returncode: raise RuntimeError(worktree.stderr.strip() or "Unable to prepare verification workspace")
        try:
            patch = executor_service.run(["git", "diff", "--binary", "HEAD"], cwd=repository)
            if patch.returncode: raise RuntimeError(patch.stderr.strip() or "Unable to snapshot execution changes")
            if patch.stdout:
                patch_path = Path(temp_dir) / "execution.patch"; patch_path.write_text(patch.stdout, encoding="utf-8")
                applied = executor_service.run(["git", "apply", "--binary", "--whitespace=nowarn", str(patch_path)], cwd=analysis_path)
                if applied.returncode: raise RuntimeError(applied.stderr.strip() or "Unable to apply execution snapshot")
            _copy_untracked(repository, analysis_path)
            rules = f"\n\nProject instructions (reference only):\n{project.agents_md}" if project.agents_md else ""
            prompt = f"Task: {task.title}\n\n{task.prompt}{rules}\n\nThis is the REQUIRED POST-EXECUTION READ-ONLY VERIFICATION. Inspect the exact working-tree snapshot produced by the preceding implementation. Verify with concrete evidence that the original findings were corrected, run non-destructive checks when useful, identify regressions or remaining gaps, and prioritize only what still needs correction. Do not edit, create, delete, rename, commit, push, merge, or deploy project files.\n\n{executor_service.CLIENT_REPORT_INSTRUCTIONS}"
            result = executor_service.run(executor_service.codex_command(project, prompt), cwd=analysis_path, timeout=executor_service.task_timeout(project))
            client_report = executor_service.extract_client_report(result.stdout)
            return {"mode": "analysis-read-only", "exit_code": result.returncode, "summary": "Validação pós-execução concluída. O fluxo seguirá para a correção final." if result.returncode == 0 else "A validação pós-execução falhou; o fluxo automático foi interrompido.", "client_report": client_report, "stdout": result.stdout[-100_000:], "stderr": result.stderr[-20_000:], "persisted_changes": False, "branch": target_branch}
        finally:
            executor_service.run(["git", "worktree", "remove", "--force", str(analysis_path)], cwd=repository)
            executor_service.run(["git", "worktree", "prune"], cwd=repository)


def execute(project: Project, task: Task) -> dict:
    if is_verification_analysis(task): return _execute_verification(project, task)
    if is_analysis_action_task(task): return _execute_action(project, task)
    raise RuntimeError("Unsupported alternating flow task")
