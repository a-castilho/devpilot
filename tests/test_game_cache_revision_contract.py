from pathlib import Path


GAME_HTML = Path("app/static/game/index.html")
BOOT = Path("app/static/game/game-bootstrap.js")
VERCEL = Path("vercel.json")


def test_game_revision_is_bumped_after_mobile_exit_hotfix():
    html = GAME_HTML.read_text(encoding="utf-8")
    boot = BOOT.read_text(encoding="utf-8")

    assert "game-flow-v94-20260914-exit" in html
    assert "game-flow-v93-20260913" not in html
    assert "game-flow-v94-20260914-exit" in boot
    assert "game-flow-v93-20260913" not in boot


def test_game_document_is_explicitly_no_store_on_vercel():
    config = VERCEL.read_text(encoding="utf-8")
    assert '"src": "/game/index.html"' in config
    assert '"Cache-Control": "no-store, max-age=0, must-revalidate"' in config
