from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"

RUNTIME = (STATIC / "runtime-experience-v13.js").read_text(encoding="utf-8")
TASK_MODAL = (STATIC / "task-modal.js").read_text(encoding="utf-8")
MOBILE_MENU = (STATIC / "mobile-accordion-menu.js").read_text(encoding="utf-8")


def test_runtime_is_loaded_from_real_boot_paths():
    marker = "/assets/runtime-experience-v13.js?v=20260830-direct-1"
    assert marker in TASK_MODAL
    assert marker in MOBILE_MENU


def test_details_have_one_capture_owner_and_hide_cleanly():
    assert "stopImmediatePropagation" in RUNTIME
    assert "dpV13Open" in RUNTIME
    assert "display', 'none', 'important'" in RUNTIME
    assert "O que fazer agora" in RUNTIME


def test_recommendations_are_prioritized_and_simplified():
    assert "extractRecommendations" in RUNTIME
    assert "simpleExplanation" in RUNTIME
    for priority in ("P0", "P1", "P2", "P3"):
        assert priority in RUNTIME
    assert "separação das partes" in RUNTIME


def test_project_selects_load_full_supported_page():
    assert "PROJECT_LIMIT = 100" in RUNTIME
    assert "/ui/projects?limit=${PROJECT_LIMIT}" in RUNTIME
    assert "Todos os projetos" in RUNTIME
    assert "#task-project" in RUNTIME
    assert "#tasks-v9-project" in RUNTIME


def test_mobile_smart_menu_is_contextual_and_full_width():
    assert "Recentes" in RUNTIME
    assert "Buscar tela ou função" in RUNTIME
    assert "Principal" in RUNTIME
    assert "Gestão" in RUNTIME
    assert "Super Admin" in RUNTIME
    assert "Ferramentas" in RUNTIME
    assert "width:100vw!important" in RUNTIME
    assert "mobile-smart-menu-recent-v13" in RUNTIME
