import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.frontend_ui_routes import ProjectVisualIdentityUpdate, _visual_identity


ROOT = Path(__file__).resolve().parents[1]
FEATURE_LOADER = ROOT / "app" / "static" / "feature-loader.js"
IDENTITY_UI = ROOT / "app" / "static" / "project-identity-ui.js"
UI_ROUTES = ROOT / "app" / "frontend_ui_routes.py"


def test_projects_navigation_loads_explicit_visual_bundle_without_legacy_observer_ship_module():
    source = FEATURE_LOADER.read_text(encoding="utf-8")

    assert "projects: ['project-delete-ui.js', 'system-tests.js', 'project-identity-ui.js', 'build-game-cockpit.js']" in source
    assert "projects: ['project-ships.js'" not in source
    assert "['.nav[data-view=\"projects\"]', 'projects']" in source
    assert "['.nav[data-view=\"tasks\"]', 'tasks']" in source


def test_project_identity_supports_professional_and_game_skins_with_owned_ship():
    source = IDENTITY_UI.read_text(encoding="utf-8")

    assert "data-project-card-skin=\"professional\"" in source
    assert "data-project-card-skin=\"game\"" in source
    assert "▦ Profissional" in source
    assert "✦ Jogo" in source
    assert "project-ship-hangar" in source
    assert "NAVE DO PROJETO" in source
    assert "<svg class=\"project-ship\"" in source
    assert "project-logo-control" in source


def test_project_logo_editor_uses_bounded_identity_contract_instead_of_full_project_list():
    source = IDENTITY_UI.read_text(encoding="utf-8")

    assert "/ui/project-identities?ids=" in source
    assert "/ui/projects/${encodeURIComponent(operation.id)}/visual-identity" in source
    assert "method: 'PATCH'" in source
    assert "image/png,image/jpeg,image/webp" in source
    assert "MAX_FILE_BYTES = 3 * 1024 * 1024" in source
    assert "apiRequest('/projects')" not in source
    assert "fullProjects" not in source


def test_project_identity_api_preserves_other_codex_config_and_serializes_only_identity():
    source = UI_ROUTES.read_text(encoding="utf-8")

    assert '@router.get("/project-identities")' in source
    assert '@router.patch("/projects/{project_id}/visual-identity")' in source
    assert "Project.id, Project.codex_config" in source
    assert "_MAX_VISUAL_IDENTITY_PROJECTS = 50" in source
    assert ".with_for_update()" in source
    assert 'config["visual_identity"] = identity' in source
    assert 'action="project.visual_identity_updated"' in source


def test_project_visual_identity_parser_keeps_small_valid_identity_only():
    raw = json.dumps(
        {
            "provider": {"model": "unchanged"},
            "visual_identity": {
                "logo": "https://example.com/logo.png",
                "accent": "#12AbEf",
                "updated_at": "2026-08-29T22:00:00+00:00",
            },
        }
    )

    identity = _visual_identity(raw)

    assert identity == {
        "logo": "https://example.com/logo.png",
        "accent": "#12AbEf",
        "updated_at": "2026-08-29T22:00:00+00:00",
    }


def test_project_visual_identity_input_rejects_unsafe_logo_sources():
    with pytest.raises(ValidationError):
        ProjectVisualIdentityUpdate(logo="javascript:alert(1)", accent="#112233")

    assert ProjectVisualIdentityUpdate(
        logo="data:image/webp;base64,AAAA",
        accent="#112233",
    ).logo.startswith("data:image/webp;base64,")


def test_project_cards_have_responsive_breakpoints_and_non_stacked_actions():
    source = IDENTITY_UI.read_text(encoding="utf-8")

    assert "repeat(3,minmax(0,1fr))" in source
    assert "repeat(2,minmax(0,1fr))" in source
    assert "@media (max-width:760px)" in source
    assert "grid-template-columns:minmax(0,1fr)!important" in source
    assert "white-space:nowrap!important" in source
    assert "project-card-actions" in source


def test_project_identity_respects_frontend_boot_policy_and_has_no_global_observer():
    source = IDENTITY_UI.read_text(encoding="utf-8")

    assert "new MutationObserver" not in source
    assert "createElement('script')" not in source
    assert 'createElement("script")' not in source
    assert "wrapProjectRenderer" in source


def test_slow_identity_save_captures_editor_before_awaiting_request():
    source = IDENTITY_UI.read_text(encoding="utf-8")

    operation_index = source.index("const operation = {id: editor.id, card: editor.card, name: editor.name};")
    request_index = source.index("await apiRequest(`/ui/projects/${encodeURIComponent(operation.id)}/visual-identity`")
    assert operation_index < request_index
    assert "if (editor?.id === operation.id)" in source
    assert "setDialogBusy(dialog, true)" in source
