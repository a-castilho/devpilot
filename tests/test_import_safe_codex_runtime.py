from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "app" / "__init__.py"
MAIN = ROOT / "app" / "main.py"
WORKER = ROOT / "app" / "worker_entry.py"


def test_package_import_does_not_eagerly_load_codex_runtime_auth():
    source = PACKAGE.read_text(encoding="utf-8")
    assert "codex_runtime_auth" not in source


def test_web_initializes_codex_auth_after_schema_creation():
    source = MAIN.read_text(encoding="utf-8")
    create = source.index("Base.metadata.create_all(bind=engine)")
    schema = source.index("ensure_runtime_schema(engine)", create)
    auth = source.index("codex_runtime_auth", schema)
    assert create < schema < auth


def test_dedicated_worker_initializes_codex_auth_at_runtime():
    source = WORKER.read_text(encoding="utf-8")
    main = source.index("def main() -> None:")
    auth = source.index("codex_runtime_auth", main)
    assert auth > main
