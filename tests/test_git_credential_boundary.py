from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Organization, ProviderCredential, Workspace
from app.services import executor, recovery


class FakeVault:
    def decrypt(self, value: str) -> str:
        return value


@pytest.fixture
def credential_store(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'git-boundary.db'}")
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(executor, "SessionLocal", SessionFactory)
    monkeypatch.setattr(recovery, "SessionLocal", SessionFactory)
    monkeypatch.setattr(executor, "Vault", FakeVault)
    monkeypatch.setattr(recovery, "Vault", FakeVault)

    with SessionFactory() as db:
        first = Workspace(name="First", slug="first")
        second = Workspace(name="Second", slug="second")
        db.add_all([first, second])
        db.flush()

        first_credential = ProviderCredential(
            workspace_id=first.id,
            provider="github",
            label="first-github",
            encrypted_secret="first-secret-token",
            enabled=True,
        )
        second_credential = ProviderCredential(
            workspace_id=second.id,
            provider="github",
            label="second-github",
            encrypted_secret="second-secret-token",
            enabled=True,
        )
        db.add_all([first_credential, second_credential])
        db.flush()

        first_org = Organization(
            workspace_id=first.id,
            provider="github",
            name="First org",
            slug="first-org",
            external_login="first-org",
            credential_id=first_credential.id,
        )
        second_org = Organization(
            workspace_id=second.id,
            provider="github",
            name="Second org",
            slug="second-org",
            external_login="second-org",
            credential_id=second_credential.id,
        )
        db.add_all([first_org, second_org])
        db.commit()

        values = {
            "first_workspace_id": first.id,
            "second_workspace_id": second.id,
            "first_org_id": first_org.id,
            "second_org_id": second_org.id,
        }

    try:
        yield SessionFactory, values
    finally:
        engine.dispose()


def project(*, workspace_id: str, organization_id: str | None, repository_url: str = "https://github.com/example/repo.git"):
    return SimpleNamespace(
        workspace_id=workspace_id,
        organization_id=organization_id,
        repository_url=repository_url,
        slug="repo",
    )


def test_executor_does_not_resolve_organization_from_another_workspace(credential_store):
    _SessionFactory, values = credential_store
    item = project(
        workspace_id=values["first_workspace_id"],
        organization_id=values["second_org_id"],
    )

    environment = executor.git_environment(item, item.repository_url)

    assert environment == {"GIT_TERMINAL_PROMPT": "0"}
    assert "GIT_CONFIG_VALUE_0" not in environment


def test_executor_scopes_github_pat_to_github_url(credential_store):
    _SessionFactory, values = credential_store
    item = project(
        workspace_id=values["first_workspace_id"],
        organization_id=values["first_org_id"],
    )

    environment = executor.git_environment(item, item.repository_url)

    assert environment["GIT_CONFIG_COUNT"] == "1"
    assert environment["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraHeader"
    assert environment["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic ")
    assert "first-secret-token" not in environment["GIT_CONFIG_VALUE_0"]


def test_executor_never_attaches_github_pat_to_another_allowed_git_host(credential_store):
    _SessionFactory, values = credential_store
    item = project(
        workspace_id=values["first_workspace_id"],
        organization_id=values["first_org_id"],
        repository_url="https://git.example.internal/example/repo.git",
    )

    environment = executor.git_environment(item, item.repository_url)

    assert environment == {"GIT_TERMINAL_PROMPT": "0"}


def test_existing_checkout_origin_is_reset_before_authenticated_fetch(tmp_path, monkeypatch):
    checkout = tmp_path / "repo"
    checkout.mkdir()
    item = project(workspace_id="workspace-1", organization_id=None)
    calls: list[tuple[list[str], object, object]] = []
    safe_url = "https://github.com/example/repo.git"
    auth_environment = {"GIT_TERMINAL_PROMPT": "0", "AUTH_MARKER": "scoped"}

    monkeypatch.setattr(executor, "validated_repository_url", lambda _project: safe_url)
    monkeypatch.setattr(executor, "repository_path", lambda _project: checkout)
    monkeypatch.setattr(executor, "git_environment", lambda _project, _url=None: auth_environment)

    def fake_run(args, cwd=None, timeout=900, env_overrides=None):
        calls.append((list(args), cwd, env_overrides))
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(executor, "run", fake_run)

    assert executor.ensure_repository(item) == checkout
    assert calls[0] == (["git", "remote", "set-url", "origin", safe_url], checkout, None)
    assert calls[1] == (["git", "fetch", "--prune", "origin"], checkout, auth_environment)


def test_recovery_ls_remote_scopes_header_and_uses_normalized_url(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = list(args)
        captured["env"] = dict(kwargs["env"])
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(recovery.subprocess, "run", fake_run)
    service = recovery.AutoRecoveryService()

    result = service._git_ls_remote("github.com/example/repo", "secret-token")

    assert result.returncode == 0
    assert captured["args"] == ["git", "ls-remote", "https://github.com/example/repo.git", "HEAD"]
    assert captured["env"]["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraHeader"
    assert "secret-token" not in captured["env"]["GIT_CONFIG_VALUE_0"]


def test_recovery_refuses_github_pat_for_non_github_host(monkeypatch):
    monkeypatch.setattr(
        recovery,
        "normalize_repository_url",
        lambda _value: "https://git.example.internal/example/repo.git",
    )
    service = recovery.AutoRecoveryService()

    with pytest.raises(ValueError, match="non-GitHub host"):
        service._git_ls_remote("https://git.example.internal/example/repo.git", "secret-token")


def test_recovery_does_not_use_cross_workspace_organization(credential_store, monkeypatch):
    _SessionFactory, values = credential_store
    item = project(
        workspace_id=values["first_workspace_id"],
        organization_id=values["second_org_id"],
    )
    called = {"remote": False}

    def fail_if_called(*args, **kwargs):
        called["remote"] = True
        raise AssertionError("cross-workspace credential must not reach network check")

    service = recovery.AutoRecoveryService()
    monkeypatch.setattr(service, "_git_ls_remote", fail_if_called)

    decision = service._recover_github_access(item, execution_attempt=1)

    assert decision.status == "needs_authorization"
    assert called["remote"] is False
