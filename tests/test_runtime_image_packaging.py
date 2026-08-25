from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_image_copies_python_package_before_project_install():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    copy_app = dockerfile.index("COPY app ./app")
    install_project = dockerfile.index("RUN pip install --no-cache-dir '.[postgres]'")

    assert copy_app < install_project
