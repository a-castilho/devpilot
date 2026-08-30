from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_user_v20_contract():
    css = (ROOT / "app/static/dashboard-user-v20.css").read_text(encoding="utf-8")
    viewport = (ROOT / "app/static/viewport-adaptive-v15.js").read_text(encoding="utf-8")
    app = (ROOT / "app/static/app.js").read_text(encoding="utf-8")

    # Existing real-data dashboard contract.
    assert "function renderOverview(overview)" in app
    assert "overview.projects" in app
    assert "overview.active" in app
    assert "overview.completed" in app
    assert "groups.approvals" in app
    assert "groups.failed" in app
    assert "#recent-tasks" not in app  # selector is accessed through $('#recent-tasks')
    assert "$('#recent-tasks')" in app

    # V20 must be visual only: no API calls or fake datasets.
    assert "fetch(" not in css
    assert "/api/" not in css
    assert "dashboard-user-v20.css" in viewport
    assert "data-dashboard-user-v20" in viewport

    # Responsive operational hierarchy.
    assert "#overview-view .command-center" in css
    assert "#overview-view .overview-metrics" in css
    assert "#overview-view .operations-strip" in css
    assert "#overview-view .overview-grid" in css
    assert "#overview-view .recent-task" in css
    assert "@container dp-dashboard" in css
    assert "@media (max-width: 900px)" in css


if __name__ == "__main__":
    test_dashboard_user_v20_contract()
    print("DASHBOARD V20: contrato OK")
