from pathlib import Path


SOURCE = Path("app/static/provider-models.js")


def test_provider_ui_normalizes_legacy_models_before_rendering():
    source = SOURCE.read_text(encoding="utf-8")

    assert "function arrayValue(value)" in source
    assert "function modelIds(value)" in source
    assert "function modelObjects(value)" in source
    assert "connections=arrayValue(c).map(normalizeConnection).filter(Boolean);" in source
    assert "catalog={...normalizeCatalog(k?.providers),...refreshed};" in source


def test_provider_ui_accepts_json_and_comma_separated_legacy_values():
    source = SOURCE.read_text(encoding="utf-8")

    assert "const parsed=JSON.parse(text);" in source
    assert "return text.split(',').map(item=>item.trim()).filter(Boolean);" in source
    assert "const models=modelIds(x.models);" in source
    assert "const ms=modelIds(value);" in source


def test_provider_editor_normalizes_api_model_shapes():
    source = SOURCE.read_text(encoding="utf-8")

    assert "editor.available=modelObjects(data?.models);" in source
    assert "editor.recommended=modelObjects(data?.recommended_models);" in source
    assert "editor.selected=new Set(modelIds(data?.selected_models).length?" in source
