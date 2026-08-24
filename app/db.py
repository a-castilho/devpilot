from collections.abc import Generator

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker, with_loader_criteria

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


_SCOPE_ROLE_USER_KEY = "_account_scope_role_user_id"
_SCOPE_ROLE_KEY = "_account_scope_role"
_SCOPE_DISABLED_OPTION = "devpilot_account_scope_disabled"


def _principal_user_id(session: Session) -> str | None:
    value = session.info.get("principal_user_id")
    return str(value) if value else None


def _principal_is_super_admin(session: Session) -> bool:
    """Resolve the current persisted role without issuing an ORM query.

    ``session_principal`` stores only the authenticated user id in ``Session.info``.
    Reading the role through the connection avoids recursively triggering the ORM
    account-scope event while still honoring role changes immediately.
    """
    user_id = _principal_user_id(session)
    if not user_id:
        return False

    if session.info.get(_SCOPE_ROLE_USER_KEY) == user_id:
        role = session.info.get(_SCOPE_ROLE_KEY)
    else:
        role = session.connection().execute(
            text("SELECT role FROM users WHERE id = :user_id"),
            {"user_id": user_id},
        ).scalar_one_or_none()
        session.info[_SCOPE_ROLE_USER_KEY] = user_id
        session.info[_SCOPE_ROLE_KEY] = str(role or "")

    # ``admin`` is the historic DevPilot value migrated to SUPER_ADMIN at startup.
    return str(role or "") in {"SUPER_ADMIN", "admin"}


@event.listens_for(Session, "do_orm_execute")
def _scope_account_reads(execute_state) -> None:
    """Apply row-level ownership to all authenticated Project/Task ORM reads.

    Internal workers do not carry ``principal_user_id`` and therefore remain able to
    process the global queue. SUPER_ADMIN is intentionally unscoped and sees all rows.
    """
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get(_SCOPE_DISABLED_OPTION):
        return

    session = execute_state.session
    user_id = _principal_user_id(session)
    if not user_id or _principal_is_super_admin(session):
        return

    # Imported lazily to avoid a db.py <-> models.py import cycle.
    from app.models import Project, Task

    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            Project,
            lambda model: model.owner_user_id == user_id,
            include_aliases=True,
        ),
        with_loader_criteria(
            Task,
            lambda model: model.owner_user_id == user_id,
            include_aliases=True,
        ),
    )


@event.listens_for(Session, "before_flush")
def _bind_account_ownership(session: Session, _flush_context, _instances) -> None:
    """Attach new projects/tasks to the authenticated account automatically.

    A background/system-created task inherits ownership from its project so worker
    processing does not accidentally create an unowned task that disappears for the
    project owner.
    """
    from app.models import Project, Task

    principal_user_id = _principal_user_id(session)

    for item in session.new:
        if isinstance(item, Project) and not item.owner_user_id and principal_user_id:
            item.owner_user_id = principal_user_id

    for item in session.new:
        if not isinstance(item, Task) or item.owner_user_id:
            continue
        if principal_user_id:
            item.owner_user_id = principal_user_id
            continue
        if item.project_id:
            item.owner_user_id = session.connection().execute(
                select(Project.owner_user_id).where(Project.id == item.project_id)
            ).scalar_one_or_none()


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
