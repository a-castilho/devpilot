from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_user_v21_contract():
    runtime = (ROOT / 'app/static/dashboard-user-v21.js').read_text(encoding='utf-8')
    feature_loader = (ROOT / 'app/static/feature-loader.js').read_text(encoding='utf-8')

    assert '__devpilotDashboardUserV21' in runtime
    assert 'CENTRAL OPERACIONAL' in runtime
    assert 'O que está acontecendo neste momento.' in runtime
    assert 'Últimas execuções' in runtime
    assert "#overview-view" in runtime
    assert "#metrics" in runtime

    # O dashboard V21 hoje é carregado pelo feature-loader central. O contrato
    # antigo que procurava loadDashboardUserV21 em viewport-adaptive-v15.js não
    # representa mais a arquitetura real e gerava falso negativo no teste local.
    assert "shellCommon" in feature_loader
    assert "'dashboard-user-v21.js'" in feature_loader

    # O painel operacional deve usar uma única população para todos os números.
    # A API /overview continua válida para projetos, mas totais históricos de
    # tarefas não podem ser misturados com o recorte recente da /ui/tasks.
    assert 'function recentSnapshot()' in runtime
    assert 'state.tasks.slice(0, 20)' in runtime
    assert "completed: count(['completed', 'done'])" in runtime
    assert "failed: count(['failed', 'error', 'blocked'])" in runtime
    assert 'Os números históricos não são misturados com este painel.' in runtime
    assert 'O painel não soma falhas antigas ou conclusões históricas' in runtime
    assert 'overview.completed' not in runtime


if __name__ == '__main__':
    test_dashboard_user_v21_contract()
    print('DASHBOARD USER V21: contrato OK')
