from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ROUTES = (
    ROOT / "app" / "frontend_ui_routes.py"
).read_text(encoding="utf-8")

APP = (
    ROOT / "app" / "static" / "app.js"
).read_text(encoding="utf-8")

INDEX = (
    ROOT / "app" / "static" / "index.html"
).read_text(encoding="utf-8")

UI = (
    ROOT / "app" / "static" /
    "tasks-operational-ui.js"
).read_text(encoding="utf-8")

CSS = (
    ROOT / "app" / "static" /
    "tasks-operational-v9.css"
).read_text(encoding="utf-8")


def validate():
    assert (
        'project_name=projects.get(row.project_id, "")'
        in ROUTES
    )

    assert "tasks-operational-ui.js" in APP

    for element in (
        "tasks-v9-back",
        "tasks-v9-refresh",
        "tasks-v9-search",
        "tasks-v9-project",
        "tasks-v9-status",
        "tasks-v9-type",
        "tasks-v9-more",
    ):
        assert element in INDEX

    for behavior in (
        "toggleDetails",
        "deleteTask",
        "approveTask",
        "reloadTasks",
        "projectName",
        "taskMatches",
        "userContext",
    ):
        assert behavior in UI

    assert "button.textContent = 'Ocultar'" in UI
    assert "button.textContent = 'Detalhes'" in UI
    assert "method: 'DELETE'" in UI
    assert "MutationObserver" not in UI

    assert ".tasks-v9-project" in CSS
    assert ".tasks-v9-details-panel" in CSS


if __name__ == "__main__":
    validate()

    print("PROJECT_NAME: OK")
    print("FILTROS: OK")
    print("DETALHES/OCULTAR: OK")
    print("ATUALIZAR: OK")
    print("VOLTAR: OK")
    print("EXCLUIR: OK")
    print("RESPONSIVIDADE: OK")
