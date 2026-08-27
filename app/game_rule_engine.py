from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


ALLOWED_OPERATORS = {"eq", "neq", "in", "not_in", "gte", "lte", "contains", "exists"}
ALLOWED_ACTIONS = {"award_xp", "award_currency", "unlock_phase", "set_flag", "emit_event"}


@dataclass(frozen=True)
class RuleSpec:
    id: str
    rule_key: str
    version: int
    event_type: str
    priority: int
    conditions: list[dict[str, Any]]
    actions: list[dict[str, Any]]


def _resolve(payload: dict[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = payload
    for part in str(path).split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def validate_conditions(conditions: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in conditions:
        if not isinstance(raw, dict):
            raise ValueError("Cada condição deve ser um objeto")
        field = str(raw.get("field") or "").strip()
        operator = str(raw.get("operator") or "eq").strip()
        if not field:
            raise ValueError("Condição sem campo")
        if operator not in ALLOWED_OPERATORS:
            raise ValueError(f"Operador não permitido: {operator}")
        normalized.append({"field": field, "operator": operator, "value": raw.get("value")})
    return normalized


def validate_actions(actions: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in actions:
        if not isinstance(raw, dict):
            raise ValueError("Cada ação deve ser um objeto")
        action_type = str(raw.get("type") or "").strip()
        if action_type not in ALLOWED_ACTIONS:
            raise ValueError(f"Ação não permitida: {action_type}")
        item = dict(raw)
        item["type"] = action_type
        if action_type in {"award_xp", "award_currency"}:
            amount = int(item.get("amount") or 0)
            if amount <= 0 or amount > 1_000_000:
                raise ValueError("Valor de recompensa fora do limite")
            item["amount"] = amount
        elif action_type == "unlock_phase":
            phase = int(item.get("phase") or 0)
            if phase <= 0 or phase > 1000:
                raise ValueError("Fase inválida")
            item["phase"] = phase
        elif action_type == "set_flag":
            key = str(item.get("key") or "").strip()
            if not key:
                raise ValueError("Flag sem chave")
            item["key"] = key
        elif action_type == "emit_event":
            event_type = str(item.get("event_type") or "").strip()
            if not event_type:
                raise ValueError("Evento de saída sem tipo")
            item["event_type"] = event_type
        normalized.append(item)
    if not normalized:
        raise ValueError("A regra precisa de pelo menos uma ação")
    return normalized


def condition_matches(condition: dict[str, Any], event: dict[str, Any]) -> bool:
    exists, actual = _resolve(event, condition["field"])
    operator = condition["operator"]
    expected = condition.get("value")
    if operator == "exists":
        return exists is bool(expected if expected is not None else True)
    if not exists:
        return False
    if operator == "eq":
        return actual == expected
    if operator == "neq":
        return actual != expected
    if operator == "in":
        return isinstance(expected, (list, tuple, set)) and actual in expected
    if operator == "not_in":
        return isinstance(expected, (list, tuple, set)) and actual not in expected
    if operator == "gte":
        try:
            return actual >= expected
        except TypeError:
            return False
    if operator == "lte":
        try:
            return actual <= expected
        except TypeError:
            return False
    if operator == "contains":
        try:
            return expected in actual
        except (TypeError, ValueError):
            return False
    return False


def evaluate_rules(rules: Iterable[RuleSpec], event_type: str, event: dict[str, Any]) -> dict[str, Any]:
    matched: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    for rule in sorted(rules, key=lambda item: (item.priority, item.rule_key, -item.version)):
        if rule.event_type != event_type:
            continue
        if not all(condition_matches(condition, event) for condition in rule.conditions):
            continue
        matched.append({"id": rule.id, "rule_key": rule.rule_key, "version": rule.version})
        for action in rule.actions:
            actions.append({**action, "rule_id": rule.id, "rule_key": rule.rule_key, "rule_version": rule.version})
    return {"event_type": event_type, "matched_rules": matched, "actions": actions}
