from __future__ import annotations

import asyncio
from io import BytesIO

from starlette.datastructures import Headers, UploadFile

from app import task_image_routes
from app.security import Principal, Role


def principal(workspace_id: str) -> Principal:
    return Principal(
        user_id=f"user-{workspace_id}",
        workspace_id=workspace_id,
        email=f"{workspace_id}@example.com",
        role=Role.ADMIN,
    )


def test_upload_writes_only_inside_authenticated_workspace(tmp_path, monkeypatch):
    calls: list[str] = []

    def scoped_dir(workspace_id: str):
        calls.append(workspace_id)
        directory = tmp_path / workspace_id
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    monkeypatch.setattr(task_image_routes, "task_images_dir", scoped_dir)
    image = UploadFile(
        file=BytesIO(b"\x89PNG\r\n\x1a\nvalid-image"),
        filename="screen.png",
        headers=Headers({"content-type": "image/png"}),
    )

    payload = asyncio.run(task_image_routes.upload_task_image(image, principal("workspace-a")))

    assert calls == ["workspace-a"]
    assert (tmp_path / "workspace-a" / payload["id"]).is_file()
    assert not (tmp_path / "workspace-b" / payload["id"]).exists()


def test_delete_cannot_remove_same_marker_from_another_workspace(tmp_path, monkeypatch):
    image_id = f"{'a' * 32}.png"
    foreign_dir = tmp_path / "workspace-b"
    foreign_dir.mkdir(parents=True)
    foreign_image = foreign_dir / image_id
    foreign_image.write_bytes(b"foreign")

    def scoped_dir(workspace_id: str):
        directory = tmp_path / workspace_id
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    monkeypatch.setattr(task_image_routes, "task_images_dir", scoped_dir)

    assert task_image_routes.delete_task_image(image_id, principal("workspace-a")) is None
    assert foreign_image.read_bytes() == b"foreign"


def test_workspace_is_required_for_route_storage():
    missing = Principal(user_id="user", workspace_id=None, email="x@example.com", role=Role.ADMIN)

    try:
        task_image_routes._principal_workspace(missing)
    except Exception as error:
        assert getattr(error, "status_code", None) == 401
    else:
        raise AssertionError("missing workspace must fail closed")
