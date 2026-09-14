from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import Project, Workspace


logger = logging.getLogger(__name__)

JOBPILOT_SLUG = "jobpilot"
JOBPILOT_DESCRIPTION = (
    "Automação de candidaturas a vagas: descoberta, análise de aderência, "
    "orquestração segura de aplicações e rastreabilidade por plataforma."
)
JOBPILOT_AGENTS_MD = """# JobPilot

Projeto independente gerenciado pelo DevPilot.

Objetivo: automatizar descoberta, análise e candidatura a vagas com segurança,
auditoria e intervenção humana apenas quando necessária (CAPTCHA, MFA ou dado
obrigatório desconhecido).

Stack alvo:
- Python 3.12
- FastAPI
- SQLAlchemy
- PostgreSQL compatível (SQLite apenas em desenvolvimento)
- Playwright para automação de navegador

Regras:
- nunca inventar dados do candidato;
- nunca contornar CAPTCHA ou MFA;
- registrar cada tentativa e mudança de estado;
- usar adaptadores por plataforma;
- priorizar alterações pequenas, testáveis e reversíveis.
"""


def _jobpilot_config() -> dict:
    return {
        "repository_pending": True,
        "repository_mode": "deferred",
        "repository_provision_state": "pending",
        "generation_strategy": "from_scratch",
        "managed_by_devpilot": True,
        "stack": {
            "language": "Python 3.12",
            "backend": "FastAPI",
            "orm": "SQLAlchemy",
            "database": "PostgreSQL",
            "automation": "Playwright",
        },
        "capabilities": [
            "job-discovery",
            "job-matching",
            "application-orchestration",
            "platform-adapters",
            "audit-trail",
        ],
    }


def bootstrap_jobpilot_project(engine: Engine) -> bool:
    """Ensure JobPilot exists as an independent DevPilot-managed project.

    Returns True only when a new project is inserted. The operation is
    idempotent so application restarts never create duplicates.
    """
    with Session(engine) as db:
        workspace = db.scalar(select(Workspace).where(Workspace.slug == "default"))
        if workspace is None:
            workspace = Workspace(name="DevPilot", slug="default")
            db.add(workspace)
            db.flush()

        existing = db.scalar(
            select(Project).where(
                Project.workspace_id == workspace.id,
                Project.slug == JOBPILOT_SLUG,
            )
        )
        if existing is not None:
            return False

        project = Project(
            workspace_id=workspace.id,
            organization_id=None,
            name="JobPilot",
            slug=JOBPILOT_SLUG,
            description=JOBPILOT_DESCRIPTION,
            repository_url="",
            default_branch="main",
            agents_md=JOBPILOT_AGENTS_MD,
            codex_config=json.dumps(_jobpilot_config(), ensure_ascii=False),
        )
        db.add(project)
        db.commit()
        logger.info("JobPilot project bootstrapped in DevPilot: project_id=%s", project.id)
        return True
