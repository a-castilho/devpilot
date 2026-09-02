from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_UI = ROOT / "app/static/project-delete-ui.js"
FEATURE_LOADER = ROOT / "app/static/feature-loader.js"


def test_low_power_projects_keep_delivery_module_light_but_expose_ready_link():
    ui = PROJECT_UI.read_text(encoding="utf-8")
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    light_block = loader.split("const PROJECTS_LIGHT_FILES = new Set([", 1)[1].split("]);", 1)[0]
    assert "project-delete-ui.js" in light_block
    assert "product-delivery-ui.js" not in light_block

    assert "function lowPowerProjects()" in ui
    assert "function ensureReadyLink(card, project)" in ui
    assert "`/api/projects/${encodeURIComponent(project.id)}/delivery`" in ui
    assert "normalizeStatus(delivery?.status) === 'ready'" in ui
    assert "safePublicUrl(delivery?.url)" in ui
    assert "project-ready-link" in ui
    assert "Abrir projeto ↗" in ui
    assert "link.target = '_blank'" in ui
    assert "link.rel = 'noopener noreferrer'" in ui


def test_ready_link_is_bounded_for_low_memory_runtime():
    ui = PROJECT_UI.read_text(encoding="utf-8")

    assert "const READY_CACHE_TTL_MS = 30000" in ui
    assert "const readyDeliveryCache = new Map()" in ui
    assert "const readyDeliveryRequests = new Map()" in ui
    assert "if (!lowPowerProjects()" in ui
    assert "readyDeliveryRequests.has(key)" in ui
    assert "readyDeliveryCache.clear()" in ui
