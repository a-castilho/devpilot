from __future__ import annotations

from app import product_delivery_routes as delivery


MANDATORY_PROJECT_PROVIDERS = ["neon", "render", "vercel"]
MANDATORY_ARCHITECTURE = {
    "frontend": "vercel",
    "backend": "render",
    "database": "neon",
}


def mandatory_selected_providers(_project) -> list[str]:
    """Every DevPilot project is delivered with the same managed cloud triad.

    Frontend: Vercel
    Backend: Render
    Database: Neon

    Keeping this invariant in one place avoids architecture drift between project
    types and guarantees the delivery state machine always provisions and verifies
    the full stack before marking a product ready.
    """
    return list(MANDATORY_PROJECT_PROVIDERS)


setattr(mandatory_selected_providers, "_devpilot_adaptive_delivery", True)


def install_mandatory_cloud_policy() -> None:
    delivery.selected_providers = mandatory_selected_providers


install_mandatory_cloud_policy()
