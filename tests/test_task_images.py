import sys
from types import SimpleNamespace

import pytest

from app.services import task_images


def test_image_markers_are_deduplicated_and_stripped():
    image_name = f"{'a' * 32}.png"
    prompt = (
        "Analise este problema visual.\n"
        f"[DEVPILOT_IMAGE={image_name}]\n"
        f"[DEVPILOT_IMAGE={image_name}]"
    )

    assert task_images.image_names_from_prompt(prompt) == [image_name]
    clean = task_images.strip_image_markers(prompt)
    assert clean == "Analise este problema visual."
    assert "DEVPILOT_IMAGE" not in clean


def test_task_image_directories_are_isolated_by_workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(task_images, "task_images_root", lambda: tmp_path)

    first = task_images.task_images_dir("workspace-a")
    second = task_images.task_images_dir("workspace-b")

    assert first == tmp_path / "workspace-a"
    assert second == tmp_path / "workspace-b"
    assert first != second


def test_codex_image_command_uses_only_project_workspace(monkeypatch, tmp_path):
    image_name = f"{'b' * 32}.webp"
    workspace_dir = tmp_path / "workspace-a"
    workspace_dir.mkdir()
    image_path = workspace_dir / image_name
    image_path.write_bytes(b"RIFF0000WEBP")
    monkeypatch.setattr(task_images, "task_images_dir", lambda workspace_id: tmp_path / workspace_id)

    project = SimpleNamespace(workspace_id="workspace-a")

    def original_command(_project, prompt):
        return ["codex", "exec", "--json", prompt]

    command = task_images.build_codex_image_command(
        original_command,
        project,
        f"Compare a tela com o esperado.\n[DEVPILOT_IMAGE={image_name}]",
    )

    assert command[0] == sys.executable
    assert command[1] == "-c"
    assert "--image" in command
    assert command[-2:] == ["--image", str(image_path)]
    assert "DEVPILOT_IMAGE" not in " ".join(command)


def test_codex_cannot_reuse_marker_from_another_workspace(monkeypatch, tmp_path):
    image_name = f"{'c' * 32}.jpg"
    foreign = tmp_path / "workspace-b"
    foreign.mkdir()
    (foreign / image_name).write_bytes(b"\xff\xd8\xfffake")
    own = tmp_path / "workspace-a"
    own.mkdir()
    monkeypatch.setattr(task_images, "task_images_dir", lambda workspace_id: tmp_path / workspace_id)

    with pytest.raises(RuntimeError, match="neste workspace"):
        task_images.build_codex_image_command(
            lambda _project, prompt: ["codex", "exec", prompt],
            SimpleNamespace(workspace_id="workspace-a"),
            f"Analise.\n[DEVPILOT_IMAGE={image_name}]",
        )


def test_codex_image_command_fails_if_uploaded_image_is_missing(monkeypatch, tmp_path):
    image_name = f"{'d' * 32}.jpg"
    workspace_dir = tmp_path / "workspace-a"
    workspace_dir.mkdir()
    monkeypatch.setattr(task_images, "task_images_dir", lambda workspace_id: tmp_path / workspace_id)

    with pytest.raises(RuntimeError, match="não está mais disponível"):
        task_images.build_codex_image_command(
            lambda _project, prompt: ["codex", "exec", prompt],
            SimpleNamespace(workspace_id="workspace-a"),
            f"Analise.\n[DEVPILOT_IMAGE={image_name}]",
        )


def test_image_marker_requires_project_workspace(monkeypatch, tmp_path):
    image_name = f"{'e' * 32}.png"
    monkeypatch.setattr(task_images, "task_images_dir", lambda workspace_id: tmp_path / workspace_id)

    with pytest.raises(RuntimeError, match="Projeto sem workspace"):
        task_images.build_codex_image_command(
            lambda _project, prompt: ["codex", "exec", prompt],
            SimpleNamespace(),
            f"Analise.\n[DEVPILOT_IMAGE={image_name}]",
        )
