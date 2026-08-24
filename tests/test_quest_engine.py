from types import SimpleNamespace

from app.models import TaskStatus
from app.security import Role
from app.services.quest_engine import (
    classify_task_risk,
    level_from_xp,
    rank_for_level,
    reward_for,
    role_can_accept,
    validate_real_task,
)


def task(**overrides):
    values = {
        "title": "Corrigir validação",
        "prompt": "Ajustar teste de unidade",
        "requires_approval": False,
        "approved_at": None,
        "status": TaskStatus.queued,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_risk_classification_prioritizes_privileged_operations():
    assert classify_task_risk(task(prompt="usar sudo para corrigir produção")) == 5
    assert classify_task_risk(task(prompt="corrigir deploy docker")) == 4
    assert classify_task_risk(task(prompt="refactor architecture")) == 3
    assert classify_task_risk(task(requires_approval=True)) == 2
    assert classify_task_risk(task()) == 1


def test_high_risk_requires_management_role():
    assert role_can_accept(Role.ANALYST, 2) is True
    assert role_can_accept(Role.ANALYST, 4) is False
    assert role_can_accept(Role.ADMIN, 5) is True
    assert role_can_accept(Role.VIEWER, 1) is False


def test_completion_requires_real_completed_task_and_approval_when_needed():
    ok, _ = validate_real_task(task(status=TaskStatus.queued), 1)
    assert ok is False

    ok, _ = validate_real_task(task(status=TaskStatus.completed, requires_approval=True), 3)
    assert ok is False

    ok, _ = validate_real_task(
        task(status=TaskStatus.completed, requires_approval=True, approved_at=object()),
        3,
    )
    assert ok is True


def test_rewards_scale_with_risk_and_never_grant_permissions():
    low = reward_for(1, 1)
    high = reward_for(5, 5)
    assert high.xp > low.xp
    assert high.moons >= low.moons
    assert high.swords > low.swords
    # RBAC is intentionally absent from Reward: game progression cannot elevate privileges.
    assert not hasattr(high, "role")


def test_progression_has_bounded_levels_and_named_ranks():
    assert level_from_xp(0) == 1
    assert level_from_xp(10_000_000) == 50
    assert rank_for_level(1) == "Observador"
    assert rank_for_level(50) == "System Administrator"
