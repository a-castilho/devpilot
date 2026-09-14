import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Project, Workspace
from app.services.bootstrap_projects import bootstrap_jobpilot_project


def test_bootstrap_jobpilot_project_creates_managed_project_once():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    assert bootstrap_jobpilot_project(engine) is True
    assert bootstrap_jobpilot_project(engine) is False

    with Session(engine) as db:
        project = db.scalar(select(Project).where(Project.slug == "jobpilot"))
        assert project is not None
        assert project.name == "JobPilot"
        assert project.repository_url == ""
        assert project.default_branch == "main"
        assert "automação de candidaturas" in project.description.lower()

        config = json.loads(project.codex_config)
        assert config["repository_pending"] is True
        assert config["repository_mode"] == "deferred"
        assert config["generation_strategy"] == "from_scratch"
        assert config["stack"]["backend"] == "FastAPI"
        assert config["stack"]["automation"] == "Playwright"

        workspace = db.scalar(select(Workspace).where(Workspace.slug == "default"))
        assert workspace is not None
        assert project.workspace_id == workspace.id
