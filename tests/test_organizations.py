import os
from pathlib import Path

os.environ.setdefault("DEVPILOT_BOOTSTRAP_TOKEN", "test-token-with-at-least-32-characters")

from sqlalchemy import create_engine, inspect, text

import app.models  # noqa: F401
from app.db import Base
from app.schemas import OrganizationCreate, normalize_organization_identifier
from app.services.executor import github_basic_authorization
from app.services.organizations import normalize_github_repository, project_slug
from app.services.schema import ensure_runtime_schema


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


def test_organization_identifier_normalization_strips_separator_after_truncation():
    value = "a" * 38 + " b"
    normalized = normalize_organization_identifier(value, max_length=39)
    assert normalized == "a" * 38
    assert not normalized.endswith("-")


def test_organization_create_accepts_one_character_github_login():
    organization = OrganizationCreate(
        name="X Org",
        slug="X Organização",
        github_login="x",
    )
    assert organization.slug == "x-organizacao"
    assert organization.github_login == "x"


def test_organization_ui_keeps_save_valid_and_non_blocking():
    script = (
        Path(__file__).parents[1] / "app" / "static" / "organization-normalization-ui.js"
    ).read_text(encoding="utf-8")
    assert "normalizedLogin.length < 1" in script
    assert "form.onsubmit = async event =>" in script
    assert ".slice(0, maxLength)" in script
    assert ".replace(/^-+|-+$/g, '');" in script
    assert "finally {" in script
    assert "void (async () => {" in script
    assert script.index("finally {") < script.index("void (async () => {")


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
