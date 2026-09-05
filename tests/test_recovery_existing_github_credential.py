from __future__ import annotations

import subprocess

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Organization, Project, ProviderCredential, Workspace
from app.services import recovery as recovery_module
from app.services.recovery import AutoRecoveryService


@pytest.fixture
def recovery_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'recovery.db'}")
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(recovery_module, "SessionLocal", TestSession)
    try:
        yield TestSession
    finally:
        engine.dispose()


def _workspace(db, slug: str) -> Workspace:
    item = Workspace(name=slug, slug=slug)
    db.add(item)
    db.flush()
    return item


def _credential(db, workspace_id: str, label: str, cipher: str) -> ProviderCredential:
    item = ProviderCredential(
        workspace_id=workspace_id,
        provider="github",
        label=label,
        encrypted_secret=cipher,
        enabled=True,
    )
    db.add(item)
    db.flush()
    return item


def _organization(
    db,
    workspace_id: str,
    login: str,
    *,
    credential_id: str | None = None,
) -> Organization:
    item = Organization(
        workspace_id=workspace_id,
        provider="github",
        name=login,
        slug=login.lower(),
        external_login=login,
        credential_id=credential_id,
    )
    db.add(item)
    db.flush()
    return item


def _project(
    db,
    workspace_id: str,
    *,
    organization_id: str | None = None,
    repository_url: str = "https://github.com/a-castilho/devpilot.git",
) -> Project:
    item = Project(
        workspace_id=workspace_id,
        organization_id=organization_id,
        name="DevPilot",
        slug="devpilot",
        repository_url=repository_url,
    )
    db.add(item)
    db.flush()
    return item


def test_registered_same_workspace_credential_repairs_missing_project_org_link(
    recovery_db,
    monkeypatch,
):
    TestSession = recovery_db
    with TestSession() as db:
        workspace = _workspace(db, "workspace-a")
        other_workspace = _workspace(db, "workspace-b")
        credential = _credential(db, workspace.id, "github-main", "cipher-main")
        _credential(db, other_workspace.id, "github-cross", "cipher-cross")
        organization = _organization(db, workspace.id, "a-castilho")
        _organization(db, other_workspace.id, "a-castilho")
        project = _project(db, workspace.id)
        db.commit()

    decrypted: list[str] = []
    checked_tokens: list[str] = []

    def decrypt(_vault, value: str) -> str:
        decrypted.append(value)
        return {"cipher-main": "token-main", "cipher-cross": "token-cross"}[value]

    def ls_remote(_repository_url: str, token: str):
        checked_tokens.append(token)
        return subprocess.CompletedProcess(["git", "ls-remote"], 0, "ok", "")

    monkeypatch.setattr(recovery_module.Vault, "decrypt", decrypt)
    service = AutoRecoveryService()
    monkeypatch.setattr(service, "_git_ls_remote", ls_remote)

    decision = service._recover_github_access(project, execution_attempt=1)

    assert decision.status == "resolved"
    assert decision.retry is True
    assert decision.requires_authorization is False
    assert decision.strategy == "github_project_link_repair"
    assert decrypted == ["cipher-main"]
    assert checked_tokens == ["token-main"]
    assert project.organization_id == organization.id

    with TestSession() as db:
        stored_project = db.get(Project, project.id)
        stored_organization = db.get(Organization, organization.id)
        assert stored_project.organization_id == organization.id
        assert stored_organization.credential_id == credential.id


def test_missing_project_org_never_uses_matching_org_from_other_workspace(
    recovery_db,
    monkeypatch,
):
    TestSession = recovery_db
    with TestSession() as db:
        workspace = _workspace(db, "workspace-a")
        other_workspace = _workspace(db, "workspace-b")
        cross_credential = _credential(db, other_workspace.id, "github-cross", "cipher-cross")
        _organization(db, other_workspace.id, "a-castilho", credential_id=cross_credential.id)
        project = _project(db, workspace.id)
        db.commit()

    monkeypatch.setattr(
        recovery_module.Vault,
        "decrypt",
        lambda *_args: pytest.fail("cross-workspace credential must not be decrypted"),
    )
    service = AutoRecoveryService()
    monkeypatch.setattr(
        service,
        "_git_ls_remote",
        lambda *_args: pytest.fail("cross-workspace credential must not reach Git"),
    )

    decision = service._recover_github_access(project, execution_attempt=1)

    assert decision.status == "needs_authorization"
    assert decision.retry is False
    assert decision.requires_authorization is True
    assert decision.strategy == "request_github_authorization"
    assert project.organization_id is None


def test_explicit_project_org_must_match_repository_owner_before_sending_token(
    recovery_db,
    monkeypatch,
):
    TestSession = recovery_db
    with TestSession() as db:
        workspace = _workspace(db, "workspace-a")
        credential = _credential(db, workspace.id, "github-main", "cipher-main")
        wrong_organization = _organization(
            db,
            workspace.id,
            "different-owner",
            credential_id=credential.id,
        )
        project = _project(db, workspace.id, organization_id=wrong_organization.id)
        db.commit()

    monkeypatch.setattr(
        recovery_module.Vault,
        "decrypt",
        lambda *_args: pytest.fail("mismatched owner credential must not be decrypted"),
    )
    service = AutoRecoveryService()
    monkeypatch.setattr(
        service,
        "_git_ls_remote",
        lambda *_args: pytest.fail("mismatched owner credential must not reach Git"),
    )

    decision = service._recover_github_access(project, execution_attempt=1)

    assert decision.status == "needs_attention"
    assert decision.retry is False
    assert decision.requires_authorization is False
    assert decision.strategy == "github_owner_boundary_stop"
