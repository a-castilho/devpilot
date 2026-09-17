from app.delivery_readiness_guard import _requires_dockerfile
from app.models import Project


def project(config: str) -> Project:
    return Project(workspace_id="w", name="Front", slug="front", repository_url="https://github.com/a/front", default_branch="main", codex_config=config)


def test_frontend_only_delivery_does_not_require_dockerfile():
    item = project('{"project_blueprint":{"databases":["none"],"backend":["none"],"frontend":["static"]}}')
    assert _requires_dockerfile(item) is False


def test_render_delivery_requires_dockerfile():
    item = project("{}")
    assert _requires_dockerfile(item) is True
