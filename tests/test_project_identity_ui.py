from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEATURE_LOADER = ROOT / "app" / "static" / "feature-loader.js"
IDENTITY_UI = ROOT / "app" / "static" / "project-identity-ui.js"


def test_projects_navigation_loads_dedicated_visual_bundle():
    source = FEATURE_LOADER.read_text(encoding="utf-8")

    assert "projects: ['project-ships.js', 'project-delete-ui.js', 'system-tests.js', 'project-identity-ui.js', 'build-game-cockpit.js']" in source
    assert "['.nav[data-view=\"projects\"]', 'projects']" in source
    assert "['.nav[data-view=\"tasks\"]', 'tasks']" in source


def test_project_identity_supports_professional_and_game_skins():
    source = IDENTITY_UI.read_text(encoding="utf-8")

    assert "data-project-card-skin=\"professional\"" in source
    assert "data-project-card-skin=\"game\"" in source
    assert "▦ Profissional" in source
    assert "✦ Jogo" in source
    assert "project-ship-hangar" in source
    assert "project-logo-control" in source


def test_project_logo_editor_persists_inside_codex_config_without_replacing_other_keys():
    source = IDENTITY_UI.read_text(encoding="utf-8")

    assert "visual_identity" in source
    assert "const codexConfig = {...config, visual_identity:" in source
    assert "method: 'PATCH'" in source
    assert "image/png,image/jpeg,image/webp" in source
    assert "MAX_FILE_BYTES = 3 * 1024 * 1024" in source
    assert "https://" in source


def test_project_cards_have_responsive_breakpoints_and_non_stacked_actions():
    source = IDENTITY_UI.read_text(encoding="utf-8")

    assert "repeat(3, minmax(0, 1fr))" in source
    assert "repeat(2, minmax(0, 1fr))" in source
    assert "@media (max-width: 760px)" in source
    assert "grid-template-columns: minmax(0, 1fr) !important" in source
    assert "white-space: nowrap !important" in source
    assert "project-card-actions" in source
