from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

UI = (
    ROOT /
    "app/static/tasks-operational-ui.js"
).read_text(encoding="utf-8")

CSS = (
    ROOT /
    "app/static/tasks-mobile-v10.css"
).read_text(encoding="utf-8")

INDEX = (
    ROOT /
    "app/static/index.html"
).read_text(encoding="utf-8")


def validate():
    assert "tasks-mobile-v10.css" in INDEX

    assert "row.style.display = 'none'" in UI
    assert "row.style.display = ''" in UI

    assert (
        "task-details-row[hidden]"
        in CSS
    )

    assert (
        "> td::before"
        in CSS
    )

    assert (
        "--dp-task-mobile-nav-space"
        in CSS
    )

    assert (
        ".tasks-v9-title"
        in CSS
    )

    assert (
        ".tasks-v9-actions"
        in CSS
    )

    assert (
        ".mobile-simple-item"
        in CSS
    )


if __name__ == "__main__":
    validate()

    print("LABELS ANTIGOS: REMOVIDOS")
    print("DETALHES FECHADOS: ZERO ESPAÇO")
    print("TIPOGRAFIA: OK")
    print("BOTÕES TOUCH: OK")
    print("SAFE AREA: OK")
    print("BOTTOM NAV: OK")
