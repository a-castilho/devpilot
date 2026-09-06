import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth_routes import login
from app.config import get_settings
from app.db import Base
from app.models import User, Workspace
from app.schemas import LoginRequest
from app.security import decode_access_token, hash_password


@pytest.fixture
def login_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


@pytest.fixture(autouse=True)
def login_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_secret", "test-only-auth-secret-with-at-least-32-chars")
    monkeypatch.setattr(settings, "auth_token_ttl_seconds", 3600)


def add_workspace_user(
    db: Session,
    *,
    workspace_slug: str,
    password: str,
    active: bool = True,
) -> User:
    workspace = Workspace(name=workspace_slug, slug=workspace_slug)
    db.add(workspace)
    db.flush()
    user = User(
        workspace_id=workspace.id,
        email="same@example.test",
        password_hash=hash_password(password),
        role="VIEWER",
        active=active,
    )
    db.add(user)
    db.commit()
    return user


def test_same_email_in_multiple_workspaces_uses_unique_password_match(login_db):
    first = add_workspace_user(
        login_db,
        workspace_slug="tenant-a",
        password="test-only-password-a",
    )
    second = add_workspace_user(
        login_db,
        workspace_slug="tenant-b",
        password="test-only-password-b",
    )

    response = login(
        LoginRequest(email="SAME@example.test", password="test-only-password-b"),
        login_db,
    )
    principal = decode_access_token(response.access_token)

    assert principal.user_id == second.id
    assert principal.workspace_id == second.workspace_id
    assert principal.user_id != first.id


def test_same_email_and_password_in_multiple_workspaces_fails_closed(login_db):
    add_workspace_user(
        login_db,
        workspace_slug="tenant-a",
        password="test-only-shared-password",
    )
    add_workspace_user(
        login_db,
        workspace_slug="tenant-b",
        password="test-only-shared-password",
    )

    with pytest.raises(HTTPException) as error:
        login(
            LoginRequest(email="same@example.test", password="test-only-shared-password"),
            login_db,
        )

    assert error.value.status_code == 401
    assert error.value.detail == "E-mail ou senha inválidos"


def test_inactive_duplicate_does_not_block_unique_active_match(login_db):
    active_user = add_workspace_user(
        login_db,
        workspace_slug="tenant-active",
        password="test-only-shared-password",
        active=True,
    )
    add_workspace_user(
        login_db,
        workspace_slug="tenant-disabled",
        password="test-only-shared-password",
        active=False,
    )

    response = login(
        LoginRequest(email="same@example.test", password="test-only-shared-password"),
        login_db,
    )
    principal = decode_access_token(response.access_token)

    assert principal.user_id == active_user.id
    assert principal.workspace_id == active_user.workspace_id
