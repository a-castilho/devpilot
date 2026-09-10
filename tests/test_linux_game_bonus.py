from pathlib import Path
from types import SimpleNamespace

from app.linux_routes import _linux_bonus_from_tasks
from app.security import Role


GAME_MARKER = "[DEVPILOT_BUILD_GAME_V1]"


def game_task(phase: int, status: str = "completed") -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        prompt=f"{GAME_MARKER}\nFASE: {phase}/7\nOBJETIVO: teste",
    )


def test_terminal_unlocks_after_game_security_milestone() -> None:
    locked = _linux_bonus_from_tasks(
        [game_task(1), game_task(2)],
        Role.ANALYST,
    )
    assert locked["eligible"] is True
    assert locked["unlocked"] is False
    assert locked["required_phases"] == [1, 2, 3]
    assert locked["required_xp"] == 420
    assert locked["earned_xp"] == 320

    unlocked = _linux_bonus_from_tasks(
        [game_task(1), game_task(2), game_task(3)],
        Role.ANALYST,
    )
    assert unlocked["unlocked"] is True
    assert unlocked["earned_xp"] == 420
    assert unlocked["scope"] == "own-isolated-workspace"


def test_failed_game_phase_does_not_unlock_terminal() -> None:
    bonus = _linux_bonus_from_tasks(
        [game_task(1), game_task(2), game_task(3, status="failed")],
        Role.OWNER,
    )
    assert bonus["unlocked"] is False
    assert bonus["completed_phases"] == [1, 2]


def test_seventh_game_phase_is_recognized_with_current_pipeline_contract() -> None:
    bonus = _linux_bonus_from_tasks(
        [game_task(1), game_task(2), game_task(3), game_task(7)],
        Role.OWNER,
    )
    assert bonus["unlocked"] is True
    assert bonus["completed_phases"] == [1, 2, 3, 7]
    assert bonus["earned_xp"] == 560


def test_legacy_six_phase_prompt_does_not_count_toward_current_bonus() -> None:
    legacy = SimpleNamespace(
        status="completed",
        prompt=f"{GAME_MARKER}\nFASE: 1/6\nOBJETIVO: legado",
    )
    bonus = _linux_bonus_from_tasks([legacy], Role.OWNER)
    assert bonus["completed_phases"] == []
    assert bonus["earned_xp"] == 0


def test_viewer_never_receives_executable_terminal() -> None:
    bonus = _linux_bonus_from_tasks(
        [game_task(1), game_task(2), game_task(3)],
        Role.VIEWER,
    )
    assert bonus["eligible"] is False
    assert bonus["unlocked"] is False
    assert "somente leitura" in bonus["message"].lower()


def test_super_admin_bypasses_game_and_has_all_sessions_scope() -> None:
    bonus = _linux_bonus_from_tasks([], Role.SUPER_ADMIN)
    assert bonus["unlocked"] is True
    assert bonus["source"] == "super-admin"
    assert bonus["scope"] == "all-devpilot-linux-sessions"


def test_linux_bonus_frontend_exposes_admin_controls_and_loader() -> None:
    ui = Path("app/static/linux-game-access.js").read_text(encoding="utf-8")
    coach = Path("app/static/linux-beginner-coach.js").read_text(encoding="utf-8")
    vercel = Path("tools/build-vercel-static.mjs").read_text(encoding="utf-8")

    assert "BÔNUS DO JOGO" in ui
    assert "Acesso total aos terminais DevPilot" in ui
    assert "/api/linux/terminal/sessions" in ui
    assert 'data-linux-admin-action="run"' in ui
    assert 'data-linux-admin-action="close"' in ui
    assert "/assets/linux-game-access.js?v=20260824-1" in coach
    assert "'linux-game-access.js'" in vercel
