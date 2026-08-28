from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPAIR = ROOT / "app" / "static" / "build-game-repair-mission.js"
LOADER = ROOT / "app" / "static" / "feature-loader.js"
GAME_HTML = ROOT / "app" / "static" / "game" / "index.html"


def test_repair_mission_is_not_owned_by_dashboard_feature_loader():
    loader = LOADER.read_text(encoding="utf-8")
    game_html = GAME_HTML.read_text(encoding="utf-8")

    assert "build-game-repair-mission.js" not in loader
    assert "gameAdvanced:" not in loader
    assert "window.__devpilotLoadGameAdvanced" not in loader
    assert "/assets/build-game.js" in game_html
    assert "/assets/feature-loader.js" not in game_html
    assert REPAIR.is_file()


def test_repair_mission_has_gated_delivery_pipeline():
    source = REPAIR.read_text(encoding="utf-8")
    for stage in ("diagnose", "fix", "test", "deploy", "validate"):
        assert f"id: '{stage}'" in source
    assert "normalize(previous?.status) === 'completed'" in source
    assert "Aguardando etapa anterior" in source
    assert "Diagnostique a causa raiz" in source
    assert "Aplique a menor correção segura" in source
    assert "Valide a correção antes de qualquer deploy" in source
    assert "Implante somente a versão que passou na etapa de testes" in source
    assert "Faça verificação pós-deploy no ambiente real" in source


def test_repair_mission_preserves_security_and_real_evidence():
    source = REPAIR.read_text(encoding="utf-8")
    assert "Não invente sucesso" in source
    assert "Nunca exponha credenciais" in source
    assert "Não desabilite autenticação, autorização, testes ou validações" in source
    assert "diferencie falha de transporte/\"Failed to fetch\"" in source
    assert "não crie infraestrutura paralela por conveniência" in source
    assert "Produção validada com evidência objetiva" in source
