from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
FEATURE_LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")
BUILDER = (ROOT / "app/static/project-builder.js").read_text(encoding="utf-8")


def test_project_builder_critical_bundle_contains_only_essential_runtime() -> None:
    block = FEATURE_LOADER.split("projectBuilder: [", 1)[1].split("],", 1)[0]
    assert "'project-provisioning.js'" in block
    assert "'project-builder.js'" in block
    assert "project-description-profile.js" not in block
    assert "mobile-project-card-compact.js" not in block


def test_project_builder_enhancement_is_not_automatically_scheduled() -> None:
    assert "projectBuilderEnhancements" in FEATURE_LOADER
    assert "loadFeature('projectBuilderEnhancements')" not in FEATURE_LOADER
    assert "requestIdleCallback" not in FEATURE_LOADER


def test_project_builder_changes_view_before_waiting_for_network_or_bundles() -> None:
    block = FEATURE_LOADER.split("async function openProjectBuilderDirect", 1)[1].split(
        "async function analyzeProjectDirect", 1
    )[0]
    assert block.index("showProjectBuilderImmediately();") < block.index("await loadFeature('projectBuilder')")
    assert "organizationsPromise = Promise.resolve(loadOrganizations())" in block
    assert "void organizationsPromise.then(() => hydrateBuilderOrganizations(admin));" in block


def test_builder_initialization_has_bounded_synchronous_work() -> None:
    assert "__devpilotProjectBuilderV94" in BUILDER
    assert "host.addEventListener('click'" in BUILDER
    assert "requestAnimationFrame(updateSummary)" in BUILDER
    assert "details?.open" in BUILDER
    assert "MutationObserver" not in BUILDER
    assert "setInterval" not in BUILDER


def test_frontend_javascript_syntax() -> None:
    for path in (
        ROOT / "app/static/feature-loader.js",
        ROOT / "app/static/project-builder.js",
        ROOT / "app/static/viewport-adaptive-v15.js",
    ):
        subprocess.run(
            ["node", "--check", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
