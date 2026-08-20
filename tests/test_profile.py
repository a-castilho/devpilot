import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth_routes import me, update_me
from app.db import Base
from app.models import User, UserProfile, Workspace
from app.schemas import ProfileUpdate
from app.security import Principal, Role, hash_password


@pytest.fixture
def profile_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def add_user(db: Session):
    ws = Workspace(name="DevPilot", slug="default")
    db.add(ws); db.flush()
    user = User(workspace_id=ws.id, email="user@example.com", password_hash=hash_password("correct horse battery staple"), role="VIEWER", active=True)
    db.add(user); db.flush(); db.add(UserProfile(user_id=user.id)); db.commit()
    return user


def principal(user: User) -> Principal:
    return Principal(user_id=user.id, workspace_id=user.workspace_id, email=user.email, role=Role.VIEWER)


def test_profile_reads_and_updates_regulaai_fields(profile_db):
    user = add_user(profile_db)
    result = update_me(
        ProfileUpdate(
            full_name="André Castilho",
            phone="+55 35 99999-9999",
            job_title="Analista de Sistemas",
            bio="Perfil DevPilot",
            avatar_url="https://example.com/avatar.png",
            locale="pt-BR",
            timezone="America/Sao_Paulo",
        ),
        principal(user),
        profile_db,
    )
    assert result.email == "user@example.com"
    assert result.role == "VIEWER"
    assert result.full_name == "André Castilho"
    assert me(principal(user), profile_db).timezone == "America/Sao_Paulo"


def test_profile_cannot_self_assign_role_or_active_state():
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({"full_name": "User", "role": "SUPER_ADMIN"})
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({"full_name": "User", "active": False})


def test_bootstrap_profile_is_read_only(profile_db):
    bootstrap = Principal(user_id=None, workspace_id=None, email=None, role=Role.SUPER_ADMIN, bootstrap=True)
    result = me(bootstrap, profile_db)
    assert result.bootstrap is True
    assert result.role == "SUPER_ADMIN"
    with pytest.raises(HTTPException) as error:
        update_me(ProfileUpdate(full_name="Owner"), bootstrap, profile_db)
    assert error.value.status_code == 409
