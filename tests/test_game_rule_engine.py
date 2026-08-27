from __future__ import annotations

import pytest

from app.game_rule_engine import RuleSpec, evaluate_rules, validate_actions, validate_conditions


def rule(*, key="security-reward", event_type="task.completed", priority=100, conditions=None, actions=None):
    return RuleSpec(
        id=f"rule-{key}",
        rule_key=key,
        version=1,
        event_type=event_type,
        priority=priority,
        conditions=conditions or [],
        actions=actions or [{"type": "award_xp", "amount": 5}],
    )


def test_rule_engine_matches_nested_event_and_returns_declarative_actions():
    result = evaluate_rules(
        [rule(conditions=[{"field": "task.category", "operator": "eq", "value": "security"}])],
        "task.completed",
        {"task": {"category": "security", "status": "completed"}},
    )

    assert result["matched_rules"] == [{"id": "rule-security-reward", "rule_key": "security-reward", "version": 1}]
    assert result["actions"][0]["type"] == "award_xp"
    assert result["actions"][0]["amount"] == 5
    assert result["actions"][0]["rule_key"] == "security-reward"


def test_rule_engine_ignores_other_events_and_orders_by_priority():
    result = evaluate_rules(
        [rule(key="later", priority=200), rule(key="first", priority=10), rule(key="other", event_type="mission.accepted")],
        "task.completed",
        {},
    )
    assert [item["rule_key"] for item in result["matched_rules"]] == ["first", "later"]


def test_rule_language_rejects_arbitrary_operators_and_actions():
    with pytest.raises(ValueError, match="Operador não permitido"):
        validate_conditions([{"field": "task.status", "operator": "eval", "value": "completed"}])

    with pytest.raises(ValueError, match="Ação não permitida"):
        validate_actions([{"type": "run_shell", "command": "rm -rf /"}])


def test_rule_language_bounds_reward_values():
    with pytest.raises(ValueError, match="fora do limite"):
        validate_actions([{"type": "award_xp", "amount": 1000001}])

    assert validate_actions([{"type": "award_xp", "amount": 100}]) == [{"type": "award_xp", "amount": 100}]
