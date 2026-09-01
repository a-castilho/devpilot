from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAV_JS = ROOT / "app/static/page-navigation-v26.js"
NAV_CSS = ROOT / "app/static/page-navigation-v26.css"
VIEWPORT_JS = ROOT / "app/static/viewport-adaptive-v15.js"
USERS_JS = ROOT / "app/static/users.js"


def require(text: str, needle: str, label: str) -> None:
    assert needle in text, f"faltando contrato V26: {label}"


def main() -> None:
    nav = NAV_JS.read_text(encoding="utf-8")
    css = NAV_CSS.read_text(encoding="utf-8")
    viewport = VIEWPORT_JS.read_text(encoding="utf-8")
    users = USERS_JS.read_text(encoding="utf-8")

    require(nav, "window.__devpilotPageNavigationV26", "runtime único")
    require(nav, "window.devpilotNavigate = navigate", "API central de navegação")
    require(nav, "event.target.closest?.(MAIN_NAV_SELECTOR)", "interceptação do menu")
    require(nav, "closeMobileMenu()", "fechamento do menu mobile")
    require(nav, "view.hidden = !active", "somente uma view visual")
    require(nav, "window.scrollTo({top: 0", "scroll ao topo")
    require(nav, "devpilot:page-ready", "evento de tela pronta")
    require(nav, "history[replace ? 'replaceState' : 'pushState']", "histórico discreto")

    require(css, "DevPilot Page Navigation V26", "marcador CSS")
    require(css, ".view[hidden]", "views ocultas fora do layout")
    require(css, "#devpilot-game-entry", "isolamento do jogo")
    require(css, "#mission-control-panel", "isolamento do Mission Control")
    require(css, "devpilot-page-enter-v26", "transição curta entre telas")

    require(viewport, "page-navigation-v26.css", "loader CSS V26")
    require(viewport, "page-navigation-v26.js", "loader JS V26")
    require(viewport, "loadPageNavigationV26()", "ativação V26")

    require(users, "dataset.view", "Usuários participa do roteador")
    require(users, "window.devpilotNavigate('users'", "Usuários usa navegação central")
    require(users, "devpilot:page-ready", "Usuários carrega após tela pronta")

    print("OK: Page Navigation V26 contract")


if __name__ == "__main__":
    main()
