from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserProfile, Workspace
from app.schemas import (
    AccessTokenResponse,
    AuthStatusResponse,
    BootstrapUserRequest,
    CurrentUserResponse,
    LoginRequest,
    ProfileUpdate,
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


def _profile_for(db: Session, user: User) -> UserProfile:
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        db.flush()
    return profile


def _public_user(user: User, profile: UserProfile) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        workspace_id=user.workspace_id,
        email=user.email,
        role=user.role,
        active=user.active,
        full_name=profile.full_name,
        phone=profile.phone,
        job_title=profile.job_title,
        bio=profile.bio,
        avatar_url=profile.avatar_url,
        locale=profile.locale,
        timezone=profile.timezone,
    )


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
    db.add(UserProfile(user_id=user.id))
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
def me(
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    if principal.bootstrap:
        return CurrentUserResponse(
            role=Role.ADMIN.value,
            bootstrap=True,
            full_name="Administrador bootstrap",
        )
    user = db.get(User, principal.user_id)
    if user is None or not user.active:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    profile = _profile_for(db, user)
    db.commit()
    return _public_user(user, profile)


@router.patch("/me", response_model=CurrentUserResponse)
def update_me(
    payload: ProfileUpdate,
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    if principal.bootstrap:
        raise HTTPException(status_code=409, detail="Perfil bootstrap não é persistente")
    user = db.get(User, principal.user_id)
    if user is None or not user.active:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    profile = _profile_for(db, user)
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(profile, key, value)
    if not profile.locale:
        profile.locale = "pt-BR"
    if not profile.timezone:
        profile.timezone = "America/Sao_Paulo"
    db.commit()
    return _public_user(user, profile)
