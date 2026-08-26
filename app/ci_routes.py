from __future__ import annotations

import hashlib
import hmac

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.config import get_settings
from app.db import SessionLocal
from app.services.ci_orchestrator import enqueue_ci_failure, failure_from_workflow_run


router = APIRouter(prefix="/api/integrations/github", tags=["ci-orchestrator"])


def _verify_signature(body: bytes, signature: str, secret: str) -> bool:
    if not secret or not signature.startswith("sha256="):
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, f"sha256={digest}")


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    x_github_event: str = Header(default="", alias="X-GitHub-Event"),
    x_hub_signature_256: str = Header(default="", alias="X-Hub-Signature-256"),
):
    settings = get_settings()
    if not settings.github_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub CI webhook is not configured",
        )

    body = await request.body()
    if not _verify_signature(body, x_hub_signature_256, settings.github_webhook_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    if x_github_event != "workflow_run":
        return {"status": "ignored", "reason": "unsupported_event"}

    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON") from exc

    failure = failure_from_workflow_run(payload)
    if failure is None:
        return {"status": "ignored", "reason": "not_actionable"}

    with SessionLocal() as db:
        return enqueue_ci_failure(db, failure)
