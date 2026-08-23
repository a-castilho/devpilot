from __future__ import annotations

import re
import tempfile
from pathlib import Path

from app.models import Project, Task
from app.services import executor

MENTOR_REF_RE = re.compile(r"\[DEVPILOT_REF=([0-9a-f]{40})\]", re.IGNORECASE)
MENTOR_CONTEXT_REF_RE = re.compile(r'"commit_sha"\s*:\s*"([0-9a-f]{40})"', re.IGNORECASE)


def _mentor_ref(task: Task, project: Project) -> str:
    prompt = str(task.prompt or "")
    for pattern in (MENTOR_REF_RE, MENTOR_CONTEXT_REF_RE):
        match = pattern.search(prompt)
        if match:
            return match.group(1).lower()
    return f"origin/{project.default_branch}"


def execute_mentor_task(project: Project, task: Task) -> dict:
    """Execute a Mentor session without persisting any repository mutation."""
    repository = executor.ensure_repository(project)
    ref = _mentor_ref(task, project)

    with tempfile.TemporaryDirectory(prefix=f"devpilot-mentor-{task.id[:8]}-") as temp_dir:
        analysis_path = Path(temp_dir) / "repository"
        worktree = executor.run(
            ["git", "worktree", "add", "--detach", str(analysis_path), ref],
            cwd=repository,
            timeout=120,
        )
        if worktree.returncode:
            raise RuntimeError(
                worktree.stderr.strip() or "Unable to prepare isolated Mentor workspace"
            )

        try:
            project_rules = (
                f"\n\nProject instructions (reference only):\n{project.agents_md}"
                if project.agents_md
                else ""
            )
            prompt = (
                f"Task: {task.title}\n\n{task.prompt}{project_rules}\n\n"
                "MENTOR EXECUTION RULES. This session is strictly read-only. Inspect the repository "
                "at the checked-out commit and follow the teaching mode requested above. Never edit, "
                "create, delete or rename files. Never run a command intended to mutate project state, "
                "install dependencies, commit, push, merge or deploy. You may run safe read-only inspection "
                "commands when needed. Prefer concrete evidence from the repository, explain uncertainty, "
                "and adapt technical depth to the learner level. Do not use the commercial client-report "
                "template unless the user explicitly asks for it."
            )
            result = executor.run(
                executor.codex_command(project, prompt),
                cwd=analysis_path,
                timeout=executor.task_timeout(project),
            )
            status = executor.run(["git", "status", "--porcelain"], cwd=analysis_path, timeout=30)
            attempted_changes = bool(status.stdout.strip()) if status.returncode == 0 else None
            response = executor.extract_client_report(result.stdout)
            return {
                "mode": "analysis-mentor-read-only",
                "exit_code": result.returncode,
                "summary": (
                    "Sessão do DevPilot Mentor concluída."
                    if result.returncode == 0
                    else "A sessão do DevPilot Mentor terminou com falha; consulte os detalhes técnicos."
                ),
                "client_report": response,
                "stdout": result.stdout[-100_000:],
                "stderr": result.stderr[-20_000:],
                "attempted_changes": attempted_changes,
                "persisted_changes": False,
                "branch": "",
                "mentor_ref": ref,
                "agents_md_generated": False,
            }
        finally:
            executor.run(
                ["git", "worktree", "remove", "--force", str(analysis_path)],
                cwd=repository,
                timeout=60,
            )
            executor.run(["git", "worktree", "prune"], cwd=repository, timeout=30)
