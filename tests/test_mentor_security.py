import json
import subprocess
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.mentor_models  # noqa: F401
from app.db import Base
from app.mentor_models import LearningEvent, LearningSkill, SecurityFinding, SecurityScan
from app.mentor_routes import (
    MentorRequest,
    SecurityFixRequest,
    SkillUpdate,
    mentor,
    security_fix,
    update_skill,
)
from app.models import Project, Task, TaskStatus, User, Workspace
from app.security import Principal, Role
from app.services import security_scanner


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


def test_teach_mode_creates_read_only_task_and_learning_event(db, monkeypatch):
    _ws, _user, project, principal = seed(db)
    snapshot = SimpleNamespace(id="snapshot-1")
    summary = {"commit_sha": "abc", "sampled_files": ["app/main.py"], "target_excerpt": ""}
    monkeypatch.setattr(
        "app.mentor_routes.get_or_create_snapshot",
        lambda *args, **kwargs: (snapshot, summary),
    )

    result = mentor(
        project.id,
        MentorRequest(
            mode="teach",
            question="Me ensine o fluxo de autenticação",
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


def test_static_security_scanner_finds_risky_patterns(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "app.py").write_text(
        'import subprocess\nsubprocess.run("echo hi", shell=True)\npassword = "super-secret-value"\n'
    )
    (repo / ".env").write_text("TOKEN=do-not-read")
    (repo / "Dockerfile").write_text('FROM python:3.12\nCMD ["python","app.py"]\n')
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)

    project = SimpleNamespace(default_branch="main")
    monkeypatch.setattr(security_scanner, "ensure_repository", lambda _project: repo)
    monkeypatch.setattr(
        security_scanner,
        "repository_commit",
        lambda _repo, _branch: "deadbeef",
    )
    result = security_scanner.scan_project(project)
    rules = {item["rule_id"] for item in result["findings"]}
    assert {"SEC000", "SEC002", "SEC003", "SEC011"}.issubset(rules)
    assert "do-not-read" not in json.dumps(result)


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
