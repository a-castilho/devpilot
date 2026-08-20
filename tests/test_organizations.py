import os

os.environ.setdefault("DEVPILOT_BOOTSTRAP_TOKEN", "test-token-with-at-least-32-characters")

from sqlalchemy import create_engine, inspect, text

import app.models  # noqa: F401
from app.db import Base
from app.services.executor import github_basic_authorization
from app.services.organizations import normalize_github_repository, project_slug
from app.services.schema import ensure_runtime_schema
from app.schemas import OrganizationCreate


def test_organization_schema_creates_relationship_tables():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    tables = set(inspect(engine).get_table_names())
    assert "organizations" in tables
    assert "repositories" in tables
    project_columns = {column["name"] for column in inspect(engine).get_columns("projects")}
    assert "organization_id" in project_columns


def test_runtime_schema_upgrades_existing_projects_table():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE projects (id VARCHAR(36) PRIMARY KEY)"))
    ensure_runtime_schema(engine)
    project_columns = {column["name"] for column in inspect(engine).get_columns("projects")}
    assert "organization_id" in project_columns


def test_project_slug_is_safe_for_devpilot_projects():
    assert project_slug("Marketplace Fiscal") == "marketplace-fiscal"
    assert project_slug("A") == "a-repo"
    assert project_slug("repo_com.pontos") == "repo-com-pontos"


def test_normalize_github_repository_removes_sensitive_noise():
    result = normalize_github_repository(
        {
            "id": 123,
            "name": "regulaai",
            "full_name": "a-castilho/regulaai",
            "description": None,
            "clone_url": "https://github.com/a-castilho/regulaai.git",
            "default_branch": "main",
            "visibility": "private",
            "archived": False,
            "owner": {"login": "a-castilho"},
        }
    )
    assert result == {
        "external_id": "123",
        "name": "regulaai",
        "full_name": "a-castilho/regulaai",
        "description": "",
        "clone_url": "https://github.com/a-castilho/regulaai.git",
        "default_branch": "main",
        "visibility": "private",
        "archived": False,
    }


def test_private_git_authorization_does_not_embed_raw_token():
    header = github_basic_authorization("secret-token")
    assert header.startswith("Authorization: Basic ")
    assert "secret-token" not in header


def test_organization_identifiers_normalize_accents_before_validation():
    organization = OrganizationCreate(
        name="A Organização",
        slug="A Organização",
        github_login="A-Organização",
    )
    assert organization.slug == "a-organizacao"
    assert organization.github_login == "a-organizacao"
