from pathlib import Path


SOURCE = Path("app/static/build-game-cockpit.js")


def test_linux_currency_is_earned_from_real_completed_xp():
    source = SOURCE.read_text(encoding="utf-8")

    assert "LINUX_INFRA_COST = 50" in source
    assert "Math.floor(xp / 10)" in source
    assert "Cada 10 XP concluídos valem 1 Linux" in source
    assert "Moeda de infraestrutura".upper() in source.upper()


def test_dedicated_linux_infra_is_isolated_and_not_duplicated():
    source = SOURCE.read_text(encoding="utf-8")

    assert "[DEVPILOT_GAME_LINUX_INFRA_V1]" in source
    assert "economy.active || economy.ready" in source
    assert "sem --privileged" in source
    assert "sem montar docker.sock" in source
    assert "isolada por tenant e projeto" in source
    assert "SUPER_ADMIN pode auditar/administrar" in source
    assert "não crie infraestrutura duplicada" in source


def test_failed_infra_request_refunds_linux_balance():
    source = SOURCE.read_text(encoding="utf-8")

    assert "REFUND_TASK_STATUSES = new Set(['failed', 'cancelled'])" in source
    assert "Tentativa anterior falhou · Linux devolvido" in source
