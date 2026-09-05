from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import voice_transcription_routes as transcription
from app.db import Base
from app.models import ProviderCredential, User, Workspace
from app.security import Role


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _workspaces(db: Session) -> tuple[Workspace, Workspace]:
    default = Workspace(name="DevPilot", slug="default")
    customer = Workspace(name="Cliente B", slug="cliente-b")
    db.add_all([default, customer])
    db.commit()
    return default, customer


def _authenticate(db: Session, workspace: Workspace) -> User:
    user = User(
        workspace_id=workspace.id,
        email=f"owner-{workspace.slug}@example.com",
        password_hash="not-used",
        role=Role.OWNER.value,
        active=True,
    )
    db.add(user)
    db.commit()
    db.info["principal_user_id"] = user.id
    return user


def test_transcription_uses_authenticated_workspace_for_persisted_credentials(monkeypatch):
    db = _session()
    default, customer = _workspaces(db)
    _authenticate(db, customer)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    foreign = ProviderCredential(
        workspace_id=default.id,
        provider="openai",
        label="Foreign OpenAI",
        encrypted_secret="foreign-secret",
        models="[]",
        enabled=True,
    )
    own = ProviderCredential(
        workspace_id=customer.id,
        provider="openai",
        label="Customer OpenAI",
        encrypted_secret="customer-secret",
        models="[]",
        enabled=True,
    )
    db.add_all([foreign, own])
    db.commit()

    workspace = transcription._workspace(db)
    assert workspace.id == customer.id
    assert workspace.id != default.id

    monkeypatch.setattr(transcription, "_decrypt_secret", lambda item: item.label)
    assert transcription._openai_api_keys(db, workspace.id) == ["Customer OpenAI"]


def test_transcription_custom_groq_candidates_never_use_foreign_workspace(monkeypatch):
    db = _session()
    default, customer = _workspaces(db)
    _authenticate(db, customer)

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    foreign = ProviderCredential(
        workspace_id=default.id,
        provider="custom",
        label="Foreign Groq",
        encrypted_secret="foreign-secret",
        models='["whisper-large-v3"]',
        enabled=True,
    )
    own = ProviderCredential(
        workspace_id=customer.id,
        provider="custom",
        label="Customer Groq",
        encrypted_secret="customer-secret",
        models='["whisper-large-v3"]',
        enabled=True,
    )
    db.add_all([foreign, own])
    db.commit()

    monkeypatch.setattr(transcription, "_decrypt_secret", lambda item: item.label)
    candidates = transcription._groq_candidates(db, customer.id)

    assert [candidate[0] for candidate in candidates] == ["Customer Groq"]
    assert all(candidate[0] != "Foreign Groq" for candidate in candidates)
