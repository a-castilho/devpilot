from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_blueprint_admin_is_loaded_only_with_admin_bundle():
    loader = read("app/static/feature-loader.js")
    admin_start = loader.index("    admin: [")
    admin_end = loader.index("    ],", admin_start)
    admin_block = loader[admin_start:admin_end]

    assert "'blueprint-admin.js'" in admin_block
    assert "'blueprint-admin.js'" not in loader[: loader.index("  const FEATURE_BUNDLES")]


def test_blueprint_admin_is_super_admin_only_and_uses_blueprint_api():
    ui = read("app/static/blueprint-admin.js")

    assert "const ROLE = 'SUPER_ADMIN'" in ui
    assert "data.superAdmin" not in ui  # role is derived from authenticated user state
    assert "button.dataset.superAdmin = 'true'" in ui
    assert "'/api/blueprints'" in ui
    assert "'/api/blueprints/recommend'" in ui
    assert "'/api/blueprints/metrics'" in ui


def test_blueprint_admin_has_management_and_matcher_controls():
    ui = read("app/static/blueprint-admin.js")

    for marker in (
        "Blueprints de projeto",
        "Testar seleção automática",
        "Cadastrar versão",
        "Executar matcher",
        "Salvar Blueprint",
    ):
        assert marker in ui
