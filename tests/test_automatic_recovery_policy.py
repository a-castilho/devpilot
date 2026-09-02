import json
from types import SimpleNamespace

from app.services import executor
from app.services.recovery import AutoRecoveryService


def test_codex_401_rotates_registered_credentials_before_human_escalation(monkeypatch):
    service = AutoRecoveryService()
    project = SimpleNamespace(workspace_id="ws-1", codex_config="{}")
    task = SimpleNamespace(id="task-1")

    monkeypatch.setattr(
        service,
        "_available_openai_credentials",
        lambda _project: [("cred-1", "OpenAI principal"), ("cred-2", "OpenAI reserva")],
    )

    first = service.recover(
        project,
        task,
        "codex_api::endpoint::responses_websocket: HTTP error: 401 Unauthorized",
        1,
    )

    assert first.category == "codex_auth"
    assert first.retry is True
    assert first.requires_authorization is False
    assert first.strategy == "codex_credential_failover"
    assert json.loads(project.codex_config)["credential_id"] == "cred-1"

    second = service.recover(
        project,
        task,
        "codex_api::endpoint::responses_websocket: HTTP error: 401 Unauthorized",
        2,
    )

    assert second.retry is True
    assert second.requires_authorization is False
    assert json.loads(project.codex_config)["credential_id"] == "cred-2"

    exhausted = service.recover(
        project,
        task,
        "codex_api::endpoint::responses_websocket: HTTP error: 401 Unauthorized",
        3,
    )

    assert exhausted.retry is False
    assert exhausted.requires_authorization is True
    assert exhausted.strategy == "request_codex_authorization_after_exhaustion"
    assert "esgotou" in exhausted.message.lower()


def test_database_failure_retries_before_automatic_root_cause_recovery(monkeypatch):
    service = AutoRecoveryService()
    project = SimpleNamespace(workspace_id="ws-1", codex_config="{}")
    task = SimpleNamespace(id="task-1")
    monkeypatch.setattr("app.services.recovery.time.sleep", lambda _seconds: None)

    retry = service.recover(project, task, "sqlalchemy.exc.OperationalError: connection refused", 1)
    assert retry.retry is True
    assert retry.requires_authorization is False
    assert retry.strategy == "database_reconnect_retry"

    exhausted = service.recover(project, task, "sqlalchemy.exc.OperationalError: connection refused", 3)
    assert exhausted.retry is False
    assert exhausted.requires_authorization is False
    assert exhausted.strategy == "database_recovery_escalation"


def test_codex_environment_uses_only_project_scoped_openai_credential(monkeypatch):
    project = SimpleNamespace(
        workspace_id="ws-1",
        codex_config=json.dumps({"credential_id": "cred-1", "model": "gpt-test"}),
    )
    credential = SimpleNamespace(encrypted_secret="encrypted-value")

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def scalar(self, _statement):
            return credential

    class FakeVault:
        def decrypt(self, value):
            assert value == "encrypted-value"
            return "sk-project-scoped"

    monkeypatch.setattr(executor, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(executor, "Vault", lambda: FakeVault())

    assert executor.codex_environment(project) == {
        "CODEX_API_KEY": "sk-project-scoped",
        "OPENAI_API_KEY": "",
    }


def test_codex_environment_preserves_existing_codex_auth_without_selected_credential():
    project = SimpleNamespace(workspace_id="ws-1", codex_config="{}")

    assert executor.codex_environment(project) == {}
