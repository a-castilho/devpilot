from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_image_copies_python_package_before_project_install():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    copy_app = dockerfile.index("COPY app ./app")
    install_project = dockerfile.index("pip install --no-cache-dir '.[postgres,rag]'")

    assert copy_app < install_project


def test_runtime_image_retries_python_dependency_install_after_network_failures():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "PIP_DEFAULT_TIMEOUT=120" in dockerfile
    assert "PIP_RETRIES=10" in dockerfile
    assert 'echo "Python dependency install attempt ${attempt}/4"' in dockerfile
    assert "if pip install --no-cache-dir '.[postgres,rag]'; then" in dockerfile
    assert "sleep $((attempt * 10))" in dockerfile
