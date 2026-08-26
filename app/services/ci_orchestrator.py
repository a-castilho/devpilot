from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import select

from app.models import Project, Repository, Task, TaskStatus
from app.services.audit import record


CI_SOURCE = "ci-recovery"
CI_MARKER = "[DEVPILOT_CI_RECOVERY]"
MAX_BRANCH_RECOVERIES = 3
BRANCH_WINDOW_HOURS = 6


@dataclass(frozen=True)
class CIFailure:
    repository_full_name: str
    workflow_name: str
    run_id: int
    run_attempt: int
    head_sha: str
    head_branch: str
    conclusion: str
    html_url: str

    @property
    def fingerprint(self) -> str:
        raw = "|".join(
            (
                self.repository_full_name.lower(),
                self.workflow_name,
                str(self.run_id),
                str(self.run_attempt),
                self.head_sha,
                self.conclusion,
            )
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    @property
    def fingerprint_marker(self) -> str:
        return f"[ci-failure:{self.fingerprint}]"

    @property
    def branch_marker(self) -> str:
        branch = self.head_branch or "detached"
        return f"[ci-branch:{branch}]"


def failure_from_workflow_run(payload: dict) -> CIFailure | None:
    if str(payload.get("action") or "") != "completed":
        return None
    run = payload.get("workflow_run") or {}
    conclusion = str(run.get("conclusion") or "").lower()
    if conclusion not in {"failure", "timed_out"}:
        return None
    repository = payload.get("repository") or {}
    full_name = str(repository.get("full_name") or "").strip()
    run_id = int(run.get("id") or 0)
    if not full_name or not run_id:
        return None
    return CIFailure(
        repository_full_name=full_name,
        workflow_name=str(run.get("name") or "GitHub Actions"),
        run_id=run_id,
        run_attempt=max(1, int(run.get("run_attempt") or 1)),
        head_sha=str(run.get("head_sha") or "").strip(),
        head_branch=str(run.get("head_branch") or "").strip(),
        conclusion=conclusion,
        html_url=str(run.get("html_url") or "").strip(),
    )


def _normalized_repo_url(value: str) -> str:
    text = str(value or "").strip().removesuffix(".git").rstrip("/")
    if text.startswith("git@github.com:"):
        return "github.com/" + text.split(":", 1)[1].lower()
    parsed = urlparse(text)
    if parsed.hostname:
        return f"{parsed.hostname.lower()}{parsed.path}".rstrip("/").lower()
    return text.lower()


def _find_project(db, repository_full_name: str) -> Project | None:
    repository = db.scalar(
        select(Repository).where(Repository.full_name == repository_full_name).limit(1)
    )
    if repository and repository.project_id:
        project = db.get(Project, repository.project_id)
        if project:
            return project

    expected = f"github.com/{repository_full_name}".lower()
    projects = db.scalars(select(Project)).all()
    return next(
        (project for project in projects if _normalized_repo_url(project.repository_url) == expected),
        None,
    )


def _recovery_prompt(failure: CIFailure) -> str:
    return (
        f"{CI_MARKER}\n"
        "[DEVPILOT_MODE=fix]\n"
        f"{failure.fingerprint_marker}\n"
        f"{failure.branch_marker}\n"
        f"[ci-head:{failure.head_sha or 'unknown'}]\n"
        f"[ci-run:{failure.run_id}:{failure.run_attempt}]\n"
        "O GitHub Actions detectou uma falha real de CI. Investigue a execução indicada, identifique "
        "a causa raiz e corrija somente o necessário no repositório. Preserve compatibilidade e não "
        "desative, ignore ou enfraqueça testes/gates para obter verde. Rode testes focados durante o "
        "diagnóstico e, antes de concluir, execute `bash scripts/test-all.sh`. Faça commit/push na branch "
        "de execução já gerenciada pelo DevPilot e deixe a revalidação do GitHub Actions decidir o gate.\n\n"
        f"Repositório: {failure.repository_full_name}\n"
        f"Workflow: {failure.workflow_name}\n"
        f"Conclusão: {failure.conclusion}\n"
        f"Branch: {failure.head_branch or 'desconhecida'}\n"
        f"SHA: {failure.head_sha or 'desconhecido'}\n"
        f"Run: {failure.html_url or failure.run_id}\n"
    )[:100_000]


def enqueue_ci_failure(db, failure: CIFailure) -> dict:
    project = _find_project(db, failure.repository_full_name)
    if not project:
        return {"status": "ignored", "reason": "project_not_managed"}

    existing = db.scalar(
        select(Task)
        .where(
            Task.project_id == project.id,
            Task.source == CI_SOURCE,
            Task.prompt.contains(failure.fingerprint_marker),
        )
        .limit(1)
    )
    if existing:
        return {"status": "duplicate", "task_id": existing.id}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=BRANCH_WINDOW_HOURS)
    recent = list(
        db.scalars(
            select(Task).where(
                Task.project_id == project.id,
                Task.source == CI_SOURCE,
                Task.created_at >= cutoff,
                Task.prompt.contains(failure.branch_marker),
            )
        ).all()
    )
    if len(recent) >= MAX_BRANCH_RECOVERIES:
        record(
            db,
            workspace_id=project.workspace_id,
            project_id=project.id,
            actor="ci-orchestrator",
            action="ci.recovery.circuit_open",
            outcome="blocked",
            details={
                "repository": failure.repository_full_name,
                "branch": failure.head_branch,
                "run_id": failure.run_id,
                "recoveries_in_window": len(recent),
                "window_hours": BRANCH_WINDOW_HOURS,
            },
        )
        db.commit()
        return {"status": "blocked", "reason": "circuit_breaker"}

    task = Task(
        workspace_id=project.workspace_id,
        owner_user_id=project.owner_user_id,
        project_id=project.id,
        title=f"Corrigir CI · {failure.workflow_name}"[:240],
        prompt=_recovery_prompt(failure),
        source=CI_SOURCE,
        status=TaskStatus.queued,
        priority=100,
        requires_approval=False,
    )
    db.add(task)
    db.flush()
    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        task_id=task.id,
        actor="ci-orchestrator",
        action="ci.recovery.queued",
        outcome="queued",
        details={
            "repository": failure.repository_full_name,
            "workflow": failure.workflow_name,
            "run_id": failure.run_id,
            "run_attempt": failure.run_attempt,
            "head_sha": failure.head_sha,
            "head_branch": failure.head_branch,
            "fingerprint": failure.fingerprint,
        },
    )
    db.commit()
    return {"status": "queued", "task_id": task.id}
