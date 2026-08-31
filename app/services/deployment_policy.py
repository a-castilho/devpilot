from __future__ import annotations

from dataclasses import dataclass

from app.security import MANAGEMENT_ROLES, Role


PRODUCTION_ENVIRONMENTS = {"prod", "production", "producao", "produção"}


@dataclass(frozen=True)
class DeploymentDecision:
    allowed: bool
    risk: int
    reason: str
    requires_explicit_approval: bool


def normalize_environment(value: str) -> str:
    return str(value or "").strip().lower()


def deployment_risk(environment: str) -> int:
    """Map deploys to the same R4/R5 scale used by the Quest engine."""
    return 5 if normalize_environment(environment) in PRODUCTION_ENVIRONMENTS else 4


def evaluate_deployment(
    role: Role,
    environment: str,
    *,
    explicitly_approved: bool = False,
) -> DeploymentDecision:
    risk = deployment_risk(environment)
    if role not in MANAGEMENT_ROLES:
        return DeploymentDecision(
            allowed=False,
            risk=risk,
            reason="Perfil sem permissão para infraestrutura/deploy",
            requires_explicit_approval=risk >= 5,
        )

    if risk >= 5 and not explicitly_approved:
        return DeploymentDecision(
            allowed=False,
            risk=risk,
            reason="Deploy de produção exige autorização explícita registrada",
            requires_explicit_approval=True,
        )

    return DeploymentDecision(
        allowed=True,
        risk=risk,
        reason="Deploy autorizado pela política R4/R5",
        requires_explicit_approval=risk >= 5,
    )
