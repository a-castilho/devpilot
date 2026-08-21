import os

os.environ.setdefault("DEVPILOT_BOOTSTRAP_TOKEN", "test-token-with-at-least-32-characters")

import pytest

from app.project_provisioning_routes import AUTHORIZED_ORGANIZATION, ProjectProvisionCreate
from app.services import github_provisioning
from app.services.github_provisioning import GitHubProvisioningError, create_github_repository


class FakeResponse:
    def __init__(self, status_code=201, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeClient:
    last_headers = None
    last_url = None
    last_json = None
    response = None

    def __init__(self, *args, headers=None, **kwargs):
        FakeClient.last_headers = headers

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json):
        FakeClient.last_url = url
        FakeClient.last_json = json
        return FakeClient.response


def github_repository_payload():
    return {
        "id": 456,
        "name": "novo-projeto",
        "full_name": "a-castilho/novo-projeto",
        "description": "Projeto criado pelo DevPilot",
        "clone_url": "https://github.com/a-castilho/novo-projeto.git",
        "default_branch": "main",
        "visibility": "private",
        "archived": False,
        "private": True,
    }


def test_project_provisioning_is_locked_to_a_castilho():
    assert AUTHORIZED_ORGANIZATION == "a-castilho"
    payload = ProjectProvisionCreate(name="Novo Projeto", slug="novo-projeto")
    assert payload.slug == "novo-projeto"


def test_create_github_repository_creates_private_initialized_repository(monkeypatch):
    FakeClient.response = FakeResponse(201, github_repository_payload())
    monkeypatch.setattr(github_provisioning.httpx, "Client", FakeClient)

    result = create_github_repository(
        "a-castilho",
        "novo-projeto",
        "Projeto criado pelo DevPilot",
        "secret-token",
    )

    assert FakeClient.last_url == "https://api.github.com/orgs/a-castilho/repos"
    assert FakeClient.last_json == {
        "name": "novo-projeto",
        "description": "Projeto criado pelo DevPilot",
        "private": True,
        "auto_init": True,
    }
    assert FakeClient.last_headers["Authorization"] == "Bearer secret-token"
    assert result["full_name"] == "a-castilho/novo-projeto"
    assert result["clone_url"] == "https://github.com/a-castilho/novo-projeto.git"
    assert result["visibility"] == "private"


def test_create_github_repository_requires_authorized_credential():
    with pytest.raises(GitHubProvisioningError) as error:
        create_github_repository("a-castilho", "novo-projeto", "", "")
    assert error.value.status_code == 409
    assert "credencial" in str(error.value).lower()
    assert "Resource owner = a-castilho" in str(error.value)


def test_create_github_repository_translates_invalid_token(monkeypatch):
    FakeClient.response = FakeResponse(401, {"message": "Bad credentials"})
    monkeypatch.setattr(github_provisioning.httpx, "Client", FakeClient)

    with pytest.raises(GitHubProvisioningError) as error:
        create_github_repository("a-castilho", "novo-projeto", "", "expired-token")

    assert error.value.status_code == 401
    assert "inválido" in str(error.value)
    assert "Resource owner = a-castilho" in str(error.value)


def test_create_github_repository_translates_permission_failure(monkeypatch):
    FakeClient.response = FakeResponse(403, {"message": "Resource not accessible by personal access token"})
    monkeypatch.setattr(github_provisioning.httpx, "Client", FakeClient)

    with pytest.raises(GitHubProvisioningError) as error:
        create_github_repository("a-castilho", "novo-projeto", "", "token-without-write")

    assert error.value.status_code == 403
    assert "não autoriza" in str(error.value)
    assert "Resource owner = a-castilho" in str(error.value)
    assert "Administration: Read and write" in str(error.value)
