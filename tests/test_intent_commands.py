from app.services.intent import interpret_voice


def test_iniciar_projeto_prepares_authorized_project_creation():
    intent = interpret_voice("iniciar projeto Portal Cliente")
    assert intent["action"] == "start_project"
    assert intent["project_name"] == "Portal Cliente"
    assert intent["project_slug"] == "portal-cliente"
    assert intent["requires_authorization"] is True
    assert intent["project_hint"] is None
    assert intent["operational"] is True


def test_regular_development_command_remains_develop():
    intent = interpret_voice("desenvolva o menu no regulaai")
    assert intent["action"] == "develop"
    assert intent["project_hint"] == "regulaai"
    assert intent["operational"] is True


def test_fix_command_is_operational_development():
    intent = interpret_voice("corrija o microfone no devpilot")
    assert intent["action"] == "develop"
    assert intent["project_hint"] == "devpilot"
    assert intent["operational"] is True


def test_test_command_is_operational_test():
    intent = interpret_voice("teste o login no devpilot")
    assert intent["action"] == "test"
    assert intent["project_hint"] == "devpilot"
    assert intent["operational"] is True


def test_deploy_command_is_operational_deploy():
    intent = interpret_voice("implante no devpilot")
    assert intent["action"] == "deploy"
    assert intent["project_hint"] == "devpilot"
    assert intent["operational"] is True


def test_analysis_command_is_operational_analysis():
    intent = interpret_voice("analise os erros no devpilot")
    assert intent["action"] == "analyze"
    assert intent["project_hint"] == "devpilot"
    assert intent["operational"] is True


def test_atualizar_local_is_allowlisted_system_action():
    intent = interpret_voice("atualizar local no Linux")
    assert intent["action"] == "update_local"
    assert intent["project_hint"] is None
    assert intent["requires_authorization"] is False
    assert intent["system_action"] is True
    assert intent["operational"] is True


def test_similar_but_unapproved_phrase_is_not_system_action():
    intent = interpret_voice("atualizar dependencias local")
    assert intent["action"] == "develop"
    assert intent["operational"] is False
