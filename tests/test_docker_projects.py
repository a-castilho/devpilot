from tools import docker_projects


def test_discover_only_returns_explicitly_registered_projects(tmp_path):
    trusted = tmp_path / "trusted"
    trusted.mkdir()
    (trusted / "compose.yaml").write_text("services: {}", encoding="utf-8")
    (trusted / docker_projects.MARKER).touch()
    untrusted = tmp_path / "untrusted"
    untrusted.mkdir()
    (untrusted / "docker-compose.yml").write_text("services: {}", encoding="utf-8")

    projects = docker_projects.discover(tmp_path)

    assert [project.directory for project in projects] == [trusted]


def test_compose_project_name_is_stable_and_scoped(tmp_path):
    directory = tmp_path / "Meu Projeto"
    directory.mkdir()

    first = docker_projects.project_name(directory)
    second = docker_projects.project_name(directory)

    assert first == second
    assert first.startswith("devpilot-meu-projeto-")


def test_up_command_is_detached_and_builds(tmp_path):
    compose = tmp_path / "compose.yaml"
    project = docker_projects.Project("devpilot-test", tmp_path, compose)

    command = docker_projects.docker_command(project, "up")

    assert command[-2:] == ["--detach", "--build"]
    assert command[:2] == ["docker", "compose"]
