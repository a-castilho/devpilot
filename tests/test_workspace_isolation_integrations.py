import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import ollama_provider_routes as ollama_routes
from app import voice_conversation_routes as voice_conversation
from app import voice_speech_routes as voice_speech
from app.db import Base
from app.models import Project, ProviderCredential, User, Workspace
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


def test_voice_speech_workspace_uses_authenticated_non_default_tenant(monkeypatch):
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

    resolved = voice_speech._workspace(db)
    assert resolved.id == customer.id
    assert resolved.id != default.id

    monkeypatch.setattr(voice_speech, "_decrypt_secret", lambda item: item.label)
    assert voice_speech._openai_api_keys(db, resolved.id) == ["Customer OpenAI"]


def test_voice_conversation_project_context_hides_foreign_project():
    db = _session()
    default, customer = _workspaces(db)
    _authenticate(db, customer)

    foreign = Project(
        workspace_id=default.id,
        name="Projeto Default",
        slug="projeto-default-voice",
        repository_url="https://github.com/example/default.git",
    )
    own = Project(
        workspace_id=customer.id,
        name="Projeto Cliente",
        slug="projeto-cliente-voice",
        repository_url="https://github.com/example/customer.git",
    )
    db.add_all([foreign, own])
    db.commit()

    resolved = voice_conversation._workspace(db)
    assert resolved.id == customer.id

    own_context = voice_conversation._project_context(db, resolved.id, own.id)
    assert "Projeto Cliente" in own_context

    try:
        voice_conversation._project_context(db, resolved.id, foreign.id)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("foreign project must be hidden")


def test_ollama_connection_is_created_only_in_authenticated_workspace(monkeypatch):
    db = _session()
    default, customer = _workspaces(db)
    _authenticate(db, customer)

    monkeypatch.setattr(
        ollama_routes,
        "_ensure_linux_ollama",
        lambda: {"status": "running", "started": True, "models": ["tinyllama"]},
    )
    monkeypatch.setattr(
        ollama_routes.Vault,
        "encrypt",
        lambda self, value: f"enc:{value}",
    )

    created = ollama_routes.connect_ollama(
        ollama_routes.OllamaConnectRequest(label="Local", models=["tinyllama"]),
        db=db,
        actor="user:test",
    )

    assert created["provider"] == "ollama"
    own = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == customer.id,
            ProviderCredential.provider == "ollama",
            ProviderCredential.label == "Local",
        )
    )
    foreign = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == default.id,
            ProviderCredential.provider == "ollama",
            ProviderCredential.label == "Local",
        )
    )
    assert own is not None
    assert json.loads(own.models) == ["tinyllama"]
    assert foreign is None
