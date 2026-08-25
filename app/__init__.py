"""DevPilot application package."""

# Register extension routes on the core API router before app.main includes it.
# The import is intentionally side-effect-only and keeps game workflow out of
# the authenticated frontend boot path.
from app import game_workflow_routes as _game_workflow_routes  # noqa: F401,E402
