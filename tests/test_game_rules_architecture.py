from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_game_rules_are_versioned_workspace_scoped_and_super_admin_only():
    model = (ROOT / "app" / "game_rule_models.py").read_text(encoding="utf-8")
    routes = (ROOT / "app" / "game_rule_routes.py").read_text(encoding="utf-8")

    assert '__tablename__ = "game_rules"' in model
    assert 'UniqueConstraint("workspace_id", "rule_key", "version"' in model
    assert 'status: Mapped[str]' in model
    assert 'require_roles(Role.SUPER_ADMIN)' in routes
    assert 'GameRule.workspace_id == principal.workspace_id' in routes


def test_published_rules_are_immutable_and_simulation_is_dry_run():
    routes = (ROOT / "app" / "game_rule_routes.py").read_text(encoding="utf-8")

    assert 'rule.status != "draft"' in routes
    assert 'Versões publicadas são imutáveis' in routes
    assert 'rule.status = "published"' in routes
    assert 'item.status = "archived"' in routes
    assert '"dry_run": True' in routes
    assert 'evaluate_rules(' in routes


def test_game_rules_admin_is_declarative_and_has_no_code_execution_surface():
    frontend = (ROOT / "app" / "static" / "game-rules-admin.js").read_text(encoding="utf-8")

    assert "Regras do Jogo" in frontend
    assert "/game/rules/simulate" in frontend
    assert "Simular sem efeitos" in frontend
    assert "Publicar versão" in frontend
    assert "eval(" not in frontend
    assert "Function(" not in frontend
    assert "shell" not in frontend.lower()


def test_existing_quest_engine_remains_the_runtime_compatibility_layer():
    quest = (ROOT / "app" / "services" / "quest_engine.py").read_text(encoding="utf-8")
    rule_engine = (ROOT / "app" / "game_rule_engine.py").read_text(encoding="utf-8")

    assert "def reward_for(" in quest
    assert "stars" in quest and "moons" in quest and "swords" in quest
    assert "ALLOWED_ACTIONS" in rule_engine
    assert "eval(" not in rule_engine
    assert "exec(" not in rule_engine


def test_game_rule_router_is_aggregated_before_metadata_create_all():
    local_routes = (ROOT / "app" / "local_test_routes.py").read_text(encoding="utf-8")
    main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")

    assert "from app.game_rule_routes import router as game_rule_router" in local_routes
    assert "router.include_router(game_rule_router)" in local_routes
    assert "from app.local_test_routes import router as local_test_router" in main
    assert "Base.metadata.create_all" in main
