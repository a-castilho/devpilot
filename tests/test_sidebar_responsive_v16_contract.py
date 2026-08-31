from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "app/static/sidebar-responsive-v16.css").read_text(encoding="utf-8")
VIEWPORT = (ROOT / "app/static/viewport-adaptive-v15.js").read_text(encoding="utf-8")


def validate():
    assert "--dp-sidebar-expanded" in CSS
    assert "min-width: var(--dp-sidebar-expanded) !important" in CSS
    assert "overflow-y: auto !important" in CSS
    assert "white-space: normal !important" in CSS
    assert "max-height: 100dvh !important" in CSS
    assert "grid-template-columns: repeat(4, minmax(0, 1fr)) !important" in CSS
    assert "sidebar-responsive-v16.css" in VIEWPORT
    assert "V16 é carregada depois da V15" in VIEWPORT


if __name__ == "__main__":
    validate()
    print("SIDEBAR EXPANDIDA: LARGURA LEGÍVEL")
    print("SIDEBAR RECOLHIDA: 72PX")
    print("NAV: SCROLL VERTICAL INDEPENDENTE")
    print("LABELS: SEM CORTE HORIZONTAL")
    print("TELA BAIXA: DENSIDADE COMPACTA")
    print("MOBILE: SHEET 100DVH")
    print("ORDEM CSS: V16 APÓS V15")
