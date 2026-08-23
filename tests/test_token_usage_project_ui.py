from pathlib import Path


TOKEN_USAGE_JS = Path("app/static/token-usage.js")


def test_recent_token_usage_resolves_and_displays_project_name():
    source = TOKEN_USAGE_JS.read_text(encoding="utf-8")

    assert "costData.by_project" in source
    assert "new Map(" in source
    assert "projectNames.get(String(item.project_id))" in source
    assert "Projeto não identificado" in source
    assert "Sem projeto" in source
    assert "Sistema / legado')} · ${esc(item.operation)" in source
