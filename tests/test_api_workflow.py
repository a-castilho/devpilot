import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import create_project, list_tasks, task_report, update_task
from app.db import Base
from app.models import Run
from app.schemas import ProjectCreate, TaskUpdate


def test_project_registration_starts_work_and_exposes_report_and_priority():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = create_project(
            ProjectCreate(
                name="Produto Novo",
                slug="produto-novo",
                description="Plataforma criada no Estúdio IA",
                repository_url="https://github.com/example/produto-novo.git",
            ),
            db,
        )
        tasks = list_tasks(limit=100, db=db)
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Inicialização automática de Produto Novo"
        assert tasks[0]["priority"] == 80

        task_id = tasks[0]["id"]
        update_task(task_id, TaskUpdate(priority=95), db)
        db.add(
            Run(
                task_id=task_id,
                status="success",
                summary="Fundação criada",
                logs=json.dumps(
                    {
                        "summary": "API, frontend e testes criados",
                        "branch": "devpilot/bootstrap",
                        "usage": {"input_tokens": 900, "output_tokens": 300, "total_tokens": 1200},
                    }
                ),
            )
        )
        db.commit()

        report = task_report(task_id, db)
        assert report["runs"][0]["output"] == "API, frontend e testes criados"
        assert report["runs"][0]["usage"]["total_tokens"] == 1200
        assert project.agents_md == ""
