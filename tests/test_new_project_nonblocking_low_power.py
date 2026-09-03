from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")
MOBILE = (ROOT / "app/static/mobile-project-card-compact.js").read_text(encoding="utf-8")
BUILDER = (ROOT / "app/static/project-builder.js").read_text(encoding="utf-8")


def test_low_power_runtime_does_not_own_new_project_navigation() -> None:
    assert "[data-project-builder-open]" not in MOBILE
    assert "openBuilderLowPower" not in MOBILE
    assert "BUILDER_OPEN_FLAG" not in MOBILE


def test_new_project_opens_before_bundle_even_on_constrained_runtime() -> None:
    block = LOADER.split("async function openProjectBuilderDirect", 1)[1].split(
        "async function analyzeProjectDirect", 1
    )[0]
    assert block.index("showProjectBuilderImmediately();") < block.index("await loadFeature('projectBuilder')")
    assert "organizationsPromise = Promise.resolve(loadOrganizations())" in block


def test_builder_has_no_polling_or_global_observer() -> None:
    assert "__devpilotProjectBuilderV94" in BUILDER
    assert "setInterval" not in BUILDER
    assert "MutationObserver" not in BUILDER
    assert "requestAnimationFrame(updateSummary)" in BUILDER
