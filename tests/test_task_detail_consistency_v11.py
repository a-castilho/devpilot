from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.frontend_ui_routes import task_detail
from app.models import Project, Task, TaskStatus, Workspace


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_task_detail_always_returns_project_name_and_hides_game_runtime_markers():
    db = _session()
    workspace = Workspace(name="DevPilot", slug="default")
    db.add(workspace)
    db.flush()

    project = Project(
        workspace_id=workspace.id,
        name="Tela Viva",
        slug="tela-viva",
        repository_url="https://github.com/example/tela-viva.git",
    )
    db.add(project)
    db.flush()

    task = Task(
        workspace_id=workspace.id,
        project_id=project.id,
        title="[Jogo] Fase 3 · Regras blindadas",
        prompt=(
            "[DEVPILOT_BUILD_GAME_V1]\n"
            "PARTIDA: game-123\n"
            "FASE: 3\n"
            "OBJETIVO: Blindar as regras\n"
            "Contexto útil para o usuário"
        ),
        source="dashboard",
        status=TaskStatus.running,
    )
    db.add(task)
    db.commit()

    detail = task_detail(task.id, db=db)

    assert detail["project_id"] == project.id
    assert detail["project_name"] == "Tela Viva"
    assert detail["source"] == "Modo Jogo"
    assert "[DEVPILOT_BUILD_GAME_V1]" not in detail["prompt"]
    assert "PARTIDA:" not in detail["prompt"]
    assert "Fase: 3" in detail["prompt"]
    assert "Objetivo: Blindar as regras" in detail["prompt"]
    assert "Contexto útil para o usuário" in detail["prompt"]


def test_normal_dashboard_task_uses_human_source_label():
    db = _session()
    workspace = Workspace(name="DevPilot", slug="default")
    db.add(workspace)
    db.flush()

    project = Project(
        workspace_id=workspace.id,
        name="Regulaai",
        slug="regulaai",
        repository_url="https://github.com/example/regulaai.git",
    )
    db.add(project)
    db.flush()

    task = Task(
        workspace_id=workspace.id,
        project_id=project.id,
        title="Revisar integração",
        prompt="Contexto do usuário: revisar somente a integração principal",
        source="dashboard",
        status=TaskStatus.completed,
    )
    db.add(task)
    db.commit()

    detail = task_detail(task.id, db=db)

    assert detail["project_name"] == "Regulaai"
    assert detail["source"] == "DevPilot"
    assert detail["prompt"] == "revisar somente a integração principal"
