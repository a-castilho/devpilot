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
        self.content = b"{}"

    def json(self):
        return self._payload


class FakeClient:
    responses = []
    requests = []
    last_headers = None

    def __init__(self, *args, headers=None, **kwargs):
        FakeClient.last_headers = headers

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json):
        FakeClient.requests.append((url, json))
        return FakeClient.responses.pop(0)


def github_repository_payload(name="novo-projeto"):
    return {
        "id": 456,
        "name": name,
        "full_name": f"a-castilho/{name}",
        "description": "Projeto criado pelo DevPilot",
        "clone_url": f"https://github.com/a-castilho/{name}.git",
        "default_branch": "main",
        "visibility": "private",
        "archived": False,
        "private": True,
    }


def github_name_collision_payload():
    return {
        "message": "Repository creation failed.",
        "errors": [
            {
                "resource": "Repository",
                "field": "name",
                "code": "custom",
                "message": "name already exists on this account",
            }
        ],
    }


def prepare(monkeypatch, responses):
    FakeClient.responses = list(responses)
    FakeClient.requests = []
    monkeypatch.setattr(github_provisioning.httpx, "Client", FakeClient)
    monkeypatch.setattr(github_provisioning, "bootstrap_repository", lambda *args, **kwargs: {"status": "ready"})
    monkeypatch.setattr(github_provisioning, "_resume_managed_repository", lambda *args, **kwargs: None)


def test_project_provisioning_is_locked_to_a_castilho():
    assert AUTHORIZED_ORGANIZATION == "a-castilho"
    payload = ProjectProvisionCreate(name="Novo Projeto", slug="novo-projeto")
    assert payload.slug == "novo-projeto"


def test_create_github_repository_creates_private_initialized_repository(monkeypatch):
    prepare(monkeypatch, [FakeResponse(201, github_repository_payload())])

    result = create_github_repository(
        "a-castilho",
        "novo-projeto",
        "Projeto criado pelo DevPilot",
        "secret-token",
    )

    url, payload = FakeClient.requests[0]
    assert url == "https://api.github.com/orgs/a-castilho/repos"
    assert payload == {
        "name": "novo-projeto",
        "description": "Projeto criado pelo DevPilot",
        "private": True,
        "auto_init": True,
    }
    assert FakeClient.last_headers["Authorization"] == "Bearer secret-token"
    assert result["full_name"] == "a-castilho/novo-projeto"


def test_repository_description_is_normalized_before_github_request(monkeypatch):
    prepare(monkeypatch, [FakeResponse(201, github_repository_payload())])
    description = "  Linha 1\nLinha\t2\x00  " + ("conteúdo " * 80)

    create_github_repository(
        "a-castilho",
        "novo-projeto",
        description,
        "secret-token",
    )

    sent_description = FakeClient.requests[0][1]["description"]
    assert sent_description == github_provisioning.sanitize_repository_description(description)
    assert len(sent_description) == github_provisioning.MAX_REPOSITORY_DESCRIPTION_LENGTH
    assert "\n" not in sent_description
    assert "\t" not in sent_description
    assert "\x00" not in sent_description
    assert "  " not in sent_description


def test_repository_description_sanitizer_keeps_short_valid_text_unchanged():
    description = "API segura para pedidos e faturamento"
    assert github_provisioning.sanitize_repository_description(description) == description


def test_repository_name_collision_is_resolved_without_user_action(monkeypatch):
    prepare(
        monkeypatch,
        [
            FakeResponse(422, github_name_collision_payload()),
            FakeResponse(201, github_repository_payload("novo-projeto-2")),
        ],
    )

    result = create_github_repository(
        "a-castilho",
        "novo-projeto",
        "Projeto criado pelo DevPilot",
        "secret-token",
    )

    assert [payload["name"] for _, payload in FakeClient.requests] == [
        "novo-projeto",
        "novo-projeto-2",
    ]
    assert result["name"] == "novo-projeto-2"
    assert result["full_name"] == "a-castilho/novo-projeto-2"


def test_second_collision_uses_next_available_suffix(monkeypatch):
    prepare(
        monkeypatch,
        [
            FakeResponse(422, github_name_collision_payload()),
            FakeResponse(422, github_name_collision_payload()),
            FakeResponse(201, github_repository_payload("novo-projeto-3")),
        ],
    )

    result = create_github_repository(
        "a-castilho", "novo-projeto", "", "secret-token"
    )

    assert [payload["name"] for _, payload in FakeClient.requests] == [
        "novo-projeto",
        "novo-projeto-2",
        "novo-projeto-3",
    ]
    assert result["name"] == "novo-projeto-3"


def test_description_validation_error_is_specific_and_not_retried(monkeypatch):
    prepare(
        monkeypatch,
        [
            FakeResponse(
                422,
                {
                    "message": "Repository creation failed.",
                    "errors": [
                        {
                            "resource": "Repository",
                            "field": "description",
                            "code": "custom",
                            "message": "description control characters are not allowed",
                        },
                        {
                            "resource": "Repository",
                            "field": "description",
                            "code": "custom",
                            "message": "description cannot be more than 350 characters",
                        },
                    ],
                },
            )
        ],
    )

    with pytest.raises(GitHubProvisioningError) as error:
        create_github_repository(
            "a-castilho", "novo-projeto", "descrição válida", "secret-token"
        )

    assert error.value.status_code == 422
    assert len(FakeClient.requests) == 1
    message = str(error.value)
    assert "campo de descrição" in message
    assert "normalização automática" in message
    assert "não em credencial ou permissão" in message
    assert "regra de validação da organização" not in message
    assert "Verifique políticas" not in message


def test_non_collision_validation_error_is_not_retried_or_misreported(monkeypatch):
    prepare(
        monkeypatch,
        [
            FakeResponse(
                422,
                {
                    "message": "Repository creation failed.",
                    "errors": [
                        {
                            "resource": "Repository",
                            "code": "custom",
                            "message": "Custom property environment is required",
                        }
                    ],
                },
            )
        ],
    )

    with pytest.raises(GitHubProvisioningError) as error:
        create_github_repository(
            "a-castilho", "novo-projeto", "", "secret-token"
        )

    assert error.value.status_code == 422
    assert len(FakeClient.requests) == 1
    assert "Custom property environment is required" in str(error.value)
    assert "regra de validação" in str(error.value)
    assert "reservar um nome" not in str(error.value)


def test_create_github_repository_requires_authorized_credential():
    with pytest.raises(GitHubProvisioningError) as error:
        create_github_repository("a-castilho", "novo-projeto", "", "")
    assert error.value.status_code == 409
    assert "credencial" in str(error.value).lower()


def test_create_github_repository_translates_invalid_token(monkeypatch):
    prepare(monkeypatch, [FakeResponse(401, {"message": "Bad credentials"})])

    with pytest.raises(GitHubProvisioningError) as error:
        create_github_repository("a-castilho", "novo-projeto", "", "expired-token")

    assert error.value.status_code == 401
    assert "inválido" in str(error.value)


def test_create_github_repository_translates_permission_failure(monkeypatch):
    prepare(monkeypatch, [FakeResponse(403)])

    with pytest.raises(GitHubProvisioningError) as error:
        create_github_repository("a-castilho", "novo-projeto", "", "token-without-write")

    assert error.value.status_code == 403
    assert "não autoriza" in str(error.value)
    assert "Administration: Read and write" in str(error.value)
    assert "Contents: Read and write" in str(error.value)


def test_starter_permission_failure_explains_required_contents_scope():
    with pytest.raises(GitHubProvisioningError) as error:
        github_provisioning._translate_starter_error(403, operation="verificar")

    assert error.value.status_code == 403
    message = str(error.value)
    assert "Contents: Read and write" in message
    assert "Resource owner = a-castilho" in message
    assert "Super Admin > Organizações" in message


def test_starter_invalid_token_is_returned_as_unauthorized():
    with pytest.raises(GitHubProvisioningError) as error:
        github_provisioning._translate_starter_error(401, operation="gravar")

    assert error.value.status_code == 401
    assert "inválido ou expirou" in str(error.value)
