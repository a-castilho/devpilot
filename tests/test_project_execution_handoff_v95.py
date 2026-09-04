from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = (ROOT / "app/static/project-builder.js").read_text(encoding="utf-8")


def test_new_project_hands_off_to_game_with_created_project_selected():
    assert "const GAME_PROJECT_KEY = 'devpilot-build-game-project'" in BUILDER
    assert "const GAME_DRAFT_PROJECT_KEY = 'devpilot-game-v74-project'" in BUILDER
    assert "const GAME_URL = '/game/index.html'" in BUILDER
    assert "localStorage.setItem(GAME_PROJECT_KEY, id)" in BUILDER
    assert "localStorage.setItem(GAME_DRAFT_PROJECT_KEY, id)" in BUILDER
    assert "window.location.assign(GAME_URL)" in BUILDER


def test_handoff_starts_a_clean_delivery_instead_of_reusing_old_game_state():
    handoff = BUILDER.split("function handoffToFirstExecution(project)", 1)[1].split(
        "async function request", 1
    )[0]

    assert "localStorage.removeItem(GAME_MISSION_KEY)" in handoff
    assert "localStorage.removeItem(GAME_DRAFT_GOAL_KEY)" in handoff


def test_project_creation_does_not_fabricate_an_execution_without_delivery():
    success = BUILDER.split("const project = await request(endpoint", 1)[1].split(
        "} catch (error)", 1
    )[0]

    assert "handoffToFirstExecution(project)" in success
    assert "request('/tasks'" not in success
    assert 'request("/tasks"' not in success


def test_project_registration_contract_remains_non_blocking():
    assert "repositoryUrl ? '/projects' : '/projects/provision'" in BUILDER
    assert "void Promise.resolve(window.loadProjects())" in BUILDER
    assert "handoffToFirstExecution(project)" in BUILDER
