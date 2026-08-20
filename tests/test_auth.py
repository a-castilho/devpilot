import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth_routes import bootstrap_user, login
from app.config import get_settings
from app.db import Base
from app.models import User, UserProfile, Workspace
from app.schemas import BootstrapUserRequest, LoginRequest
from app.security import (
    Role,
    create_access_token,
    current_principal,
    decode_access_token,
    hash_password,
    require_bootstrap_access,
    require_super_admin,
    session_principal,
    verify_password,
)


@pytest.fixture
def auth_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


@pytest.fixture(autouse=True)
def auth_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_secret", "test-auth-secret-with-at-least-32-characters")
    monkeypatch.setattr(settings, "auth_token_ttl_seconds", 3600)
    monkeypatch.setattr(settings, "bootstrap_token", "test-bootstrap-token-with-at-least-32-characters")


def add_user(db: Session, *, active=True, password="correct horse battery staple", role="user"):
    ws = Workspace(name="DevPilot", slug="default")
    db.add(ws); db.flush()
    user = User(workspace_id=ws.id, email="User@Example.com", password_hash=hash_password(password), role=role, active=active)
    db.add(user); db.flush(); db.add(UserProfile(user_id=user.id, full_name="Test User")); db.commit()
    return user


def test_password_is_stored_as_argon2id_hash():
    encoded = hash_password("correct horse battery staple")
    assert encoded.startswith("$argon2id$")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_login_normalizes_email_and_maps_legacy_user_to_viewer(auth_db):
    user = add_user(auth_db)
    response = login(LoginRequest(email="  USER@example.com ", password="correct horse battery staple"), auth_db)
    principal = decode_access_token(response.access_token)
    assert response.expires_in == 3600
    assert principal.user_id == user.id
    assert principal.role is Role.VIEWER


@pytest.mark.parametrize("email,password,active", [
    ("user@example.com", "wrong password", True),
    ("missing@example.com", "wrong password", True),
    ("user@example.com", "correct horse battery staple", False),
])
def test_login_rejects_invalid_credentials_with_generic_error(auth_db, email, password, active):
    add_user(auth_db, active=active)
    with pytest.raises(HTTPException) as error:
        login(LoginRequest(email=email, password=password), auth_db)
    assert error.value.status_code == 401
    assert error.value.detail == "E-mail ou senha inválidos"


def test_bootstrap_creates_only_first_super_admin(auth_db):
    response = bootstrap_user(BootstrapUserRequest(email="Admin@Example.com", password="a secure first password"), auth_db, "owner")
    assert decode_access_token(response.access_token).role is Role.SUPER_ADMIN
    assert auth_db.query(UserProfile).count() == 1
    with pytest.raises(HTTPException) as error:
        bootstrap_user(BootstrapUserRequest(email="second@example.com", password="another secure password"), auth_db, "owner")
    assert error.value.status_code == 409


def test_bootstrap_token_and_legacy_admin_remain_super_admin(auth_db):
    assert require_bootstrap_access(authorization="Bearer test-bootstrap-token-with-at-least-32-characters") == "owner"
    bootstrap = current_principal(authorization="Bearer test-bootstrap-token-with-at-least-32-characters")
    assert bootstrap.role is Role.SUPER_ADMIN
    assert require_super_admin(bootstrap) == "owner"
    admin = add_user(auth_db, role="admin")
    token, _ = create_access_token(admin)
    assert current_principal(authorization=f"Bearer {token}").role is Role.SUPER_ADMIN


def test_session_principal_uses_current_database_role_and_active_state(auth_db):
    user = add_user(auth_db, role="ANALYST")
    token, _ = create_access_token(user)
    raw = current_principal(authorization=f"Bearer {token}")
    user.role = "VIEWER"; auth_db.commit()
    assert session_principal(raw, auth_db).role is Role.VIEWER
    user.active = False; auth_db.commit()
    with pytest.raises(HTTPException) as error:
        session_principal(raw, auth_db)
    assert error.value.status_code == 401


def test_malformed_token_is_rejected():
    with pytest.raises(HTTPException) as error:
        decode_access_token("not.a.valid-token")
    assert error.value.status_code == 401
