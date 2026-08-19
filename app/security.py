import hashlib
import hmac

from fastapi import Depends, Header, HTTPException

from app.config import get_settings


def require_access(authorization: str | None = Header(default=None)) -> str:
    expected = get_settings().bootstrap_token
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing access token")
    return "owner"


def require_super_admin(actor: str = Depends(require_access)) -> str:
    if actor != "owner":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return actor


def privacy_id(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:32]
