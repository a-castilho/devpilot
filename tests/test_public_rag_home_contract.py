from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_prelogin_home_exposes_public_search_and_login_entrypoint():
    source = (ROOT / "app" / "static" / "auth-ui.js").read_text(encoding="utf-8")

    assert "function renderPublicHome" in source
    assert "Conhecimento vivo dos projetos" in source
    assert "/api/investia/catalog/search" in source
    assert 'id="public-login"' in source
    assert "renderLoginForm" in source


def test_public_search_only_uses_explicitly_published_projects():
    source = (ROOT / "app" / "investia_public_routes.py").read_text(encoding="utf-8")

    assert '@router.get("/catalog/search")' in source
    assert "InvestiaProjectConfig.public_enabled.is_(True)" in source
    assert "get_rag_service" in source
    assert "rag.retrieve(" in source
    assert "project.organization_id" in source


def test_public_search_degrades_without_rag():
    source = (ROOT / "app" / "investia_public_routes.py").read_text(encoding="utf-8")

    assert '"rag_available": rag_available' in source
    assert '"match": "rag" if excerpts else "metadata"' in source
    assert "except Exception" in source
