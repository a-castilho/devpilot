from pathlib import Path


BUILD_GAME_JS = Path("app/static/build-game.js")
BUILD_GAME_URL_BONUS_JS = Path("app/static/build-game-url-bonus.js")
BUILD_GAME_COCKPIT_JS = Path("app/static/build-game-cockpit.js")
BUILD_GAME_COCKPIT_CSS = Path("app/static/build-game-cockpit.css")
INDEX_HTML = Path("app/static/index.html")
TASK_ANALYTICS_JS = Path("app/static/task-analytics.js")


def test_build_game_is_loaded_from_dashboard():
    loader = TASK_ANALYTICS_JS.read_text(encoding="utf-8")

    assert "/assets/build-game.js?v=20260824-1" in loader
    assert "data-build-game-loader" in loader


def test_build_game_uses_real_project_tasks_and_sequential_gates():
    source = BUILD_GAME_JS.read_text(encoding="utf-8")

    assert "[DEVPILOT_BUILD_GAME_V1]" in source
    assert "Mapa da missão" in source
    assert "Batalha de testes" in source
    assert "Chefe final" in source
    assert "normalize(task?.status) === 'completed'" in source
    assert "phase.id <= game.current" in source
    assert "/tasks?project_id=${encodeURIComponent(selectedProjectId)}&limit=500" in source
    assert "Conclua a fase atual antes de avançar" in source


def test_each_game_phase_creates_an_executable_devpilot_task():
    source = BUILD_GAME_JS.read_text(encoding="utf-8")

    assert "await api('/tasks'" in source
    assert "[DEVPILOT_MODE=develop]" in source
    assert "requires_approval: false" in source
    assert "source: 'dashboard'" in source
    assert "CRITÉRIO DE VITÓRIA" in source
    assert "não invente aprovação" in source
    assert "não use fallback que transforme falha em sucesso" in source


def test_game_preserves_history_and_supports_new_missions():
    source = BUILD_GAME_JS.read_text(encoding="utf-8")

    assert "devpilot-build-game-mission" in source
    assert "Começar uma nova partida? O histórico atual será preservado nas tarefas." in source
    assert ".devpilot/build-game.md" in source
    assert "XP" in source


def test_completed_game_requires_real_verified_url_before_mission_completion():
    loader = TASK_ANALYTICS_JS.read_text(encoding="utf-8")
    bonus = BUILD_GAME_URL_BONUS_JS.read_text(encoding="utf-8")

    assert "/assets/build-game-url-bonus.js?v=20260824-1" in loader
    assert "data-build-game-url-bonus-loader" in loader
    assert "#build-game-view .build-game-victory" in bonus
    assert "CHEFE FINAL VENCIDO · ENTREGA PENDENTE" in bonus
    assert "A missão só será concluída quando uma URL pública real responder com sucesso." in bonus
    assert "ENTREGA FINAL CONCLUÍDA" in bonus
    assert "Publicar e gerar URL" in bonus
    assert "/delivery/${action}" in bonus
    assert "/delivery/validate-url" in bonus
    assert "missionDelivered(delivery)" in bonus
    assert "PRONTO PARA TESTAR" in bonus
    assert "noopener noreferrer" in bonus
    assert "^https:\\/\\/" in bonus


def test_legacy_review_does_not_freeze_game_progression():
    loader = TASK_ANALYTICS_JS.read_text(encoding="utf-8")

    assert "old workers could leave successful game tasks in review forever" in loader
    assert "[DEVPILOT_BUILD_GAME_V1]" in loader
    assert "legacyReview" in loader
    assert "task?.requires_approval !== true" in loader
    assert "return {...task, status:'completed'}" in loader


def test_build_game_cockpit_skin_is_loaded_and_bridges_devpilot_voice():
    dashboard = INDEX_HTML.read_text(encoding="utf-8")
    source = BUILD_GAME_COCKPIT_JS.read_text(encoding="utf-8")
    styles = BUILD_GAME_COCKPIT_CSS.read_text(encoding="utf-8")

    assert "/assets/build-game-cockpit.js?v=20260824-1" in dashboard
    assert "VISÃO DA CABINE" in source
    assert "COMMS · DEVPILOTVOZ" in source
    assert "devpilot-build-game-project" in source
    assert "devpilot-chat-active-project-id" in source
    assert "window.devpilotChatProjectContext" in source
    assert "#voice-dock" in source
    assert "/api/super-admin/voice" in source
    assert "devpilot:build-game-voice-link" in source
    assert "build-game-cockpit-window" in styles
    assert "prefers-reduced-motion:no-preference" in styles


def test_restricted_voice_diagnostic_is_not_reported_as_online():
    source = BUILD_GAME_COCKPIT_JS.read_text(encoding="utf-8")

    assert "if (response.status === 403)" in source
    assert "updateVoiceState(view, 'warn', message)" in source
    assert "ok: null" in source
    assert "diagnostic_restricted: true" in source
    assert "voice_client_ready: voiceClientReady" in source
    assert "voiceClientReady ? 'online' : 'warn'" not in source
    assert "DevPilotVoz disponível'" not in source
