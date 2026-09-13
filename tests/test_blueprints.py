from pathlib import Path

import pytest

from app.services.blueprints import BlueprintError, BlueprintRegistry


def manifest(**changes):
    value = {
        "name": "fullstack-fastapi-react-postgres",
        "version": "1.0.0",
        "type": "fullstack",
        "status": "stable",
        "stack": {"backend": "fastapi", "frontend": "react", "database": "postgresql"},
        "capabilities": ["rest-api", "docker", "health-check"],
        "parameters": ["project_name"],
        "files": {"README.md": "# {{ project_name }}\n"},
        "validation": ["backend_tests"],
    }
    value.update(changes)
    return value


def test_register_is_immutable(tmp_path: Path):
    registry = BlueprintRegistry(tmp_path)
    registry.register(manifest())
    with pytest.raises(BlueprintError, match="imutável"):
        registry.register(manifest())


def test_match_prefers_compatible_stable_blueprint(tmp_path: Path):
    registry = BlueprintRegistry(tmp_path)
    registry.register(manifest())
    matches = registry.match(stack={"backend": "fastapi", "frontend": "react"}, capabilities=["docker"], project_type="fullstack")
    assert matches[0].name == "fullstack-fastapi-react-postgres"
    assert matches[0].score >= 90


def test_materialize_replaces_declared_parameters(tmp_path: Path):
    registry = BlueprintRegistry(tmp_path / "registry")
    registry.register(manifest())
    result = registry.materialize("fullstack-fastapi-react-postgres", "1.0.0", tmp_path / "project", {"project_name": "CandidataAI"})
    assert (tmp_path / "project" / "README.md").read_text() == "# CandidataAI\n"
    assert result["version"] == "1.0.0"


def test_materialize_does_not_overwrite_by_default(tmp_path: Path):
    registry = BlueprintRegistry(tmp_path / "registry")
    registry.register(manifest())
    destination = tmp_path / "project"
    destination.mkdir()
    (destination / "README.md").write_text("existing")
    with pytest.raises(BlueprintError, match="já existe"):
        registry.materialize("fullstack-fastapi-react-postgres", "1.0.0", destination, {"project_name": "X"})


def test_rejects_path_traversal(tmp_path: Path):
    registry = BlueprintRegistry(tmp_path)
    with pytest.raises(BlueprintError, match="Caminho inseguro"):
        registry.register(manifest(files={"../escape.txt": "x"}))


def test_rejects_probable_secret(tmp_path: Path):
    registry = BlueprintRegistry(tmp_path)
    with pytest.raises(BlueprintError, match="secret"):
        registry.register(manifest(files={"config.txt": "api_key=abcdefghijklmnop"}))


def test_records_validation_outcome(tmp_path: Path):
    registry = BlueprintRegistry(tmp_path)
    registry.register(manifest())
    metrics = registry.record_outcome("fullstack-fastapi-react-postgres", "1.0.0", True)
    assert metrics == {"uses": 1, "successes": 1, "failures": 0}
