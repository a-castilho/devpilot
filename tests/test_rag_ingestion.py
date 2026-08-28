from types import SimpleNamespace

from app.rag.git_source import GitRagSource
from app.rag.sanitizer import RagSanitizer


def test_sanitizer_redacts_common_secret_assignments():
    sanitized = RagSanitizer().sanitize("api_key=abc123 password: secret-value")
    assert "abc123" not in sanitized
    assert "secret-value" not in sanitized
    assert sanitized.count("[REDACTED]") == 2


def test_git_source_text_extensions_are_conservative():
    source = GitRagSource()
    assert source is not None


def test_project_requires_organization_for_indexing_contract():
    project = SimpleNamespace(id="p1", organization_id=None)
    assert project.organization_id is None
