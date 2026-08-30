from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_user_v21_contract():
    runtime = (ROOT / 'app/static/dashboard-user-v21.js').read_text(encoding='utf-8')
    viewport = (ROOT / 'app/static/viewport-adaptive-v15.js').read_text(encoding='utf-8')

    assert '__devpilotDashboardUserV21' in runtime
    assert 'CENTRAL OPERACIONAL' in runtime
    assert 'O que está acontecendo neste momento.' in runtime
    assert 'Últimas execuções' in runtime
    assert "#overview-view" in runtime
    assert "#metrics" in runtime
    assert "dashboard-user-v21.js" in viewport
    assert 'loadDashboardUserV21' in viewport


if __name__ == '__main__':
    test_dashboard_user_v21_contract()
    print('DASHBOARD USER V21: contrato OK')
