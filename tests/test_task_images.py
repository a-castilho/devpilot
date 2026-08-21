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


def test_codex_image_command_uses_image_flag_and_prompt_via_stdin(monkeypatch, tmp_path):
    image_name = f"{'b' * 32}.webp"
    image_path = tmp_path / image_name
    image_path.write_bytes(b"RIFF0000WEBP")
    monkeypatch.setattr(task_images, "task_images_dir", lambda: tmp_path)

    project = SimpleNamespace()

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


def test_codex_image_command_fails_if_uploaded_image_is_missing(monkeypatch, tmp_path):
    image_name = f"{'c' * 32}.jpg"
    monkeypatch.setattr(task_images, "task_images_dir", lambda: tmp_path)

    with pytest.raises(RuntimeError, match="não está mais disponível"):
        task_images.build_codex_image_command(
            lambda _project, prompt: ["codex", "exec", prompt],
            SimpleNamespace(),
            f"Analise.\n[DEVPILOT_IMAGE={image_name}]",
        )
