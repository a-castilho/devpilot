import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.connection_models  # noqa: F401
from app.connection_routes import (
    ConnectionAuthorization,
    ConnectionCreate,
    authorize_connection,
    check_connection,
    create_connection,
    list_connections,
    manage_connections,
)
from app.db import Base
from app.models import Project, ProviderCredential, Workspace
from app.security import Principal, Role
from app.services.vault import Vault


@pytest.fixture
def db_context():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(name="DevPilot", slug="default")
        other = Workspace(name="Other", slug="other")
        db.add_all([workspace, other])
        db.flush()
        source = Project(
            workspace_id=workspace.id,
            name="Nave A",
            slug="nave-a",
            description="",
            repository_url="https://example.test/a.git",
        )
        target = Project(
            workspace_id=workspace.id,
            name="Nave B",
            slug="nave-b",
            description="",
            repository_url="https://example.test/b.git",
        )
        foreign = Project(
            workspace_id=other.id,
            name="Foreign",
            slug="foreign",
            description="",
            repository_url="https://example.test/f.git",
        )
        db.add_all([source, target, foreign])
        db.commit()
        yield db, workspace, source, target, foreign
    engine.dispose()


def principal(workspace: Workspace, role: Role = Role.SUPER_ADMIN) -> Principal:
    return Principal(
        user_id="user-1",
        workspace_id=workspace.id,
        email="root@example.com",
        role=role,
    )


def test_connections_are_super_admin_only(db_context):
    _, workspace, *_ = db_context
    with pytest.raises(HTTPException) as error:
        manage_connections(principal(workspace, Role.ADMIN))
    assert error.value.status_code == 403


def test_product_to_product_connection_requires_explicit_authorization(db_context):
    db, workspace, source, target, _ = db_context
    created = create_connection(
        ConnectionCreate(
            source_project_id=source.id,
            target_kind="project",
            target_ref=target.id,
            scopes=["read"],
        ),
        db=db,
        principal=principal(workspace),
    )
    assert created["status"] == "pending"
    assert created["authorized"] is False

    checked = check_connection(created["id"], db=db, principal=principal(workspace))
    assert checked["ok"] is False
    assert checked["connection"]["status"] == "degraded"

    activated = authorize_connection(
        created["id"],
        ConnectionAuthorization(authorized=True),
        db=db,
        principal=principal(workspace),
    )
    assert activated["status"] == "active"
    assert activated["authorized"] is True


def test_cross_workspace_product_target_is_rejected(db_context):
    db, workspace, source, _, foreign = db_context
    with pytest.raises(HTTPException) as error:
        create_connection(
            ConnectionCreate(
                source_project_id=source.id,
                target_kind="project",
                target_ref=foreign.id,
                scopes=["read"],
                authorized=True,
            ),
            db=db,
            principal=principal(workspace),
        )
    assert error.value.status_code == 404


def test_external_connection_reuses_existing_vault_credential(db_context):
    db, workspace, source, *_ = db_context
    credential = ProviderCredential(
        workspace_id=workspace.id,
        provider="cloud:github",
        label="cloud-admin",
        encrypted_secret=Vault().encrypt("github-secret-token-123"),
        models="{}",
        enabled=True,
    )
    db.add(credential)
    db.commit()

    created = create_connection(
        ConnectionCreate(
            source_project_id=source.id,
            target_kind="provider",
            target_ref="github",
            scopes=["repository:read"],
            authorized=True,
        ),
        db=db,
        principal=principal(workspace),
    )
    assert created["status"] == "active"
    assert "secret" not in created
    assert "provider_credential_id" not in created

    rows = list_connections(db=db, principal=principal(workspace))
    assert len(rows) == 1
    assert rows[0]["target_ref"] == "github"


def test_provider_without_configured_credential_is_rejected(db_context):
    db, workspace, source, *_ = db_context
    with pytest.raises(HTTPException) as error:
        create_connection(
            ConnectionCreate(
                source_project_id=source.id,
                target_kind="provider",
                target_ref="vercel",
                scopes=["deploy"],
                authorized=True,
            ),
            db=db,
            principal=principal(workspace),
        )
    assert error.value.status_code == 409
