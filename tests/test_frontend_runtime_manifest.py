from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "app/static/runtime-manifest.js"
LOADER = ROOT / "app/static/feature-loader.js"
STATIC = ROOT / "app/static"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_runtime_manifest_is_single_feature_inventory():
    manifest = read(MANIFEST)
    loader = read(LOADER)

    assert "window.__devpilotRuntimeManifest" in manifest
    assert "window.__devpilotRuntimeManifest" in loader
    assert "MANIFEST_SRC" in loader
    assert "const FEATURE_BUNDLES = Object.freeze" not in loader


def test_required_product_surfaces_are_pinned_in_manifest():
    manifest = read(MANIFEST)
    required = (
        "simplified-nav.js",
        "mobile-accordion-menu.js",
        "project-ships.js",
        "product-delivery-ui.js",
        "task-analytics.js",
        "task-failures.js",
        "task-image-upload.js",
        "task-workflow-observability.js",
        "repeatai-live-graphs.js",
        "super-admin-task-panel.js",
        "token-usage.js",
        "cloud-admin.js",
        "deploy-admin.js",
        "rag-admin-ui.js",
        "rag-jobs-ui.js",
        "super-admin-voice.js",
        "audit-integrity.js",
    )
    for asset in required:
        assert asset in manifest, asset
        assert (STATIC / asset).is_file(), asset


def test_project_navigation_can_only_load_project_bundle():
    manifest = read(MANIFEST)
    assert "{selector: '.nav[data-view=\"projects\"]', feature: 'projects'}" in manifest
    assert "projects: [" in manifest
    assert "'project-ships.js'" in manifest


def test_super_admin_bundle_keeps_all_dashboards():
    manifest = read(MANIFEST)
    admin_block = manifest.split("admin: [", 1)[1].split("],", 1)[0]
    for asset in (
        "super-admin-task-panel.js",
        "token-usage.js",
        "deploy-admin.js",
        "cloud-admin.js",
        "super-admin-local-test.js",
        "investia-admin.js",
        "investia-homologation.js",
        "game-rules-admin.js",
        "linux-terminal.js",
        "career-linkedin.js",
        "mission-control.js",
        "rag-admin-ui.js",
        "rag-jobs-ui.js",
    ):
        assert asset in admin_block, asset


def test_explicit_navigation_uses_cooperative_progressive_loading():
    loader = read(LOADER)
    assert "shortYield" in loader
    assert "idleYield" in loader
    assert "feature-critical-ready" in loader
    assert "scheduleBackground" in loader
    assert "intentEpoch" in loader
    assert "devpilot-low-power" in loader


def test_manifest_references_only_existing_javascript_assets():
    manifest = read(MANIFEST)
    assets = set(re.findall(r"'([a-z0-9][a-z0-9._-]+\\.js)'", manifest, re.I))
    assert assets
    missing = sorted(asset for asset in assets if not (STATIC / asset).is_file())
    assert missing == []
