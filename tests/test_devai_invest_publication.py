from types import SimpleNamespace

from app.investia_models import InvestiaProjectStatus
from app.investia_public_routes import _accepting_investments, _publication_status


def config(*, public_enabled: bool, status: InvestiaProjectStatus):
    return SimpleNamespace(public_enabled=public_enabled, status=status)


def test_not_published_is_not_available_for_investment():
    item = config(public_enabled=False, status=InvestiaProjectStatus.fundraising)

    assert _publication_status(item) == "not_published"
    assert _accepting_investments(item) is False


def test_published_fundraising_project_accepts_investments():
    item = config(public_enabled=True, status=InvestiaProjectStatus.fundraising)

    assert _publication_status(item) == "published"
    assert _accepting_investments(item) is True


def test_paused_project_remains_published_but_blocks_new_investments():
    item = config(public_enabled=True, status=InvestiaProjectStatus.paused)

    assert _publication_status(item) == "paused"
    assert _accepting_investments(item) is False
