from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.security import Principal, require_access, session_principal
from app.services.task_images import (
    IMAGE_ID_RE,
    MAX_TASK_IMAGE_BYTES,
    task_images_dir,
)


router = APIRouter(prefix="/api/task-images", dependencies=[Depends(require_access)])


_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def _detected_extension(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    return None


def _safe_delete(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _principal_workspace(principal: Principal) -> str:
    workspace_id = str(principal.workspace_id or "").strip()
    if not workspace_id:
        raise HTTPException(401, "Sessão sem workspace válido")
    return workspace_id


@router.post("", status_code=201)
async def upload_task_image(
    image: UploadFile = File(...),
    principal: Principal = Depends(session_principal),
):
    declared_extension = _IMAGE_TYPES.get(str(image.content_type or "").lower())
    if not declared_extension:
        raise HTTPException(415, "Envie uma imagem PNG, JPG ou WEBP")

    content = await image.read(MAX_TASK_IMAGE_BYTES + 1)
    await image.close()
    if not content:
        raise HTTPException(422, "A imagem enviada está vazia")
    if len(content) > MAX_TASK_IMAGE_BYTES:
        raise HTTPException(413, "A imagem deve ter no máximo 8 MB")

    detected_extension = _detected_extension(content)
    if not detected_extension or detected_extension != declared_extension:
        raise HTTPException(415, "O arquivo enviado não corresponde a uma imagem válida")

    image_id = f"{uuid4().hex}{detected_extension}"
    target = task_images_dir(_principal_workspace(principal)) / image_id
    try:
        target.write_bytes(content)
    except OSError as error:
        _safe_delete(target)
        raise HTTPException(500, "Não foi possível armazenar a imagem para análise") from error

    return {
        "id": image_id,
        "name": image.filename or image_id,
        "content_type": image.content_type,
        "size": len(content),
        "marker": f"[DEVPILOT_IMAGE={image_id}]",
    }


@router.delete("/{image_id}", status_code=204)
def delete_task_image(
    image_id: str,
    principal: Principal = Depends(session_principal),
):
    normalized = str(image_id or "").lower()
    if not IMAGE_ID_RE.fullmatch(normalized):
        raise HTTPException(404, "Imagem não encontrada")
    _safe_delete(task_images_dir(_principal_workspace(principal)) / normalized)
    return None
