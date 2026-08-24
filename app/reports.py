from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.quest_routes import router as quest_router
from app.quest_ui_routes import router as quest_ui_router
from app.security import require_access


# Keep this router prefix-free so feature routers can retain their canonical API paths.
# The legacy report endpoint keeps exactly the same /api/project-report URL and access policy.
router = APIRouter()
REPORT_FILE = Path(__file__).parent / "report_data" / "project-report.json"


@router.get("/api/project-report", dependencies=[Depends(require_access)])
def project_report():
    if not REPORT_FILE.is_file():
        raise HTTPException(404, "Relatório de homologação ainda não foi gerado")
    try:
        return json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(503, "Relatório de homologação indisponível") from exc


router.include_router(quest_router)
router.include_router(quest_ui_router)
