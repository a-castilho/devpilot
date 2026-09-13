from __future__ import annotations

import pytest

from app.blueprints import (
    BlueprintFile,
    BlueprintManifest,
    BlueprintRegistry,
    BlueprintRenderError,
    BlueprintService,
    BlueprintStatus,
    ProjectRequirements,
)


def manifest(version: str = "1.0.0") -> BlueprintManifest:
    return BlueprintManifest(
        slug="fastapi-react",
        name="FastAPI React",
        version=version,
        status=BlueprintStatus.stable,
        stack={"backend": "fastapi", "frontend": "react"},
        capabilities=("rest-api", "frontend"),
        parameters=("project_name",),
        tags=("python", "saas"),
        files=(BlueprintFile("README.md", "# {{ project_name }}\n"),),
    )


def test_registry_versions_and_latest(tmp_path):
    registry = BlueprintRegistry(tmp_path)
    registry.register(manifest("1.0.0"))
    registry.register(manifest("1.2.0"))

    assert registry.get("fastapi-react").version == "1.2.0"
    assert [item.version for item in registry.list(latest_only=False)] == ["1.0.0", "1.2.0"]


def test_matcher_prefers_compatible_blueprint(tmp_path):
    registry = BlueprintRegistry(tmp_path)
    registry.register(manifest())
    service = BlueprintService(registry)

    matches = service.recommend(
        ProjectRequirements(
            description="SaaS Python",
            stack={"backend": "fastapi", "frontend": "react"},
            capabilities=("rest-api",),
        )
    )

    assert matches
    assert matches[0].slug == "fastapi-react"
    assert matches[0].score >= 0.7


def test_render_requires_parameters_and_blocks_path_escape(tmp_path):
    registry = BlueprintRegistry(tmp_path)
    registry.register(manifest())
    service = BlueprintService(registry)

    with pytest.raises(BlueprintRenderError, match="missing blueprint parameters"):
        service.render("fastapi-react", {})

    rendered = service.render("fastapi-react", {"project_name": "CandidateAI"})
    assert rendered.files["README.md"] == "# CandidateAI\n"

    unsafe = BlueprintManifest(
        slug="unsafe",
        name="Unsafe",
        version="1.0.0",
        parameters=("project_name",),
        files=(BlueprintFile("../outside.txt", "{{ project_name }}"),),
    )
    registry.register(unsafe)
    with pytest.raises(BlueprintRenderError, match="unsafe blueprint path"):
        service.render("unsafe", {"project_name": "x"})


def test_registry_rejects_embedded_secret(tmp_path):
    registry = BlueprintRegistry(tmp_path)
    unsafe = BlueprintManifest(
        slug="secret",
        name="Secret",
        version="1.0.0",
        files=(BlueprintFile(".env", "API_KEY=real-secret-value\n"),),
    )
    with pytest.raises(BlueprintRenderError, match="possible secret"):
        registry.register(unsafe)


def test_usage_metrics(tmp_path):
    registry = BlueprintRegistry(tmp_path)
    registry.record_usage(project_id="p1", slug="fastapi-react", version="1.0.0", score=0.8)
    registry.record_usage(
        project_id="p1", slug="fastapi-react", version="1.0.0", score=0.8, outcome="completed"
    )
    metrics = registry.metrics()["fastapi-react@1.0.0"]
    assert metrics["uses"] == 2
    assert metrics["successful"] == 1
    assert metrics["success_rate"] == 0.5
