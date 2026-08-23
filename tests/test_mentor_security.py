import json
import subprocess
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.mentor_models  # noqa: F401
from app import worker
from app.db import Base
from app.mentor_models import LearningEvent, LearningSkill, SecurityFinding, SecurityScan
from app.mentor_routes import (
    MentorRequest,
    SecurityFixRequest,
    SkillUpdate,
    mentor,
    security_fix,
    security_scan,
    update_skill,
)
from app.models import Project, Task, TaskStatus, User, Workspace
from app.security import Principal, Role
from app.services import mentor_executor, project_context, security_scanner


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def seed(db: Session, role=Role.ADMIN):
    ws = Workspace(name="DevPilot", slug="default")
    db.add(ws)
    db.flush()
    user = User(
        workspace_id=ws.id,
        email="mentor@example.com",
        password_hash="x",
        role=role.value,
    )
    db.add(user)
    db.flush()
    project = Project(
        workspace_id=ws.id,
        name="Projeto teste",
        slug="projeto-teste",
        repository_url="https://github.com/example/repo.git",
        default_branch="main",
    )
    db.add(project)
    db.commit()
    principal = Principal(user_id=user.id, workspace_id=ws.id, email=user.email, role=role)
    return ws, user, project, principal


def init_git_repo(path):
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tests@devpilot.local"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "DevPilot Tests"], cwd=path, check=True)


def commit_all(path, message="fixture"):
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=path, check=True, capture_output=True)


def test_teach_mode_creates_read_only_task_without_persisting_source_excerpt(db, monkeypatch):
    _ws, _user, project, principal = seed(db)
    snapshot = SimpleNamespace(id="snapshot-1")
    sha = "a" * 40
    summary = {
        "commit_sha": sha,
        "sampled_files": ["app/main.py"],
        "target": "app/main.py",
        "target_excerpt": 'password="should-never-be-persisted"',
    }
    monkeypatch.setattr(
        "app.mentor_routes.get_or_create_snapshot",
        lambda *args, **kwargs: (snapshot, summary),
    )

    result = mentor(
        project.id,
        MentorRequest(
            mode="teach",
            question="Me ensine o fluxo de autenticação",
            target="app/main.py",
            skill="FastAPI",
            level="beginner",
        ),
        db,
        principal,
        None,
    )

    task = result["task"]
    assert task.status is TaskStatus.queued
    assert task.requires_approval is False
    assert "[DEVPILOT_MODE=analysis-read-only]" in task.prompt
    assert f"[DEVPILOT_REF={sha}]" in task.prompt
    assert f'"commit_sha": "{sha}"' in task.prompt
    assert "should-never-be-persisted" not in task.prompt
    assert "target_excerpt" not in task.prompt
    assert "nível beginner" in task.prompt
    assert db.query(LearningEvent).filter_by(project_id=project.id).count() == 1


def test_analyst_cannot_start_execution_from_mentor(db):
    _ws, _user, project, principal = seed(db, Role.ANALYST)
    with pytest.raises(HTTPException) as error:
        mentor(
            project.id,
            MentorRequest(mode="execute", question="Atualize a autenticação"),
            db,
            principal,
            None,
        )
    assert error.value.status_code == 403
    assert db.query(Task).count() == 0


def test_skill_profile_is_project_scoped(db):
    _ws, _user, project, principal = seed(db)
    item = update_skill(
        project.id,
        "Docker",
        SkillUpdate(
            level="advanced",
            confidence=85,
            concepts_seen=["multi-stage"],
            needs_review=["rootless"],
        ),
        db,
        principal,
    )
    assert item.level == "advanced"
    assert json.loads(item.concepts_seen) == ["multi-stage"]
    assert db.query(LearningSkill).filter_by(project_id=project.id, skill="Docker").count() == 1


def test_viewer_cannot_update_learning_profile(db):
    _ws, _user, project, principal = seed(db, Role.VIEWER)
    with pytest.raises(HTTPException) as error:
        update_skill(
            project.id,
            "Docker",
            SkillUpdate(level="beginner", confidence=40),
            db,
            principal,
        )
    assert error.value.status_code == 403
    assert db.query(LearningSkill).count() == 0


def test_project_context_is_pinned_to_commit_and_redacts_target(tmp_path, monkeypatch):
    repo = tmp_path / "context-repo"
    repo.mkdir()
    init_git_repo(repo)
    (repo / "app.py").write_text(
        'password = "committed-secret-value"\nauthorization: Bearer ghp_123456789012345678901234567890\n'
    )
    commit_all(repo)
    (repo / "app.py").write_text("dirty-marker-that-must-not-be-read\n")

    project = SimpleNamespace(
        id="project-context-test",
        name="Context test",
        description="",
        default_branch="main",
    )
    monkeypatch.setattr(project_context, "ensure_repository", lambda _project: repo)
    summary = project_context.build_project_context(project, target="app.py")

    assert "dirty-marker-that-must-not-be-read" not in summary["target_excerpt"]
    assert "committed-secret-value" not in summary["target_excerpt"]
    assert "ghp_123456789012345678901234567890" not in summary["target_excerpt"]
    assert "[REDACTED]" in summary["target_excerpt"]


def test_static_security_scanner_finds_risky_patterns(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    (repo / "app.py").write_text(
        'import subprocess\nsubprocess.run("echo hi", shell=True)\npassword = "super-secret-value"\n'
    )
    (repo / ".env").write_text("TOKEN=do-not-read")
    (repo / "Dockerfile").write_text('FROM python:3.12\nCMD ["python","app.py"]\n')
    (repo / "README.md").write_text("Example only: subprocess.run('echo', shell=True)\n")
    commit_all(repo)

    project = SimpleNamespace(id="security-test", default_branch="main")
    monkeypatch.setattr(project_context, "ensure_repository", lambda _project: repo)
    result = security_scanner.scan_project(project)
    rules = {item["rule_id"] for item in result["findings"]}
    assert {"SEC000", "SEC002", "SEC003", "SEC011"}.issubset(rules)
    assert "do-not-read" not in json.dumps(result)
    assert not any(
        item["file_path"] == "README.md" and item["rule_id"] == "SEC003"
        for item in result["findings"]
    )


def test_mentor_executor_uses_context_commit_and_respects_execution_switch(monkeypatch):
    sha = "b" * 40
    task = SimpleNamespace(prompt=f'context={{"commit_sha": "{sha}"}}')
    project = SimpleNamespace(default_branch="main")
    assert mentor_executor._mentor_ref(task, project) == sha

    monkeypatch.setattr(
        mentor_executor,
        "get_settings",
        lambda: SimpleNamespace(execution_enabled=False),
    )
    monkeypatch.setattr(
        mentor_executor.executor,
        "ensure_repository",
        lambda _project: (_ for _ in ()).throw(AssertionError("repository must not be touched")),
    )
    disabled_task = SimpleNamespace(id="12345678", prompt=task.prompt)
    result = mentor_executor.execute_mentor_task(project, disabled_task)
    assert result["mode"] == "analysis-mentor-read-only-disabled"
    assert result["persisted_changes"] is False


def test_worker_routes_read_only_mentor_away_from_generic_executor(monkeypatch):
    project = SimpleNamespace(default_branch="main")
    mentor_task = SimpleNamespace(
        source="mentor",
        prompt="[DEVPILOT_MODE=analysis-read-only]\nEnsine este projeto",
    )
    execute_task = SimpleNamespace(source="mentor", prompt="Implemente a alteração")

    monkeypatch.setattr(worker, "execute_mentor_task", lambda _project, _task: {"mode": "mentor"})
    monkeypatch.setattr(worker, "execute_task", lambda _project, _task: {"mode": "generic"})

    assert worker.execute_queued_task(project, mentor_task)["mode"] == "mentor"
    assert worker.execute_queued_task(project, execute_task)["mode"] == "generic"
    assert worker._mentor_failure_result()["persisted_changes"] is False


def test_security_scan_supersedes_previous_open_findings(db, monkeypatch):
    ws, user, project, principal = seed(db)
    old_scan = SecurityScan(
        workspace_id=ws.id,
        project_id=project.id,
        requested_by_user_id=user.id,
        commit_sha="old",
    )
    db.add(old_scan)
    db.flush()
    old_finding = SecurityFinding(
        workspace_id=ws.id,
        project_id=project.id,
        scan_id=old_scan.id,
        rule_id="SEC003",
        severity="high",
        category="code-execution",
        title="Achado antigo",
        file_path="app/old.py",
        line_number=4,
        evidence="shell=True",
        impact="injeção",
        remediation="use lista de argumentos",
        status="open",
    )
    db.add(old_finding)
    db.commit()

    monkeypatch.setattr(
        "app.mentor_routes.scan_project",
        lambda _project: {
            "commit_sha": "c" * 40,
            "counts": {"critical": 0, "high": 0, "medium": 1, "low": 0},
            "coverage": {
                "tracked_files": 3,
                "scanned_text_files": 2,
                "skipped_large_files": 0,
                "dependency_manifests": [],
                "dependency_vulnerability_database": "not-enabled",
            },
            "findings": [
                {
                    "rule_id": "SEC011",
                    "severity": "medium",
                    "category": "container",
                    "title": "Container sem USER não-root explícito",
                    "file_path": "Dockerfile",
                    "line_number": 1,
                    "evidence": "Dockerfile sem diretiva USER",
                    "impact": "impacto",
                    "remediation": "adicione USER",
                }
            ],
        },
    )

    result = security_scan(project.id, db, principal)
    db.refresh(old_finding)
    assert old_finding.status == "superseded"
    assert len(result["findings"]) == 1
    assert result["findings"][0].status == "open"

    with pytest.raises(HTTPException) as error:
        security_fix(
            project.id,
            old_finding.id,
            SecurityFixRequest(apply=True),
            db,
            principal,
        )
    assert error.value.status_code == 409


def test_security_fix_requires_explicit_apply_and_then_approval(db):
    ws, user, project, principal = seed(db)
    scan = SecurityScan(
        workspace_id=ws.id,
        project_id=project.id,
        requested_by_user_id=user.id,
        commit_sha="abc",
    )
    db.add(scan)
    db.flush()
    finding = SecurityFinding(
        workspace_id=ws.id,
        project_id=project.id,
        scan_id=scan.id,
        rule_id="SEC003",
        severity="high",
        category="code-execution",
        title="Subprocess com shell=True",
        file_path="app/x.py",
        line_number=10,
        evidence="subprocess.run(..., shell=True)",
        impact="injeção",
        remediation="use lista de argumentos",
    )
    db.add(finding)
    db.commit()

    proposal = security_fix(
        project.id,
        finding.id,
        SecurityFixRequest(apply=False),
        db,
        principal,
    )
    assert proposal["apply"] is False
    assert db.query(Task).count() == 0

    created = security_fix(
        project.id,
        finding.id,
        SecurityFixRequest(apply=True),
        db,
        principal,
    )
    assert created["task"].status is TaskStatus.awaiting_approval
    assert created["task"].requires_approval is True
