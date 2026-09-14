import json
import os
import sqlite3
import tempfile

_runtime_db = tempfile.NamedTemporaryFile(prefix="devpilot-jobpilot-test-", suffix=".db", delete=False)
_runtime_db.close()
os.environ["DEVPILOT_DATABASE_URL"] = f"sqlite:///{_runtime_db.name}"

# app/__init__.py refreshes Codex auth at import time. Seed only the table that
# read requires so this focused unit test remains isolated from the application DB.
with sqlite3.connect(_runtime_db.name) as connection:
    connection.execute(
        """
        CREATE TABLE provider_credentials (
            id VARCHAR(36) PRIMARY KEY,
            workspace_id VARCHAR(36) NOT NULL,
            provider VARCHAR(40) NOT NULL,
            label VARCHAR(120) NOT NULL,
            encrypted_secret TEXT NOT NULL,
            models TEXT NOT NULL,
            enabled BOOLEAN NOT NULL,
            created_at DATETIME NOT NULL
        )
        """
    )

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Project, User, Workspace
from app.services.bootstrap_projects import bootstrap_jobpilot_project


def test_bootstrap_jobpilot_project_creates_managed_project_once():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        workspace = Workspace(name="DevPilot", slug="default")
        db.add(workspace)
        db.flush()
        admin = User(
            workspace_id=workspace.id,
            email="admin@example.invalid",
            password_hash="test-only",
            role="SUPER_ADMIN",
            active=True,
        )
        db.add(admin)
        db.commit()
        admin_id = admin.id

    assert bootstrap_jobpilot_project(engine) is True
    assert bootstrap_jobpilot_project(engine) is False

    with Session(engine) as db:
        project = db.scalar(select(Project).where(Project.slug == "jobpilot"))
        assert project is not None
        assert project.name == "JobPilot"
        assert project.repository_url == ""
        assert project.default_branch == "main"
        assert project.owner_user_id == admin_id
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
