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


def test_atualizar_local_is_allowlisted_system_action():
    intent = interpret_voice("atualizar local no Linux")
    assert intent["action"] == "update_local"
    assert intent["project_hint"] is None
    assert intent["requires_authorization"] is False
    assert intent["system_action"] is True


def test_similar_but_unapproved_phrase_is_not_system_action():
    intent = interpret_voice("atualizar dependencias local")
    assert intent["action"] == "develop"
