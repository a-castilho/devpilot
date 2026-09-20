from ipaddress import ip_address

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
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
    canonical_role,
    create_access_token,
    hash_password,
    require_bootstrap_access,
    session_principal,
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
        role=canonical_role(user.role).value,
        active=user.active,
        full_name=profile.full_name,
        phone=profile.phone,
        job_title=profile.job_title,
        bio=profile.bio,
        avatar_url=profile.avatar_url,
        locale=profile.locale,
        timezone=profile.timezone,
    )


def _is_loopback_request(request: Request) -> bool:
    if request.client is None or not request.client.host:
        return False
    host = request.client.host.split("%", 1)[0]
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return host.lower() == "localhost"


def _local_bootstrap_available(request: Request) -> bool:
    """Allow tokenless first-admin setup only on the local development machine.

    This never applies in production and never applies to LAN/remote clients. The first-user
    check in ``bootstrap_user`` still guarantees the flow can create only one initial admin.
    """
    env = get_settings().env.strip().lower()
    return env not in {"production", "prod"} and _is_loopback_request(request)


def _authenticated_user(db: Session, email: str, password: str) -> User | None:
    """Resolve password login without ever choosing a tenant arbitrarily.

    E-mail uniqueness is scoped to ``(workspace_id, email)``, so the same normalized e-mail
    can legitimately exist in more than one workspace. A password-only login is safe only
    when the supplied credential identifies exactly one active account. If zero or multiple
    active accounts match, fail closed and let the public login endpoint return its generic
    authentication error.
    """
    candidates = list(
        db.scalars(select(User).where(func.lower(User.email) == email)).all()
    )
    if not candidates:
        # Preserve a real password verification on unknown e-mails to avoid a trivial
        # timing distinction from the single-account failure path.
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None

    matches: list[User] = []
    for candidate in candidates:
        password_hash = candidate.password_hash or _DUMMY_PASSWORD_HASH
        password_valid = verify_password(password, password_hash)
        if candidate.active and candidate.password_hash and password_valid:
            matches.append(candidate)

    if len(matches) != 1:
        return None
    return matches[0]


@router.get("/status", response_model=AuthStatusResponse)
def status(request: Request, db: Session = Depends(get_db)):
    users = db.scalar(select(func.count(User.id))) or 0
    bootstrap_required = users == 0
    return AuthStatusResponse(
        bootstrap_required=bootstrap_required,
        local_bootstrap_available=bootstrap_required and _local_bootstrap_available(request),
    )


@router.post("/bootstrap", response_model=AccessTokenResponse, status_code=201)
def bootstrap_user(
    payload: BootstrapUserRequest,
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    existing = db.scalar(select(func.count(User.id))) or 0
    if existing:
        raise HTTPException(status_code=409, detail="Primeiro usuário já configurado")

    # Local development is intentionally frictionless for the machine owner. Remote/LAN
    # setup still requires the one-time bootstrap credential so another device cannot claim
    # SUPER_ADMIN just because the database is empty.
    if not _local_bootstrap_available(request):
        require_bootstrap_access(authorization)

    ws = default_workspace(db)
    user = User(
        workspace_id=ws.id,
        email=normalized_email(payload.email),
        password_hash=hash_password(payload.password),
        role=Role.SUPER_ADMIN.value,
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
    user = _authenticated_user(db, email, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

    token, ttl = create_access_token(user)
    return AccessTokenResponse(access_token=token, expires_in=ttl)


@router.get("/me", response_model=CurrentUserResponse)
def me(
    principal: Principal = Depends(session_principal),
    db: Session = Depends(get_db),
):
    if principal.bootstrap:
        return CurrentUserResponse(
            role=Role.SUPER_ADMIN.value,
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
    principal: Principal = Depends(session_principal),
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
