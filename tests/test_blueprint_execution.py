from __future__ import annotations

import json
from types import SimpleNamespace

from app.blueprint_execution import prepare_blueprint_workspace
from app.blueprint_routes import registry


def project(config: dict):
    return SimpleNamespace(
        id="project-blueprint-test",
        name="Minha API",
        slug="minha-api",
        codex_config=json.dumps(config),
    )


def test_selected_blueprint_materializes_missing_files_only(tmp_path):
    target = tmp_path / "repo"
    target.mkdir()
    (target / "README.md").write_text("conteudo existente\n", encoding="utf-8")
    config = {
        "generation_strategy": "blueprint_delta",
        "blueprint": {"slug": "backend-fastapi", "version": "1.0.0"},
    }

    result = prepare_blueprint_workspace(project(config), target)

    assert result["generation_strategy"] == "blueprint_delta"
    assert (target / "README.md").read_text(encoding="utf-8") == "conteudo existente\n"
    assert (target / "app/main.py").is_file()
    assert "README.md" in result["skipped_existing"]
    assert "app/main.py" in result["created"]
    assert (target / ".devpilot/blueprint.json").is_file()


def test_blueprint_materialization_is_idempotent(tmp_path):
    target = tmp_path / "repo"
    target.mkdir()
    config = {
        "generation_strategy": "blueprint_delta",
        "blueprint": {"slug": "backend-fastapi", "version": "1.0.0"},
    }
    item = project(config)

    first = prepare_blueprint_workspace(item, target)
    second = prepare_blueprint_workspace(item, target)

    assert second == first


def test_non_blueprint_strategy_does_not_touch_repository(tmp_path):
    target = tmp_path / "repo"
    target.mkdir()
    assert prepare_blueprint_workspace(project({"generation_strategy": "from_scratch"}), target) is None
    assert list(target.iterdir()) == []
