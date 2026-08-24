from pathlib import Path

from app.main import spa


HOTFIX = Path("app/static/token-usage-mobile-fix.js")


def test_token_usage_mobile_fix_is_loaded_with_cache_busting():
    rendered = spa("mobile").body.decode("utf-8")

    assert "/assets/token-usage-mobile-fix.js?v=" in rendered


def test_budget_zero_values_are_validated_before_request():
    source = HOTFIX.read_text(encoding="utf-8")

    assert "daily > 0 || monthly > 0" in source
    assert "Informe um limite diário ou mensal" in source
    assert "stopImmediatePropagation" in source


def test_mobile_cost_table_is_rendered_without_horizontal_crop():
    source = HOTFIX.read_text(encoding="utf-8")

    assert ".token-cost-grid .token-admin-table thead{display:none}" in source
    assert "grid-template-columns:minmax(0,1fr) auto" in source
    assert "Sem preço:" in source


def test_api_errors_keep_http_status_instead_of_generic_failure():
    source = HOTFIX.read_text(encoding="utf-8")

    assert "Falha na operação (HTTP ${status})" in source
    assert "Sem conexão com o DevPilot" in source
    assert "normalizeErrorDetail" in source