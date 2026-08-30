from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"

APP = (STATIC / "app.js").read_text(encoding="utf-8")
LOADER = (
    STATIC / "feature-loader.js"
).read_text(encoding="utf-8")
MODAL = (
    STATIC / "task-modal.js"
).read_text(encoding="utf-8")
GAME = (
    STATIC / "game-weapons.js"
).read_text(encoding="utf-8")


def validate():
    # Um único fluxo de abertura.
    assert "devpilotOpenTaskModal" in APP
    assert "ensureTaskProjectsForModal" in APP

    # Modal precisa aparecer antes de carregar projetos/plugins.
    open_at = APP.index("modal.showModal")
    projects_at = APP.index(
        "ensureTaskProjectsForModal(projectId)"
    )
    assert open_at < projects_at

    # Nunca redesenhar Projetos/Naves só para preencher select.
    assert (
        "task-modal' && !state.projects.length) "
        "await loadProjects()"
    ) not in APP

    # Proteção de duplo submit.
    assert "taskForm.dataset.submitting" in APP

    # Pós-submit não bloqueia o retorno visual.
    assert "requestIdleCallback" in APP

    # Loader fornece módulos, mas não possui o clique.
    assert "taskModal:" in LOADER
    assert "gameWeapons:" in LOADER

    assert (
        """['[data-open="task-modal"]', 'taskModal']"""
        not in LOADER
    )

    assert (
        """['[data-project-task]', 'taskModal']"""
        not in LOADER
    )

    # Jogo não pode contaminar modal genérico.
    assert "data-game-weapons-loader" not in MODAL

    # Nenhum observer global do body.
    assert "new MutationObserver(scheduleSync)" not in GAME

    # Funcionalidades essenciais preservadas.
    for asset in (
        "project-ships.js",
        "super-admin-voice.js",
        "rag-admin-ui.js",
    ):
        assert asset in LOADER


if __name__ == "__main__":
    validate()

    print("NOVA TAREFA · FLUXO ÚNICO: OK")
    print("MODAL IMEDIATO: OK")
    print("SEM RENDER DAS NAVES AO ABRIR: OK")
    print("SEM DUPLO SUBMIT: OK")
    print("GAME ISOLADO: OK")
    print("RUNTIME GOLDEN PRESERVADO: OK")
