import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Project, ProviderCredential, Workspace
from app.services.product_delivery import (
    automatic_delivery_state,
    connection,
    delivery_alerts,
    delivery_due,
    public_delivery_state,
    run_delivery,
)
from app.services.vault import Vault


@pytest.fixture
def delivery_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(name="DevPilot", slug="default")
        db.add(workspace)
        db.flush()
        project = Project(
            workspace_id=workspace.id,
            organization_id=None,
            name="Produto teste",
            slug="produto-teste",
            description="",
            repository_url="https://github.com/a-castilho/produto-teste.git",
            default_branch="main",
            agents_md="",
            codex_config=json.dumps(
                {
                    "project_blueprint": {
                        "databases": ["none"],
                        "backend": ["fastapi"],
                        "frontend": ["none"],
                    },
                    "delivery": automatic_delivery_state(),
                }
            ),
        )
        db.add(project)
        db.commit()
        yield db, workspace, project
    engine.dispose()


def test_regular_user_never_receives_provider_failure_details():
    private = {
        "status": "blocked",
        "url": "",
        "checks": [],
        "last_error": "render: owner ID não configurado",
        "blocked_providers": ["render"],
        "admin_attention": True,
    }

    public = public_delivery_state(private, super_admin=False)

    assert public["status"] == "deploying"
    assert public["last_error"] == ""
    assert "blocked_providers" not in public
    assert "render" not in json.dumps(public)


def test_super_admin_keeps_diagnostic_state():
    private = {
        "status": "blocked",
        "last_error": "Infraestrutura ainda não configurada pela administração.",
        "blocked_providers": ["render"],
    }

    assert public_delivery_state(private, super_admin=True) is private


def test_delivery_uses_existing_cloud_admin_vault_credential(delivery_db):
    db, workspace, _ = delivery_db
    token = "render-token-123456789"
    db.add(
        ProviderCredential(
            workspace_id=workspace.id,
            provider="cloud:render",
            label="cloud-admin",
            encrypted_secret=Vault().encrypt(token),
            models='{"scope":"tea-example"}',
            enabled=True,
        )
    )
    db.commit()

    assert connection(db, workspace.id, "render") == (token, "tea-example")


def test_blocked_delivery_waits_for_admin_then_becomes_due(delivery_db):
    db, workspace, project = delivery_db

    blocked = run_delivery(db, project, "worker:delivery-auto")
    assert blocked["status"] == "blocked"
    assert blocked["admin_attention"] is True
    assert blocked["blocked_providers"] == ["render"]
    assert delivery_due(db, project) is False

    db.add(
        ProviderCredential(
            workspace_id=workspace.id,
            provider="cloud:render",
            label="cloud-admin",
            encrypted_secret=Vault().encrypt("render-token-123456789"),
            models='{"scope":"tea-example"}',
            enabled=True,
        )
    )
    db.commit()
    db.refresh(project)

    assert delivery_due(db, project) is True


def test_only_super_admin_alert_payload_contains_blocked_provider(delivery_db):
    db, workspace, project = delivery_db
    run_delivery(db, project, "worker:delivery-auto")

    alerts = delivery_alerts(db, workspace.id)

    assert len(alerts) == 1
    assert alerts[0]["project_id"] == project.id
    assert alerts[0]["blocked_providers"] == ["render"]
