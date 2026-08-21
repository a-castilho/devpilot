import pytest
from fastapi import HTTPException
from starlette.requests import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import User, UserProfile, Workspace
from app.schemas import UserCreate, UserUpdate
from app.security import (
    Principal,
    Role,
    can_manage_role,
    hash_password,
    require_access,
    require_roles,
)
from app.user_routes import create_user, list_users, update_user


@pytest.fixture
def profile_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        ws = Workspace(name="DevPilot", slug="default")
        db.add(ws); db.flush()
        root = User(workspace_id=ws.id, email="root@example.com", password_hash=hash_password("root password 123"), role="SUPER_ADMIN", active=True)
        db.add(root); db.flush(); db.add(UserProfile(user_id=root.id, full_name="Root")); db.commit()
        yield db, ws, root
    engine.dispose()


def principal(user, role=None):
    return Principal(user.id, user.workspace_id, user.email, role or Role(user.role))


def test_super_admin_creates_owner_and_users_are_scoped(profile_db):
    db, ws, root = profile_db
    owner = create_user(
        UserCreate(email="OWNER@example.com", full_name="Workspace Owner", password="owner password 123", role="OWNER"),
        db,
        principal(root),
    )
    assert owner.email == "owner@example.com"
    assert owner.role == "OWNER"
    assert owner.full_name == "Workspace Owner"
    assert {row.email for row in list_users(db, principal(root))} == {"root@example.com", "owner@example.com"}


def test_owner_can_manage_operational_roles_but_not_super_admin(profile_db):
    db, ws, root = profile_db
    owner = User(workspace_id=ws.id, email="owner@example.com", password_hash=hash_password("owner password 123"), role="OWNER", active=True)
    db.add(owner); db.flush(); db.add(UserProfile(user_id=owner.id)); db.commit()
    assert create_user(UserCreate(email="analyst@example.com", password="analyst password 123", role="ANALYST"), db, principal(owner)).role == "ANALYST"
    with pytest.raises(HTTPException) as error:
        create_user(UserCreate(email="super@example.com", password="superadmin password", role="SUPER_ADMIN"), db, principal(owner))
    assert error.value.status_code == 403


def test_admin_cannot_manage_owner_and_self_cannot_be_deactivated(profile_db):
    db, ws, root = profile_db
    owner = User(workspace_id=ws.id, email="owner@example.com", password_hash=hash_password("owner password 123"), role="OWNER", active=True)
    admin = User(workspace_id=ws.id, email="admin@example.com", password_hash=hash_password("admin password 123"), role="ADMIN", active=True)
    db.add_all([owner, admin]); db.flush(); db.add_all([UserProfile(user_id=owner.id), UserProfile(user_id=admin.id)]); db.commit()
    with pytest.raises(HTTPException) as error:
        update_user(owner.id, UserUpdate(active=False), db, principal(admin))
    assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        update_user(admin.id, UserUpdate(active=False), db, principal(admin))
    assert error.value.status_code == 400


def request(method, path):
    return Request({"type":"http","method":method,"path":path,"raw_path":path.encode(),"query_string":b"","headers":[],"scheme":"http","server":("test",80),"client":("test",123)})


def test_viewer_is_read_only_and_analyst_cannot_administer_configuration():
    viewer = Principal("v", "w", "v@example.com", Role.VIEWER)
    analyst = Principal("a", "w", "a@example.com", Role.ANALYST)
    assert require_access(request("GET", "/api/projects"), viewer) == "user:v"
    with pytest.raises(HTTPException):
        require_access(request("POST", "/api/tasks"), viewer)
    assert require_access(request("POST", "/api/tasks"), analyst) == "user:a"
    with pytest.raises(HTTPException):
        require_access(request("POST", "/api/providers"), analyst)


def test_role_management_matrix_matches_regulaai():
    expected = {
        Role.SUPER_ADMIN: set(Role),
        Role.OWNER: {Role.ADMIN, Role.ANALYST, Role.VIEWER},
        Role.ADMIN: {Role.ANALYST, Role.VIEWER},
        Role.ANALYST: set(),
        Role.VIEWER: set(),
    }
    for actor, allowed in expected.items():
        assert {target for target in Role if can_manage_role(actor, target)} == allowed


def test_require_roles_keeps_super_admin_bypass_and_denies_viewer():
    dependency = require_roles(Role.OWNER, Role.ADMIN)
    super_admin = Principal("root", "w", "root@example.com", Role.SUPER_ADMIN)
    viewer = Principal("viewer", "w", "viewer@example.com", Role.VIEWER)

    assert dependency(principal=super_admin) is super_admin
    with pytest.raises(HTTPException) as error:
        dependency(principal=viewer)
    assert error.value.status_code == 403
