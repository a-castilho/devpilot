from pathlib import Path


BUILD_GAME_JS = Path("app/static/build-game.js")
BUILD_GAME_NEW_SESSION_JS = Path("app/static/build-game-new-session.js")
BUILD_GAME_URL_BONUS_JS = Path("app/static/build-game-url-bonus.js")
BUILD_GAME_COCKPIT_JS = Path("app/static/build-game-cockpit.js")
BUILD_GAME_COCKPIT_CSS = Path("app/static/build-game-cockpit.css")
INDEX_HTML = Path("app/static/index.html")
GAME_HTML = Path("app/static/game/index.html")
GAME_PIPELINE_COMPAT_JS = Path("app/static/game/pipeline-v2-compat.js")
TASK_ANALYTICS_JS = Path("app/static/task-analytics.js")
FEATURE_LOADER_JS = Path("app/static/feature-loader.js")


def test_build_game_is_loaded_only_by_standalone_game_document():
    analytics = TASK_ANALYTICS_JS.read_text(encoding="utf-8")
    loader = FEATURE_LOADER_JS.read_text(encoding="utf-8")
    game_html = GAME_HTML.read_text(encoding="utf-8")

    assert "/assets/build-game.js" not in analytics
    assert "data-build-game-loader" not in analytics
    assert "game: [" not in loader
    assert "'build-game.js'" not in loader
    assert "/assets/build-game.js" in game_html
    assert "/assets/feature-loader.js" not in game_html
    assert "data-devpilot-feature-placeholder" in loader


def test_build_game_uses_real_project_tasks_and_sequential_v2_gates():
    source = BUILD_GAME_JS.read_text(encoding="utf-8")
    assert "[DEVPILOT_BUILD_GAME_V1]" in source
    assert "[DEVPILOT_BUILD_GAME_PIPELINE_V2]" in source
    phase_names = [
        "name: 'Planejamento'",
        "name: 'Implementação'",
        "name: 'Execução'",
        "name: 'Testes'",
        "name: 'Documentação'",
        "name: 'Git'",
        "name: 'Entrega e revisão'",
    ]
    assert all(name in source for name in phase_names)
    assert [source.index(name) for name in phase_names] == sorted(source.index(name) for name in phase_names)
    assert "normalize(task?.status) === 'completed'" in source
    assert "phase.id <= game.current" in source
    assert "/tasks?project_id=${encodeURIComponent(selectedProjectId)}&limit=500" in source
    assert "Conclua a etapa atual antes de avançar" in source


def test_game_initial_page_always_exposes_project_combo_and_round_goal():
    source = BUILD_GAME_JS.read_text(encoding="utf-8")
    game_html = GAME_HTML.read_text(encoding="utf-8")

    assert '<label>Projeto<select id="build-game-project">${projectOptions}</select></label>' in source
    assert "Entrega da rodada" in source
    assert "Nova rodada" in source
    assert "Planejamento → Implementação → Execução → Testes → Documentação → Git → Entrega/revisão" in source
    assert "frontend-v49-game-v2" in game_html


def test_lightweight_history_keeps_v2_identity_without_reinterpreting_legacy_games():
    compat = GAME_PIPELINE_COMPAT_JS.read_text(encoding="utf-8")
    game_html = GAME_HTML.read_text(encoding="utf-8")

    assert "[DEVPILOT_BUILD_GAME_PIPELINE_V2]" in compat
    assert "title.startsWith('[Jogo] Etapa ')" in compat
    assert "prompt.includes(GAME_MARKER)" in compat
    assert "/assets/game/pipeline-v2-compat.js" in game_html
    assert game_html.index("task-payload-guard.js") < game_html.index("pipeline-v2-compat.js") < game_html.index("game-bootstrap.js")


def test_each_game_phase_creates_an_executable_devpilot_task():
    source = BUILD_GAME_JS.read_text(encoding="utf-8")
    assert "await api('/tasks'" in source
    assert "[DEVPILOT_MODE=develop]" in source
    assert "requires_approval: false" in source
    assert "source: 'dashboard'" in source
    assert "CRITÉRIO DE VITÓRIA" in source
    assert "não invente aprovação" in source
    assert "não use fallback que transforme falha em sucesso" in source


def test_game_requires_stage_specific_evidence_and_real_implementation_delta():
    source = BUILD_GAME_JS.read_text(encoding="utf-8")
    assert "CONTRATO DE PROGRESSÃO REAL" in source
    assert "Evidência obrigatória desta etapa" in source
    assert "Na Implementação deve existir delta funcional persistente" in source
    assert "Nas demais etapas, a evidência específica acima é obrigatória" in source
    assert "git status --short" in source
    assert "git diff --stat" in source
    assert "ANTES, a AÇÃO REALIZADA, a EVIDÊNCIA e o DEPOIS" in source
    assert "NÃO marque a tarefa como concluída" in source
    assert "URL pública é evidência de entrega, não prêmio que substitui código" in source
    assert "Esta etapa NÃO pode terminar apenas com análise" in source
    assert "Se a implementação pedida estiver parcial, mantenha a etapa incompleta ou bloqueada" in source


def test_round_goal_is_written_by_user_and_locked_after_pipeline_starts():
    source = BUILD_GAME_JS.read_text(encoding="utf-8")
    cockpit = BUILD_GAME_COCKPIT_JS.read_text(encoding="utf-8")

    assert "Entrega da rodada" in source
    assert "data-round-goal-locked" in source
    assert "const goalLocked = missionTasks.length > 0" in source
    assert "missionTasks.length ? historicalGoal" in source
    assert "Preserve o objetivo literal da rodada" in source
    assert "Descreva o que deve ser entregue nesta rodada" in source
    assert "Objetivo definido automaticamente" not in cockpit
    assert "O jogo não inventa o objetivo" in cockpit


def test_round_only_wins_with_final_delivery_review_evidence():
    source = BUILD_GAME_JS.read_text(encoding="utf-8")

    assert "UMA RODADA · UMA ENTREGA REAL" in source
    assert "Planejamento → Implementação → Execução → Testes → Documentação → Git → Entrega/revisão" in source
    assert "ENTREGA DA RODADA" in source
    assert "A rodada só vence se a funcionalidade descrita pelo usuário existir de ponta a ponta" in source
    assert "game.passed === phases.length" in source
    assert "Entrega da rodada pronta para o usuário" in source


def test_game_preserves_history_and_supports_new_missions():
    source = BUILD_GAME_JS.read_text(encoding="utf-8")
    assert "devpilot-build-game-mission" in source
    assert "Começar uma nova rodada? O histórico e a entrega atual serão preservados nas tarefas." in source
    assert ".devpilot/build-game.md" in source
    assert "XP" in source


def test_new_game_runtime_is_not_owned_by_dashboard_loader_and_resets_visible_state():
    loader = FEATURE_LOADER_JS.read_text(encoding="utf-8")
    source = BUILD_GAME_NEW_SESSION_JS.read_text(encoding="utf-8")
    assert "'build-game-new-session.js'" not in loader
    assert "'build-game.js'" not in loader
    assert "previousMissionId = missionId()" in source
    assert "0/7 etapas" in source
    assert "0/${TOTAL_XP} XP" in source
    assert "build-game-victory" in source
    assert "build-game-url-bonus" in source
    assert "build-game-subphases" in source
    assert "A rodada começa quando você iniciar o Planejamento." in source
    assert "devpilot:build-game-new-session" in source
    assert "await window.loadBuildGame()" in source


def test_completed_game_url_bonus_is_not_owned_by_dashboard_loader():
    loader = FEATURE_LOADER_JS.read_text(encoding="utf-8")
    bonus = BUILD_GAME_URL_BONUS_JS.read_text(encoding="utf-8")
    assert "'build-game-url-bonus.js'" not in loader
    assert "'build-game.js'" not in loader
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