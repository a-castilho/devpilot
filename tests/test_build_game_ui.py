from pathlib import Path


BUILD_GAME_JS = Path("app/static/build-game.js")
BUILD_GAME_NEW_SESSION_JS = Path("app/static/build-game-new-session.js")
BUILD_GAME_URL_BONUS_JS = Path("app/static/build-game-url-bonus.js")
BUILD_GAME_COCKPIT_JS = Path("app/static/build-game-cockpit.js")
BUILD_GAME_COCKPIT_CSS = Path("app/static/build-game-cockpit.css")
INDEX_HTML = Path("app/static/index.html")
TASK_ANALYTICS_JS = Path("app/static/task-analytics.js")
FEATURE_LOADER_JS = Path("app/static/feature-loader.js")


def test_build_game_is_loaded_only_by_explicit_feature_bundle():
    analytics = TASK_ANALYTICS_JS.read_text(encoding="utf-8")
    loader = FEATURE_LOADER_JS.read_text(encoding="utf-8")

    assert "/assets/build-game.js" not in analytics
    assert "data-build-game-loader" not in analytics
    assert "game: [" in loader
    assert "'build-game.js'" in loader
    assert "data-devpilot-feature-placeholder" in loader


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


def test_game_requires_real_repository_progress_in_every_phase():
    source = BUILD_GAME_JS.read_text(encoding="utf-8")

    assert "CONTRATO DE PROGRESSÃO REAL" in source
    assert "Toda fase precisa deixar um delta persistente e verificável no projeto" in source
    assert "git status --short" in source
    assert "git diff --stat" in source
    assert "ANTES, a MUDANÇA IMPLEMENTADA e o DEPOIS" in source
    assert "NÃO marque a tarefa como concluída" in source
    assert "URL pública é evidência de entrega, não prêmio que substitui código" in source
    assert "Esta fase NÃO pode terminar apenas com análise" in source
    assert "Se não houver delta funcional real, a fase deve permanecer incompleta ou falhar" in source


def test_game_preserves_history_and_supports_new_missions():
    source = BUILD_GAME_JS.read_text(encoding="utf-8")

    assert "devpilot-build-game-mission" in source
    assert "Começar uma nova partida? O histórico atual será preservado nas tarefas." in source
    assert ".devpilot/build-game.md" in source
    assert "XP" in source


def test_new_game_is_part_of_explicit_bundle_and_resets_visible_state():
    loader = FEATURE_LOADER_JS.read_text(encoding="utf-8")
    source = BUILD_GAME_NEW_SESSION_JS.read_text(encoding="utf-8")

    assert "'build-game-new-session.js'" in loader
    assert loader.index("'build-game.js'") < loader.index("'build-game-new-session.js'")
    assert "previousMissionId = missionId()" in source
    assert "0/6 fases" in source
    assert "0/${TOTAL_XP} XP" in source
    assert "build-game-victory" in source
    assert "build-game-url-bonus" in source
    assert "build-game-subphases" in source
    assert "A partida começa quando você jogar a primeira fase." in source
    assert "devpilot:build-game-new-session" in source
    assert "await window.loadBuildGame()" in source


def test_completed_game_uses_explicit_url_bonus_before_mission_completion():
    loader = FEATURE_LOADER_JS.read_text(encoding="utf-8")
    bonus = BUILD_GAME_URL_BONUS_JS.read_text(encoding="utf-8")

    assert "'build-game-url-bonus.js'" in loader
    assert loader.index("'build-game.js'") < loader.index("'build-game-url-bonus.js'")
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
    analytics = TASK_ANALYTICS_JS.read_text(encoding="utf-8")

    assert "old workers could leave successful game tasks in review forever" in analytics
    assert "[DEVPILOT_BUILD_GAME_V1]" in analytics
    assert "legacyReview" in analytics
    assert "task?.requires_approval !== true" in analytics
    assert "return {...task, status:'completed'}" in analytics


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
