from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth_routes import default_workspace, normalized_email
from app.db import get_db
from app.models import User, UserProfile
from app.schemas import UserCreate, UserResponse, UserUpdate
from app.security import (
    Principal,
    Role,
    can_manage_role,
    canonical_role,
    ensure_can_manage_role,
    hash_password,
    require_roles,
)
from app.services.audit import record


router = APIRouter(prefix="/api/users", tags=["users"])
manage_users = require_roles(Role.SUPER_ADMIN, Role.OWNER, Role.ADMIN)

ROLE_INFO = [
    {"value": "SUPER_ADMIN", "label": "Super Admin", "description": "Acesso total à plataforma."},
    {"value": "OWNER", "label": "Proprietário", "description": "Administra o workspace e delega perfis."},
    {"value": "ADMIN", "label": "Administrador", "description": "Administra operação e perfis operacionais."},
    {"value": "ANALYST", "label": "Analista", "description": "Executa análises e tarefas de desenvolvimento."},
    {"value": "VIEWER", "label": "Leitura", "description": "Consulta dados sem executar alterações."},
]


def actor_workspace_id(db: Session, principal: Principal) -> str:
    if principal.workspace_id:
        return principal.workspace_id
    if principal.bootstrap:
        return default_workspace(db).id
    raise HTTPException(status_code=403, detail="Workspace de usuário inválido")


def profile_for(db: Session, user: User) -> UserProfile:
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        db.flush()
    return profile


def clean_name(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def user_view(db: Session, user: User) -> UserResponse:
    profile = profile_for(db, user)
    return UserResponse(
        id=user.id,
        workspace_id=user.workspace_id,
        email=user.email,
        full_name=profile.full_name,
        role=canonical_role(user.role).value,
        active=user.active,
        created_at=user.created_at,
    )


def _is_hidden_super_admin(principal: Principal, user: User) -> bool:
    """SUPER_ADMIN identities are invisible to every non-SUPER_ADMIN principal."""
    return principal.role is not Role.SUPER_ADMIN and canonical_role(user.role) is Role.SUPER_ADMIN


def target_user(db: Session, principal: Principal, user_id: str) -> User:
    workspace_id = actor_workspace_id(db, principal)
    user = db.scalar(select(User).where(User.id == user_id, User.workspace_id == workspace_id))
    if not user or _is_hidden_super_admin(principal, user):
        # Use 404 instead of 403 so lower roles cannot infer that a SUPER_ADMIN account exists.
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user


@router.get("/roles")
def list_roles(principal: Principal = Depends(manage_users)):
    if principal.role is Role.SUPER_ADMIN:
        return ROLE_INFO
    return [item for item in ROLE_INFO if item["value"] != Role.SUPER_ADMIN.value]


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_users),
):
    workspace_id = actor_workspace_id(db, principal)
    users = db.scalars(
        select(User).where(User.workspace_id == workspace_id).order_by(User.created_at, User.email)
    ).all()
    if principal.role is not Role.SUPER_ADMIN:
        users = [user for user in users if not _is_hidden_super_admin(principal, user)]
    result = [user_view(db, user) for user in users]
    db.commit()
    return result


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_users),
):
    workspace_id = actor_workspace_id(db, principal)
    email = normalized_email(payload.email)
    existing = db.scalar(
        select(User).where(User.workspace_id == workspace_id, func.lower(User.email) == email)
    )
    if existing:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")

    role = ensure_can_manage_role(principal.role, canonical_role(payload.role))
    user = User(
        workspace_id=workspace_id,
        email=email,
        password_hash=hash_password(payload.password),
        role=role.value,
        active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.id, full_name=clean_name(payload.full_name)))
    record(
        db,
        workspace_id=workspace_id,
        actor=principal.actor,
        action="user.created",
        details={"user_id": user.id, "role": role.value},
    )
    db.commit()
    db.refresh(user)
    return user_view(db, user)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_users),
):
    target = target_user(db, principal, user_id)
    target_role = canonical_role(target.role)
    is_self = principal.user_id == target.id

    if is_self:
        if payload.active is False:
            raise HTTPException(status_code=400, detail="Você não pode desativar seu próprio usuário")
        if payload.role is not None and canonical_role(payload.role) is not principal.role:
            raise HTTPException(status_code=400, detail="Você não pode remover seu próprio perfil de acesso")
    elif not can_manage_role(principal.role, target_role):
        raise HTTPException(status_code=403, detail="Você não pode administrar este usuário")

    changed: list[str] = []
    if payload.role is not None:
        requested = canonical_role(payload.role)
        if not is_self:
            requested = ensure_can_manage_role(principal.role, requested)
        target.role = requested.value
        changed.append("role")

    if payload.active is not None:
        target.active = payload.active
        changed.append("active")

    if payload.full_name is not None:
        profile_for(db, target).full_name = clean_name(payload.full_name)
        changed.append("full_name")

    record(
        db,
        workspace_id=target.workspace_id,
        actor=principal.actor,
        action="user.updated",
        details={
            "user_id": target.id,
            "fields": changed,
            "role": canonical_role(target.role).value,
            "active": target.active,
        },
    )
    db.commit()
    db.refresh(target)
    return user_view(db, target)
