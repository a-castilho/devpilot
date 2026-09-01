from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEATURE_LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")


def test_mobile_projects_bundle_excludes_heavy_optional_modules():
    assert "PROJECTS_LIGHT_FILES" in FEATURE_LOADER
    assert "'mobile-project-card-compact.js'" in FEATURE_LOADER
    assert "'project-delete-ui.js'" in FEATURE_LOADER
    assert "feature === 'projects' && constrainedProjectsRuntime()" in FEATURE_LOADER
    assert "return files.filter(name => PROJECTS_LIGHT_FILES.has(name))" in FEATURE_LOADER

    light_block = FEATURE_LOADER.split("const PROJECTS_LIGHT_FILES", 1)[1].split("]);", 1)[0]
    assert "project-ships.js" not in light_block
    assert "product-delivery-ui.js" not in light_block
    assert "project-builder.js" not in light_block


def test_lazy_assets_use_their_own_server_revision():
    assert "window.__devpilotAssetRevisions = Object.freeze(assetRevisions)" in MAIN
    assert "name: _asset_revision(name)" in MAIN
    assert "const assetRevision = name" in FEATURE_LOADER
    assert "encodeURIComponent(assetRevision(name))" in FEATURE_LOADER
