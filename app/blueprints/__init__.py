from .domain import (
    BlueprintFile,
    BlueprintManifest,
    BlueprintMatch,
    BlueprintStatus,
    ProjectRequirements,
    RenderedProject,
)
from .matcher import match_blueprints
from .registry import BlueprintRegistry
from .renderer import BlueprintRenderError, render_project, validate_no_embedded_secrets
from .service import BlueprintService

__all__ = [
    "BlueprintFile",
    "BlueprintManifest",
    "BlueprintMatch",
    "BlueprintRegistry",
    "BlueprintRenderError",
    "BlueprintService",
    "BlueprintStatus",
    "ProjectRequirements",
    "RenderedProject",
    "match_blueprints",
    "render_project",
    "validate_no_embedded_secrets",
]

# DevPilot adapter hook. The portable modules above remain framework-independent;
# importing the package inside DevPilot only wraps the canonical checkout once.
try:
    from app.blueprint_runtime_hook import install_blueprint_runtime
    install_blueprint_runtime()
except (ImportError, AttributeError):
    pass
