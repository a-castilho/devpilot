from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_new_project_has_one_navigation_owner() -> None:
    feature_loader = read("feature-loader.js")
    viewport = read("viewport-adaptive-v15.js")
    builder = read("project-builder.js")

    assert "async function openProjectBuilderDirect" in feature_loader
    assert "showProjectBuilderImmediately();" in feature_loader
    assert "target.closest('[data-project-builder-open]')" in feature_loader
    assert "[data-project-builder-open]" not in viewport
    assert "[data-project-builder-open]" not in builder


def test_feature_loader_has_one_global_publisher() -> None:
    owners = []
    marker = "window.__devpilotLoadFeature = loadFeature"
    for path in sorted(STATIC.glob("*.js")):
        if marker in path.read_text(encoding="utf-8"):
            owners.append(path.name)

    assert owners == ["feature-loader.js"]


def test_project_builder_uses_bounded_event_topology() -> None:
    source = read("project-builder.js")

    assert "__devpilotProjectBuilderV94" in source
    assert "host.addEventListener('click'" in source
    assert "host.addEventListener('pointerdown'" in source
    assert "host.querySelectorAll('.choice-card[data-group][data-option]').forEach" in source
    assert ".choice-card').forEach(button => {\n      button.addEventListener('click'" not in source
    assert "MutationObserver" not in source
    assert "setInterval" not in source


def test_project_builder_defers_expensive_preview_and_records_timings() -> None:
    source = read("project-builder.js")

    assert "requestAnimationFrame(updateSummary)" in source
    assert "details?.open" in source
    assert "__devpilotFrontendDiagnostics" in source
    assert "recordDiagnostic('render-groups'" in source
    assert "recordDiagnostic('builder-init'" in source
    assert "durationMs >= 50" in source


def test_builder_categories_are_layout_isolated() -> None:
    source = read("page-navigation-v26.css")

    assert "#new-project-view .builder-group" in source
    assert "content-visibility: auto" in source
    assert "contain-intrinsic-size: 190px" in source
    assert "contain: layout style paint" in source


def test_workspace_skins_is_presentation_only() -> None:
    source = read("workspace-skins.js")

    assert "__devpilotWorkspaceSkinsV94" in source
    assert "FEATURE_BUNDLES" not in source
    assert "window.__devpilotLoadFeature" not in source
    assert "createElement('script')" not in source
    assert "body.appendChild =" not in source
    assert "MutationObserver" not in source


def test_game_ships_cannot_inject_or_touch_builder_runtime() -> None:
    source = read("mobile-game-ships-stable.js")

    assert "__devpilotMobileGameShipsStableV94" in source
    assert "project-builder-mobile-runtime-v39.js" not in source
    assert "ensureBuilderRuntime" not in source
    assert "project-builder-groups" not in source
    assert "document.createElement('script')" not in source


def test_changed_frontend_javascript_has_valid_syntax() -> None:
    for name in (
        "project-builder.js",
        "viewport-adaptive-v15.js",
        "workspace-skins.js",
        "mobile-game-ships-stable.js",
    ):
        subprocess.run(
            ["node", "--check", str(STATIC / name)],
            check=True,
            capture_output=True,
            text=True,
        )
