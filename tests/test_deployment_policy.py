from app.security import Role
from app.services.deployment_policy import deployment_risk, evaluate_deployment


def test_homolog_deploy_is_r4_and_management_can_execute():
    assert deployment_risk("homolog") == 4

    for role in (Role.SUPER_ADMIN, Role.OWNER, Role.ADMIN):
        decision = evaluate_deployment(role, "homolog")
        assert decision.allowed is True
        assert decision.risk == 4
        assert decision.requires_explicit_approval is False


def test_non_management_cannot_execute_r4_deploy():
    for role in (Role.ANALYST, Role.VIEWER):
        decision = evaluate_deployment(role, "homolog")
        assert decision.allowed is False
        assert decision.risk == 4


def test_production_is_r5_and_requires_explicit_approval():
    assert deployment_risk("production") == 5
    assert deployment_risk("produção") == 5

    blocked = evaluate_deployment(Role.SUPER_ADMIN, "production")
    assert blocked.allowed is False
    assert blocked.requires_explicit_approval is True
    assert "autorização explícita" in blocked.reason

    approved = evaluate_deployment(
        Role.SUPER_ADMIN,
        "production",
        explicitly_approved=True,
    )
    assert approved.allowed is True
    assert approved.risk == 5


def test_explicit_approval_does_not_bypass_role_policy():
    decision = evaluate_deployment(
        Role.VIEWER,
        "production",
        explicitly_approved=True,
    )
    assert decision.allowed is False
    assert decision.risk == 5
