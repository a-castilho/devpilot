from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import Principal, session_principal
from app.services.ai_costs import budget_block_reason


def require_ai_budget_access(
    principal: Principal = Depends(session_principal),
    db: Session = Depends(get_db),
) -> None:
    reason = budget_block_reason(
        db,
        workspace_id=principal.workspace_id,
        user_id=principal.user_id,
    )
    if reason:
        raise HTTPException(status_code=402, detail=reason)
