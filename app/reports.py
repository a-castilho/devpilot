from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.security import require_access


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])
REPORT_FILE = Path(__file__).parent / "report_data" / "project-report.json"


@router.get("/project-report")
def project_report():
    if not REPORT_FILE.is_file():
        raise HTTPException(404, "Relatório de homologação ainda não foi gerado")
    try:
        return json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(503, "Relatório de homologação indisponível") from exc
