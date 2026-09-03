from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEWPORT = (ROOT / "app/static/viewport-adaptive-v15.js").read_text(encoding="utf-8")
LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")


def test_legacy_window_owner_was_removed_from_new_project() -> None:
    assert "[data-project-builder-open]" not in VIEWPORT
    assert "openProjectBuilderSafe" not in VIEWPORT
    assert "__devpilotTaskActionSafeOpenV41" in VIEWPORT


def test_feature_loader_is_the_canonical_new_project_owner() -> None:
    assert "async function openProjectBuilderDirect" in LOADER
    assert "target.closest('[data-project-builder-open]')" in LOADER
    assert "showProjectBuilderImmediately();" in LOADER


def test_canonical_owner_opens_before_loading_builder() -> None:
    block = LOADER.split("async function openProjectBuilderDirect", 1)[1].split(
        "async function analyzeProjectDirect", 1
    )[0]
    assert block.index("showProjectBuilderImmediately();") < block.index("await loadFeature('projectBuilder')")
