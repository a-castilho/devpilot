"""DevPilot application package."""

# Homologation-only infrastructure bootstrap. Importing this module is safe in
# other environments because it self-disables unless the runtime is homologation.
from app import render_autoprovision_bootstrap as _render_autoprovision_bootstrap  # noqa: F401,E402
