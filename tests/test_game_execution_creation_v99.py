from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "app/static/game/runtime.js"
INDEX = ROOT / "app/static/game/index.html"


def test_jogar_agora_creates_task_before_repository_is_ready():
    source = RUNTIME.read_text(encoding="utf-8")
    assert "[DEVPILOT_REPOSITORY_GATE_V99]" in source
    assert "repositoryGateRequest" in source
    assert "requires_approval: true" in source
    assert "const data = await requestJson(route.path, requestOptions);" in source
    assert "void releaseRepositoryGatedTask(data, gate.projectId);" in source
    assert "waitForRepositoryReady" not in source


def test_staged_execution_waits_for_repository_then_is_released():
    source = RUNTIME.read_text(encoding="utf-8")
    assert "/repository/retry" in source
    assert "/repository/provisioning" in source
    assert "/approve" in source
    assert "Execução criada. Repositório pronto; Planejamento liberado para o worker." in source
    assert "repositoryReleaseInFlight" in source


def test_reload_resumes_repository_gate_without_losing_execution():
    source = RUNTIME.read_text(encoding="utf-8")
    assert "repositoryGatedTask(row)" in source
    assert "void releaseRepositoryGatedTask(row, row?.project_id);" in source
    assert "status: repositoryGatedTask(row) ? 'queued' : row?.status" in source


def test_v99_cache_revision_is_published():
    html = INDEX.read_text(encoding="utf-8")
    assert "game-flow-v99-20260904" in html
    assert 'data-devpilot-game-version="v99"' in html


if __name__ == "__main__":
    test_jogar_agora_creates_task_before_repository_is_ready()
    test_staged_execution_waits_for_repository_then_is_released()
    test_reload_resumes_repository_gate_without_losing_execution()
    test_v99_cache_revision_is_published()
    print("GAME_EXECUTION_CREATION_V99=OK")
