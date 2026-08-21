from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app" / "main.py"
ASSET = ROOT / "app" / "static" / "repeatai-dashboard-graphs.js"


def test_complete_repeatai_graph_asset_is_loaded_by_spa():
    main = MAIN.read_text(encoding="utf-8")
    assert 'repeatai-dashboard-graphs.js' in main
    assert ASSET.is_file()


def test_complete_repeatai_graph_dashboard_contains_original_signal_views():
    script = ASSET.read_text(encoding="utf-8")
    expected = (
        "Linha do tempo por evento",
        "Distribuição dos eventos",
        "Mapa de calor",
        "Trajetória e cliques",
        "Categorias de teclado",
        "Scroll por direção",
        "Ritmo de interação",
        "MOUSE_SAMPLE_MS",
        "IntersectionObserver",
    )
    for marker in expected:
        assert marker in script


def test_complete_repeatai_graphs_do_not_add_external_chart_dependencies():
    script = ASSET.read_text(encoding="utf-8").lower()
    assert "chart.js" not in script
    assert "cdn.jsdelivr" not in script
    assert "unpkg.com" not in script
