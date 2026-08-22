import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import User, UserProfile, Workspace
from app.security import Principal, Role, hash_password
from app.user_routes import list_roles, list_users, manage_users, target_user


@pytest.fixture
def users_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(name="DevPilot", slug="default")
        db.add(workspace)
        db.flush()
        yield db, workspace
    engine.dispose()


def add_user(db: Session, workspace: Workspace, *, email: str, role: str) -> User:
    user = User(
        workspace_id=workspace.id,
        email=email,
        password_hash=hash_password("correct horse battery staple"),
        role=role,
        active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.id, full_name=email.split("@", 1)[0]))
    db.commit()
    return user


def principal_for(user: User, role: Role) -> Principal:
    return Principal(
        user_id=user.id,
        workspace_id=user.workspace_id,
        email=user.email,
        role=role,
    )


def test_admin_never_receives_super_admin_users(users_db):
    db, workspace = users_db
    super_admin = add_user(db, workspace, email="root@example.com", role="SUPER_ADMIN")
    legacy_super_admin = add_user(db, workspace, email="legacy@example.com", role="admin")
    admin = add_user(db, workspace, email="admin@example.com", role="ADMIN")
    analyst = add_user(db, workspace, email="analyst@example.com", role="ANALYST")

    visible = list_users(db=db, principal=principal_for(admin, Role.ADMIN))
    visible_ids = {item.id for item in visible}

    assert admin.id in visible_ids
    assert analyst.id in visible_ids
    assert super_admin.id not in visible_ids
    assert legacy_super_admin.id not in visible_ids


def test_owner_role_catalog_does_not_disclose_super_admin(users_db):
    db, workspace = users_db
    owner = add_user(db, workspace, email="owner@example.com", role="OWNER")

    roles = list_roles(principal_for(owner, Role.OWNER))

    assert {item["value"] for item in roles} == {"OWNER", "ADMIN", "ANALYST", "VIEWER"}
    assert all("Super Admin" not in item["label"] for item in roles)


def test_lower_manager_cannot_probe_super_admin_by_id(users_db):
    db, workspace = users_db
    super_admin = add_user(db, workspace, email="root@example.com", role="SUPER_ADMIN")
    admin = add_user(db, workspace, email="admin@example.com", role="ADMIN")

    with pytest.raises(HTTPException) as error:
        target_user(db, principal_for(admin, Role.ADMIN), super_admin.id)

    assert error.value.status_code == 404
    assert error.value.detail == "Usuário não encontrado"


def test_super_admin_still_sees_all_workspace_users(users_db):
    db, workspace = users_db
    super_admin = add_user(db, workspace, email="root@example.com", role="SUPER_ADMIN")
    admin = add_user(db, workspace, email="admin@example.com", role="ADMIN")
    analyst = add_user(db, workspace, email="analyst@example.com", role="ANALYST")

    visible = list_users(db=db, principal=principal_for(super_admin, Role.SUPER_ADMIN))

    assert {item.id for item in visible} == {super_admin.id, admin.id, analyst.id}
    assert "SUPER_ADMIN" in {item["value"] for item in list_roles(principal_for(super_admin, Role.SUPER_ADMIN))}


def test_analyst_cannot_open_user_administration(users_db):
    db, workspace = users_db
    analyst = add_user(db, workspace, email="analyst@example.com", role="ANALYST")

    with pytest.raises(HTTPException) as error:
        manage_users(principal_for(analyst, Role.ANALYST))

    assert error.value.status_code == 403
