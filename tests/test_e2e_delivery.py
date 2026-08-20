import os

os.environ.setdefault("DEVPILOT_BOOTSTRAP_TOKEN", "test-token-with-at-least-32-characters")

from app.e2e import initial_project_prompt
from app.services import github_delivery


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, responses, calls, **kwargs):
        self.responses = list(responses)
        self.calls = calls
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json=None):
        self.calls.append(("POST", url, json))
        return self.responses.pop(0)

    def get(self, url, params=None):
        self.calls.append(("GET", url, params))
        return self.responses.pop(0)


def test_initial_project_prompt_requires_complete_review_ready_project():
    prompt = initial_project_prompt("Projeto E2E")
    assert "GET /health" in prompt
    assert "HTTP 200" in prompt
    assert "automated tests" in prompt
    assert "GitHub Actions CI" in prompt
    assert "isolated task branch" in prompt
    assert "remote publication" in prompt


def test_create_github_repository_is_private_initialized_and_normalized(monkeypatch):
    calls = []
    response = FakeResponse(
        201,
        {
            "id": 9001,
            "name": "teste-e2e",
            "full_name": "a-castilho/teste-e2e",
            "description": "Projeto de teste",
            "clone_url": "https://github.com/a-castilho/teste-e2e.git",
            "default_branch": "main",
            "visibility": "private",
            "archived": False,
            "private": True,
        },
    )

    monkeypatch.setattr(
        github_delivery.httpx,
        "Client",
        lambda **kwargs: FakeClient([response], calls, **kwargs),
    )

    result = github_delivery.create_github_repository(
        "a-castilho",
        "secret-token",
        "teste-e2e",
        description="Projeto de teste",
        private=True,
    )

    assert result["full_name"] == "a-castilho/teste-e2e"
    assert result["clone_url"] == "https://github.com/a-castilho/teste-e2e.git"
    method, url, payload = calls[0]
    assert method == "POST"
    assert url.endswith("/orgs/a-castilho/repos")
    assert payload["private"] is True
    assert payload["auto_init"] is True
    assert "secret-token" not in repr(calls)


def test_ci_status_prefers_completed_check_runs(monkeypatch):
    calls = []
    statuses = FakeResponse(200, {"state": "pending", "statuses": []})
    checks = FakeResponse(
        200,
        {
            "check_runs": [
                {"name": "tests", "status": "completed", "conclusion": "success"},
                {"name": "docker", "status": "completed", "conclusion": "success"},
            ]
        },
    )

    monkeypatch.setattr(
        github_delivery.httpx,
        "Client",
        lambda **kwargs: FakeClient([statuses, checks], calls, **kwargs),
    )

    result = github_delivery.fetch_commit_ci_status(
        "a-castilho/teste-e2e",
        "secret-token",
        "abc123",
    )

    assert result["state"] == "success"
    assert len(result["checks"]) == 2
    assert "secret-token" not in repr(calls)
