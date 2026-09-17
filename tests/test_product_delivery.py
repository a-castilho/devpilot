from app.models import Project
from app.product_delivery_routes import initial_delivery, selected_providers, verify
from app.services.github_provisioning import starter_files


def project_with_config(config: str = "{}") -> Project:
    return Project(
        workspace_id="workspace-1",
        organization_id=None,
        name="Produto Cliente",
        slug="produto-cliente",
        description="",
        repository_url="https://github.com/a-castilho/produto-cliente.git",
        default_branch="main",
        agents_md="",
        codex_config=config,
    )


def test_starter_is_deployable_and_contains_no_database_secret():
    files = starter_files("produto-cliente", "Produto do cliente")
    assert "Dockerfile" in files
    assert "backend/main.py" in files
    assert "index.html" in files
    assert "vercel.json" in files
    assert ".devpilot-product.json" in files
    assert "SELECT 1" in files["backend/main.py"]
    assert "DATABASE_URL" in files["backend/main.py"]
    assert "postgresql://" not in "\n".join(files.values())
    assert "Bearer " not in "\n".join(files.values())


def test_default_project_requests_complete_product_stack():
    assert selected_providers(project_with_config()) == ["neon", "render", "vercel"]


def test_frontend_only_project_does_not_request_database_or_backend():
    project = project_with_config('{"project_blueprint":{"databases":["none"],"backend":["none"],"frontend":["static"]}}')
    assert selected_providers(project) == ["vercel"]


def test_delivery_state_is_persistent_shape():
    state = initial_delivery(project_with_config())
    assert state["status"] == "pending"
    assert state["url"] == ""
    assert state["providers"] == {}
    assert state["checks"] == []


def test_waiting_code_guard_has_automatic_starter_repair_path():
    from app import delivery_readiness_guard as guard
    assert callable(guard._repair_deployable_revision)


def test_verify_frontend_only_requires_only_frontend(monkeypatch):
    class Response:
        status_code = 200
    class Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, *args, **kwargs): return Response()
    monkeypatch.setattr("app.product_delivery_routes.httpx.Client", Client)
    state = {"requested": ["vercel"], "providers": {"vercel": {"url": "https://front.example"}}}
    result = verify(state)
    assert result["status"] == "ready"
    assert [item["name"] for item in result["checks"]] == ["frontend"]


def test_verify_fullstack_database_is_proven_by_backend_health_not_vercel_health(monkeypatch):
    calls = []
    class Response:
        status_code = 200
    class Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, **kwargs):
            calls.append(url)
            return Response()
    monkeypatch.setattr("app.product_delivery_routes.httpx.Client", Client)
    state = {
        "requested": ["neon", "render", "vercel"],
        "providers": {
            "neon": {"status": "provisioned"},
            "render": {"url": "https://api.example"},
            "vercel": {"url": "https://front.example"},
        },
    }
    result = verify(state)
    assert result["status"] == "ready"
    assert "https://front.example/health" not in calls
    assert {item["name"] for item in result["checks"]} == {"database", "backend", "frontend"}
