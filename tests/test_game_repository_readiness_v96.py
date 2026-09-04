from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "app/static/game/runtime.js").read_text(encoding="utf-8")


def test_game_waits_for_repository_before_posting_task():
    assert "async function waitForRepositoryReady(projectId)" in RUNTIME
    assert "function taskProjectId(path, options = {})" in RUNTIME
    assert "if (projectId) await waitForRepositoryReady(projectId);" in RUNTIME


def test_repository_readiness_is_based_on_real_repository_url():
    readiness = RUNTIME.split("function repositoryReady(project)", 1)[1].split(
        "async function waitForRepositoryReady", 1
    )[0]
    assert "project?.repository_url" in readiness
    assert ".trim()" in readiness


def test_game_polls_lightweight_projects_endpoint_until_repository_exists():
    wait = RUNTIME.split("async function waitForRepositoryReady(projectId)", 1)[1].split(
        "async function api(path, options = {})", 1
    )[0]
    assert "/ui/projects?limit=50&include_project_id=" in wait
    assert "REPOSITORY_READY_WAIT_MS" in wait
    assert "REPOSITORY_READY_POLL_MS" in wait
    assert "repositoryReady(project)" in wait


def test_game_never_creates_task_after_repository_wait_timeout():
    wait = RUNTIME.split("async function waitForRepositoryReady(projectId)", 1)[1].split(
        "async function api(path, options = {})", 1
    )[0]
    assert "Nenhuma execução foi criada para evitar uma falha Git" in wait
    assert "throw new Error(" in wait


def test_task_post_still_uses_existing_api_only_after_guard():
    api_block = RUNTIME.split("async function api(path, options = {})", 1)[1].split(
        "function status(value)", 1
    )[0]
    guard_index = api_block.index("if (projectId) await waitForRepositoryReady(projectId);")
    request_index = api_block.index("const data = await requestJson(route.path, requestOptions);")
    assert guard_index < request_index
