from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAME_INDEX = ROOT / "app" / "static" / "game" / "index.html"
GAME_LINK = ROOT / "app" / "static" / "game" / "delivery-test-link.js"
PROJECTS = ROOT / "app" / "static" / "mobile-project-card-compact.js"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_completed_game_loads_verified_test_link_surface():
    index = text(GAME_INDEX)
    source = text(GAME_LINK)

    assert "/assets/game/delivery-test-link.js" in index
    assert "LINK PARA TESTE" in source
    assert "Abrir sistema para teste" in source
    assert "target=\"_blank\"" in source
    assert "rel=\"noopener noreferrer\"" in source
    assert "/delivery/validate-url" in source
    assert "/delivery/auto" in source
    assert "missionDelivered" in source
    assert ".vercel.app" in source
    assert ".onrender.com" in source


def test_projects_surface_keeps_public_test_url_visible():
    source = text(PROJECTS)

    assert "project-public-url" in source
    assert "delivery.url" in source
    assert "link.target = '_blank'" in source
    assert "link.rel = 'noopener noreferrer'" in source
    assert "Produto publicado e URL validada." in source
    assert "/delivery/auto" in source
