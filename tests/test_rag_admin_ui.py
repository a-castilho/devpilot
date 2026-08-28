from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_rag_admin_ui_is_lazy_loaded_with_super_admin_bundle():
    loader = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")
    assert "rag-admin-ui.js" in loader
    assert "admin:" in loader


def test_rag_admin_ui_uses_super_admin_rag_endpoints():
    ui = (ROOT / "app/static/rag-admin-ui.js").read_text(encoding="utf-8")
    assert "/super-admin/rag/overview" in ui
    assert "/super-admin/rag/settings" in ui
    assert "/super-admin/rag/health" in ui
    assert "/super-admin/rag/projects/" in ui
    assert "RAG / Conhecimento" in ui


def test_rag_admin_ui_has_visual_monitoring_charts_and_fail_open_loading():
    ui = (ROOT / "app/static/rag-admin-ui.js").read_text(encoding="utf-8")
    assert "rag-chart-grid" in ui
    assert "rag-bar" in ui
    assert "Cobertura dos projetos" in ui
    assert "Saúde das dependências" in ui
    assert "Recursos habilitados" in ui
    assert "Promise.allSettled" in ui
    assert "Carregamento parcial" in ui
