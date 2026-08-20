from app.services.intent import interpret_voice


def test_iniciar_projeto_prepares_authorized_project_creation():
    intent = interpret_voice("iniciar projeto Portal Cliente")
    assert intent["action"] == "start_project"
    assert intent["project_name"] == "Portal Cliente"
    assert intent["project_slug"] == "portal-cliente"
    assert intent["requires_authorization"] is True
    assert intent["project_hint"] is None


def test_regular_development_command_remains_develop():
    intent = interpret_voice("desenvolva o menu no regulaai")
    assert intent["action"] == "develop"
    assert intent["project_hint"] == "regulaai"
