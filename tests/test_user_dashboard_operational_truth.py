from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import overview
from app.db import Base
from app.models import Project, Task, TaskStatus, Workspace


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "app" / "static" / "index.html"
APP_JS = ROOT / "app" / "static" / "app.js"
STYLES = ROOT / "app" / "static" / "styles.css"


def _project(db: Session, workspace: Workspace, slug: str) -> Project:
    item = Project(
        workspace_id=workspace.id,
        name=slug,
        slug=slug,
        repository_url=f"https://github.com/example/{slug}.git",
    )
    db.add(item)
    db.flush()
    return item


def _task(db: Session, workspace: Workspace, project: Project, status: TaskStatus, index: int) -> None:
    db.add(
        Task(
            workspace_id=workspace.id,
            project_id=project.id,
            title=f"{status.value}-{index}",
            prompt="dashboard operational truth",
            status=status,
        )
    )


def test_overview_returns_complete_workspace_scoped_status_counts():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        workspace = Workspace(name="DevPilot", slug="default")
        other_workspace = Workspace(name="Other", slug="other")
        db.add_all([workspace, other_workspace])
        db.flush()
        project = _project(db, workspace, "devpilot")
        other_project = _project(db, other_workspace, "other-project")

        statuses = [
            TaskStatus.queued,
            TaskStatus.planning,
            TaskStatus.running,
            TaskStatus.review,
            TaskStatus.awaiting_approval,
            TaskStatus.failed,
            TaskStatus.blocked,
            TaskStatus.completed,
            TaskStatus.completed,
        ]
        for index, task_status in enumerate(statuses):
            _task(db, workspace, project, task_status, index)
        _task(db, other_workspace, other_project, TaskStatus.completed, 99)
        db.commit()

        result = overview(db)

    assert result["tasks"] == 9
    assert result["projects"] == 1
    assert result["active"] == 4
    assert result["completed"] == 2
    assert result["attention"] == {"approvals": 1, "failed": 2, "active": 4}
    assert set(result["status_counts"]) == {status.value for status in TaskStatus}
    assert result["status_counts"]["planning"] == 1
    assert result["status_counts"]["completed"] == 2
    engine.dispose()


def test_dashboard_uses_authoritative_totals_with_legacy_fallback():
    source = APP_JS.read_text(encoding="utf-8")

    assert "overview.status_counts" in source
    assert "overview.attention?.approvals" in source
    assert "overview.attention?.failed" in source
    assert "overview.attention?.active" in source
    assert "Os totais não são inferidos desta página." in source
    assert "['queued', 'planning', 'running', 'review']" in source
    assert "completed: tasks.filter(task => normalized(task.status) === 'completed')" in source


def test_dashboard_exposes_accessible_attention_and_sync_feedback():
    html = DASHBOARD.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")
    source = APP_JS.read_text(encoding="utf-8")

    assert '<button type="button" class="attention-card" id="attention-card"' in html
    assert 'id="system-overview-status"' in html
    assert 'id="system-overview-detail"' in html
    assert "Progresso geral" in html
    assert "setOverviewSyncState('loading')" in source
    assert "setOverviewSyncState('ready')" in source
    assert "setOverviewSyncState('error', message)" in source
    assert ".attention-card:focus-visible" in styles
    assert ".system-overview.is-error" in styles
