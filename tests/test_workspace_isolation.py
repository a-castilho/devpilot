import json

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Project, ProviderCredential, Workspace
from app.project_provisioning_routes import ProjectProvisionCreate, provision_project
from app.provider_models_routes import connection_models, model_catalog
from app.security import Principal, Role
from app.services.workspace_scope import workspace_for_principal


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _principal(workspace_id: str, role: Role = Role.OWNER) -> Principal:
    return Principal(
        user_id=f"user-{workspace_id}",
        workspace_id=workspace_id,
        email=f"{workspace_id}@example.com",
        role=role,
    )


def _workspaces(db: Session) -> tuple[Workspace, Workspace]:
    default = Workspace(name="DevPilot", slug="default")
    customer = Workspace(name="Cliente B", slug="cliente-b")
    db.add_all([default, customer])
    db.commit()
    return default, customer


def test_workspace_resolver_uses_principal_id_instead_of_default_slug():
    db = _session()
    default, customer = _workspaces(db)

    resolved = workspace_for_principal(db, _principal(customer.id))

    assert resolved.id == customer.id
    assert resolved.id != default.id
    assert resolved.slug == "cliente-b"


def test_project_provisioning_persists_in_non_default_principal_workspace():
    db = _session()
    default, customer = _workspaces(db)
    background_tasks = BackgroundTasks()

    project = provision_project(
        ProjectProvisionCreate(
            name="Projeto Cliente B",
            slug="projeto-cliente-b",
            description="Isolamento por workspace",
            agents_md="",
            codex_config={},
        ),
        background_tasks=background_tasks,
        db=db,
        principal=_principal(customer.id),
        actor="user:customer-b",
    )

    assert project.workspace_id == customer.id
    assert project.workspace_id != default.id
    persisted = db.scalar(select(Project).where(Project.id == project.id))
    assert persisted is not None
    assert persisted.workspace_id == customer.id
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].args[1] == customer.id


def test_provider_model_catalog_never_returns_other_workspace_connection():
    db = _session()
    default, customer = _workspaces(db)
    default_credential = ProviderCredential(
        workspace_id=default.id,
        provider="openai",
        label="Default OpenAI",
        encrypted_secret="unused-default-secret",
        models=json.dumps(["gpt-default-only"]),
        enabled=True,
    )
    customer_credential = ProviderCredential(
        workspace_id=customer.id,
        provider="openai",
        label="Customer OpenAI",
        encrypted_secret="unused-customer-secret",
        models=json.dumps(["gpt-customer-only"]),
        enabled=True,
    )
    db.add_all([default_credential, customer_credential])
    db.commit()

    payload = model_catalog(db=db, principal=_principal(customer.id))

    openai = payload["providers"]["openai"]
    assert openai["connection_id"] == customer_credential.id
    assert openai["connection_id"] != default_credential.id
    assert [item["id"] for item in openai["models"]] == ["gpt-customer-only"]


def test_provider_connection_from_another_workspace_is_hidden():
    db = _session()
    default, customer = _workspaces(db)
    foreign = ProviderCredential(
        workspace_id=default.id,
        provider="custom",
        label="Foreign provider",
        encrypted_secret="foreign-secret-not-read",
        models=json.dumps(["foreign-model"]),
        enabled=True,
    )
    db.add(foreign)
    db.commit()

    with pytest.raises(HTTPException) as error:
        connection_models(
            foreign.id,
            db=db,
            principal=_principal(customer.id),
        )

    assert error.value.status_code == 404
    assert error.value.detail == "Conexão de IA não encontrada"


def test_missing_principal_workspace_fails_closed():
    db = _session()
    _workspaces(db)
    missing = Principal(
        user_id="user-missing",
        workspace_id="workspace-does-not-exist",
        email="missing@example.com",
        role=Role.OWNER,
    )

    with pytest.raises(HTTPException) as error:
        workspace_for_principal(db, missing)

    assert error.value.status_code == 401
