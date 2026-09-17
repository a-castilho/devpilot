from app.models import Project
from app.product_delivery_routes import initial_delivery, selected_providers, verify, provision_vercel
from app.services.github_provisioning import starter_files


def project_with_config(config: str = "{}") -> Project:
    return Project(workspace_id="workspace-1", organization_id=None, name="Produto Cliente", slug="produto-cliente", description="", repository_url="https://github.com/a-castilho/produto-cliente.git", default_branch="main", agents_md="", codex_config=config)


def test_starter_is_deployable_and_contains_no_database_secret():
    files = starter_files("produto-cliente", "Produto do cliente")
    assert "Dockerfile" in files and "backend/main.py" in files and "index.html" in files and "vercel.json" in files and ".devpilot-product.json" in files
    assert "SELECT 1" in files["backend/main.py"] and "DATABASE_URL" in files["backend/main.py"]
    assert "postgresql://" not in "\n".join(files.values()) and "Bearer " not in "\n".join(files.values())


def test_default_project_requests_complete_product_stack(): assert selected_providers(project_with_config()) == ["neon", "render", "vercel"]

def test_frontend_only_project_does_not_request_database_or_backend():
    project = project_with_config('{"project_blueprint":{"databases":["none"],"backend":["none"],"frontend":["static"]}}')
    assert selected_providers(project) == ["vercel"]

def test_delivery_state_is_persistent_shape():
    state = initial_delivery(project_with_config()); assert state["status"] == "pending" and state["url"] == "" and state["providers"] == {} and state["checks"] == []

def test_waiting_code_guard_has_automatic_starter_repair_path():
    from app import delivery_readiness_guard as guard
    assert callable(guard._repair_deployable_revision)

def test_verify_frontend_only_requires_only_frontend(monkeypatch):
    class Response: status_code = 200
    class Client:
        def __init__(self,*a,**k): pass
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def get(self,*a,**k): return Response()
    monkeypatch.setattr("app.product_delivery_routes.httpx.Client", Client)
    result=verify({"requested":["vercel"],"providers":{"vercel":{"url":"https://front.example"}}})
    assert result["status"]=="ready" and [x["name"] for x in result["checks"]]==["frontend"]

def test_verify_fullstack_database_is_proven_by_backend_health_not_vercel_health(monkeypatch):
    calls=[]
    class Response: status_code=200
    class Client:
        def __init__(self,*a,**k): pass
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def get(self,url,**k): calls.append(url); return Response()
    monkeypatch.setattr("app.product_delivery_routes.httpx.Client", Client)
    state={"requested":["neon","render","vercel"],"providers":{"neon":{"status":"provisioned","project_id":"n1"},"render":{"url":"https://api.example"},"vercel":{"url":"https://front.example"}}}
    result=verify(state)
    assert result["status"]=="ready" and "https://front.example/health" not in calls
    assert {x["name"] for x in result["checks"]}=={"database","backend","frontend"}


def test_vercel_existing_project_without_url_creates_a_fresh_deployment(monkeypatch):
    calls=[]
    class Client: pass
    def fake_request(client, provider, method, url, token, **kwargs):
        calls.append((method,url,kwargs.get("payload")))
        if url.endswith("/deployments"):
            return {"id":"dpl_new","url":"produto-cliente.vercel.app"}
        return {}
    monkeypatch.setattr("app.product_delivery_routes.request_json", fake_request)
    state={"providers":{"vercel":{"project_id":"prj_existing","deployment_id":"dpl_stale","url":""}}}
    url=provision_vercel(Client(),"token","team_1",project_with_config(),state,"https://api.example","a-castilho/produto-cliente")
    assert url=="https://produto-cliente.vercel.app"
    assert state["providers"]["vercel"]["deployment_id"]=="dpl_new"
    assert any(path.endswith("/deployments") for _,path,_ in calls)
