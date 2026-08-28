from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Project
from app.services.audit import record
from app.services.product_delivery import delivery_due, run_delivery


def process_one_delivery() -> bool:
    """Process one due automatic homologation delivery without exposing provider details to users."""
    with SessionLocal() as db:
        projects = db.scalars(select(Project).limit(200)).all()
        project = next((item for item in projects if delivery_due(db, item)), None)
        if not project:
            return False

        try:
            run_delivery(db, project, "worker:delivery-auto")
        except Exception as error:  # defensive worker boundary
            record(
                db,
                workspace_id=project.workspace_id,
                project_id=project.id,
                actor="worker:delivery-auto",
                action="project.delivery_automation_crashed",
                outcome="failed",
                details={"error_type": type(error).__name__},
            )
            db.commit()
        return True
