from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, Workspace
from app.schemas import (
    AccessTokenResponse,
    AuthStatusResponse,
    BootstrapUserRequest,
    CurrentUserResponse,
    LoginRequest,
)
from app.security import (
    _DUMMY_PASSWORD_HASH,
    Principal,
    Role,
    create_access_token,
    current_principal,
    hash_password,
    require_bootstrap_access,
    verify_password,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])


def default_workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        item = Workspace(name="DevPilot", slug="default")
        db.add(item)
        db.flush()
    return item


def normalized_email(value: str) -> str:
    return value.strip().lower()


@router.get("/status", response_model=AuthStatusResponse)
def status(db: Session = Depends(get_db)):
    users = db.scalar(select(func.count(User.id))) or 0
    return AuthStatusResponse(bootstrap_required=users == 0)


@router.post("/bootstrap", response_model=AccessTokenResponse, status_code=201)
def bootstrap_user(
    payload: BootstrapUserRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_bootstrap_access),
):
    existing = db.scalar(select(func.count(User.id))) or 0
    if existing:
        raise HTTPException(status_code=409, detail="Primeiro usuário já configurado")

    ws = default_workspace(db)
    user = User(
        workspace_id=ws.id,
        email=normalized_email(payload.email),
        password_hash=hash_password(payload.password),
        role=Role.ADMIN.value,
        active=True,
    )
    db.add(user)
    db.flush()
    token, ttl = create_access_token(user)
    db.commit()
    return AccessTokenResponse(access_token=token, expires_in=ttl)


@router.post("/login", response_model=AccessTokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = normalized_email(payload.email)
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    password_hash = user.password_hash if user and user.password_hash else _DUMMY_PASSWORD_HASH
    password_valid = verify_password(payload.password, password_hash)
    if user is None or not user.active or not user.password_hash or not password_valid:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

    token, ttl = create_access_token(user)
    return AccessTokenResponse(access_token=token, expires_in=ttl)


@router.get("/me", response_model=CurrentUserResponse)
def me(principal: Principal = Depends(current_principal)):
    return CurrentUserResponse(
        id=principal.user_id,
        workspace_id=principal.workspace_id,
        email=principal.email,
        role=principal.role.value,
        bootstrap=principal.bootstrap,
    )
