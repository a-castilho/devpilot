from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_initial_loading_screen_is_server_injected_and_lightweight():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "def _inject_initial_loading_screen" in main
    assert 'id="devpilot-initial-loader"' in main
    assert "Inicializando central operacional" in main
    assert "devpilot:authenticated-ui-ready" in main
    assert "devpilot:authenticated-core-ready" in main
    assert "html = _inject_initial_loading_screen(html)" in main


if __name__ == "__main__":
    test_initial_loading_screen_is_server_injected_and_lightweight()
    print("INITIAL LOADER: contrato OK")
