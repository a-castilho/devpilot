from app.services.security_scanner import _is_sensitive_filename


def test_real_environment_files_are_sensitive():
    assert _is_sensitive_filename(".env") is True
    assert _is_sensitive_filename("config/.env.production") is True


def test_environment_templates_are_not_security_findings():
    assert _is_sensitive_filename(".env.example") is False
    assert _is_sensitive_filename(".env.sample") is False
    assert _is_sensitive_filename("config/.env.production.template") is False
    assert _is_sensitive_filename(".env.dist") is False
