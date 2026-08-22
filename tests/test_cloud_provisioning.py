from __future__ import annotations

import json

import httpx

from app.services.cloud_provisioning import (
    CloudConnection,
    CloudProvisioner,
    NeonProvision,
    provision_cloud_stack,
    selected_cloud_providers,
)


def test_selected_cloud_providers_follow_blueprint():
    assert selected_cloud_providers(
        {
            "databases": ["postgresql"],
            "backend": ["fastapi"],
            "frontend": ["react"],
        }
    ) == ["neon", "render", "vercel"]
    assert selected_cloud_providers(
        {
            "databases": ["postgresql"],
            "backend": ["fastapi"],
            "frontend": ["none"],
        }
    ) == ["neon", "render"]
    assert selected_cloud_providers(
        {
            "databases": [],
            "backend": ["none"],
            "frontend": ["react"],
        }
    ) == ["vercel"]


def test_neon_provision_returns_only_public_metadata():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST" and request.url.path == "/api/v2/projects":
            return httpx.Response(
                201,
                json={
                    "project": {"id": "neon-project", "region_id": "aws-sa-east-1"},
                    "branch": {"id": "main-branch"},
                    "databases": [{"name": "app"}],
                    "roles": [{"name": "app"}],
                },
            )
        if request.method == "POST" and request.url.path.endswith("/branches"):
            return httpx.Response(201, json={"branch": {"id": "homolog-branch"}})
        if request.method == "GET" and request.url.path.endswith("/connection_uri"):
            return httpx.Response(
                200,
                json={"uri": "postgresql://secret:password@host.example/app"},
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provisioner = CloudProvisioner(client)
    result = provisioner.provision_neon(
        connection=CloudConnection(token="neon-secret", account_id="org-1"),
        project_name="produto",
    )

    assert result.public["project_id"] == "neon-project"
    assert result.public["homolog_branch_id"] == "homolog-branch"
    assert result.database_url.startswith("postgresql://")
    assert "postgresql://" not in json.dumps(result.public)
    assert all("neon-secret" not in request.url.query.decode() for request in requests)


def test_render_receives_database_url_but_never_returns_it():
    seen_service_body: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_service_body
        if request.method == "POST" and request.url.path == "/v1/projects":
            return httpx.Response(201, json={"id": "render-project"})
        if request.method == "GET" and request.url.path == "/v1/environments":
            return httpx.Response(
                200,
                json=[
                    {"id": "env-homolog", "name": "homolog"},
                    {"id": "env-production", "name": "production"},
                ],
            )
        if request.method == "POST" and request.url.path == "/v1/services":
            seen_service_body = json.loads(request.content)
            return httpx.Response(
                201,
                json={
                    "service": {
                        "id": "srv-1",
                        "url": "https://produto-homolog.onrender.com",
                    }
                },
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provisioner = CloudProvisioner(client)
    secret_url = "postgresql://secret:password@host.example/app"
    result = provisioner.provision_render(
        connection=CloudConnection(token="render-secret", account_id="owner-1"),
        project_name="produto",
        repository_url="https://github.com/a-castilho/produto.git",
        branch="main",
        database_url=secret_url,
    )

    env = {item["key"]: item["value"] for item in seen_service_body["envVars"]}
    assert env["DATABASE_URL"] == secret_url
    assert result["service_id"] == "srv-1"
    assert secret_url not in json.dumps(result)


def test_vercel_links_repository_and_configures_backend_url():
    seen_project: dict = {}
    seen_env: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_project, seen_env
        if request.method == "POST" and request.url.path == "/v11/projects":
            seen_project = json.loads(request.content)
            return httpx.Response(201, json={"id": "prj-1", "name": "produto"})
        if request.method == "POST" and request.url.path == "/v10/projects/prj-1/env":
            seen_env = json.loads(request.content)
            return httpx.Response(201, json={"created": seen_env, "failed": []})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provisioner = CloudProvisioner(client)
    result = provisioner.provision_vercel(
        connection=CloudConnection(token="vercel-secret", account_id="team-1"),
        project_name="produto",
        repository_full_name="a-castilho/produto",
        backend_url="https://produto-homolog.onrender.com",
    )

    assert seen_project["gitRepository"] == {
        "type": "github",
        "repo": "a-castilho/produto",
    }
    assert {item["key"] for item in seen_env} == {
        "APP_BACKEND_URL",
        "NEXT_PUBLIC_API_URL",
        "VITE_API_URL",
    }
    assert all(item["type"] == "encrypted" for item in seen_env)
    assert result == {
        "status": "provisioned",
        "project_id": "prj-1",
        "project_name": "produto",
        "team_id": "team-1",
    }


class FakeProvisioner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def neon_database_url(self, *, connection, metadata):
        self.calls.append("neon_database_url")
        return "postgresql://transient"

    def provision_neon(self, **kwargs):
        self.calls.append("neon")
        return NeonProvision(
            public={
                "status": "ready",
                "project_id": "np",
                "main_branch_id": "main",
                "homolog_branch_id": "homolog",
                "database_name": "app",
                "role_name": "app",
                "region_id": "",
            },
            database_url="postgresql://transient",
        )

    def provision_render(self, **kwargs):
        self.calls.append("render")
        assert kwargs["database_url"] == "postgresql://transient"
        return {
            "status": "provisioned",
            "project_id": "rp",
            "homolog_environment_id": "rh",
            "production_environment_id": "rprod",
            "service_id": "srv",
            "url": "https://produto-homolog.onrender.com",
        }

    def provision_vercel(self, **kwargs):
        self.calls.append("vercel")
        assert kwargs["backend_url"] == "https://produto-homolog.onrender.com"
        return {
            "status": "provisioned",
            "project_id": "vp",
            "project_name": "produto",
            "team_id": "team",
        }


def test_stack_is_resumable_and_does_not_recreate_ready_neon():
    worker = FakeProvisioner()
    existing = {
        "providers": {
            "neon": {
                "status": "ready",
                "project_id": "np",
                "main_branch_id": "main",
                "homolog_branch_id": "homolog",
                "database_name": "app",
                "role_name": "app",
            }
        }
    }
    state = provision_cloud_stack(
        project_name="produto",
        repository_url="https://github.com/a-castilho/produto.git",
        repository_full_name="a-castilho/produto",
        branch="main",
        blueprint={
            "databases": ["postgresql"],
            "backend": ["fastapi"],
            "frontend": ["react"],
        },
        connections={
            "neon": CloudConnection("n"),
            "render": CloudConnection("r", "owner"),
            "vercel": CloudConnection("v", "team"),
        },
        existing=existing,
        provisioner=worker,
    )

    assert state["status"] == "provisioned"
    assert worker.calls == ["neon_database_url", "render", "vercel"]
    assert "postgresql://" not in json.dumps(state)


def test_stack_reports_missing_credentials_without_external_calls():
    worker = FakeProvisioner()
    state = provision_cloud_stack(
        project_name="produto",
        repository_url="https://github.com/a-castilho/produto.git",
        repository_full_name="a-castilho/produto",
        branch="main",
        blueprint={
            "databases": ["postgresql"],
            "backend": ["fastapi"],
            "frontend": ["react"],
        },
        connections={},
        provisioner=worker,
    )

    assert state["status"] == "blocked"
    assert state["missing_credentials"] == ["neon", "render", "vercel"]
    assert worker.calls == []
