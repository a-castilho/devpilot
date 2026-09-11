from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_canonical_chat_runtime_owns_mobile_controls_and_normal_chat():
    source = (ROOT / "app/static/chat-canonical-runtime.js").read_text(encoding="utf-8")

    assert "#voice-visible-conversation" in source
    assert "replaceInteractive(legacyTranscript)" in source
    assert "replaceInteractive($('#voice-chat-send'))" in source
    assert "replaceInteractive($('#voice-start'))" not in source
    assert "devpilotVoiceConversationSubmit" in source
    assert "voice-runtime-stability" in source
    assert "dataset.chatMode" in source
    assert "api('/chat'" in source
    assert "response_style: 'chat'" in source
    assert "knowledge?.sources" in source
    assert "100dvh" in source
    assert "window.visualViewport" in source


def test_mobile_chat_forces_real_scroll_area_above_status_and_composer():
    source = (ROOT / "app/static/chat-canonical-runtime.js").read_text(encoding="utf-8")

    assert "data-canonical-chat=\"1\"" in source
    assert "#voice-visible-conversation{box-sizing:border-box!important;flex:1 1 auto!important;min-height:0!important" in source
    assert "scroll-padding-bottom:140px!important" in source
    assert ".voice-chatgpt-stage{width:100%!important" in source
    assert "display:flex!important" in source
    assert ".voice-chatgpt-composer{width:100%!important" in source
    assert "#voice-start," in source
    assert "pointer-events:auto!important" in source


def test_chat_history_is_scoped_by_authenticated_identity_and_project():
    source = (ROOT / "app/static/chat-canonical-runtime.js").read_text(encoding="utf-8")

    assert "sessionIdentity" in source
    assert "payload.workspace_id" in source
    assert "payload.sub" in source
    assert "${sessionIdentity()}:${projectId() || 'general'}" in source


def test_canonical_chat_runtime_is_owned_by_feature_loader():
    feature_loader = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")
    build = (ROOT / "tools/build-vercel-static.mjs").read_text(encoding="utf-8")

    assert "'chat-canonical-runtime.js'" in feature_loader
    assert feature_loader.index("'chat-request-watchdog.js'") < feature_loader.index("'chat-canonical-runtime.js'")
    assert "'chat-canonical-runtime.js'" in build
    assert "chat-canonical-bootstrap.js" not in build


def test_chat_knowledge_combines_project_docs_live_state_and_rag():
    source = (ROOT / "app/rag/chat_context.py").read_text(encoding="utf-8")

    assert "Documentação/instruções persistentes (AGENTS.md)" in source
    assert "Atividades recentes do projeto" in source
    assert "Resultados recentes documentados" in source
    assert "_live_context" in source
    assert "project_rag_scope(project)" in source
    assert "rag.retrieve(" in source
    assert "enqueue_index_job(" in source


def test_rag_scope_falls_back_to_workspace_when_organization_is_optional():
    scope = (ROOT / "app/rag/scope.py").read_text(encoding="utf-8")
    ingestion = (ROOT / "app/rag/ingestion.py").read_text(encoding="utf-8")
    worker = (ROOT / "app/rag/worker.py").read_text(encoding="utf-8")
    admin = (ROOT / "app/rag_admin_routes.py").read_text(encoding="utf-8")

    assert "project.organization_id or project.workspace_id" in scope
    assert "project_rag_scope(project)" in ingestion
    assert "project_rag_scope(project)" in worker
    assert "project_rag_scope(project)" in admin
    assert "Project must belong to an organization" not in admin


def test_chat_javascript_has_valid_syntax():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    for path in (
        ROOT / "app/static/chat-canonical-runtime.js",
        ROOT / "app/static/feature-loader.js",
        ROOT / "tools/build-vercel-static.mjs",
    ):
        subprocess.run([node, "--check", str(path)], cwd=ROOT, check=True, capture_output=True, text=True)


def test_vercel_static_build_keeps_canonical_chat_on_demand():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run([node, "tools/build-vercel-static.mjs"], cwd=ROOT, check=True, capture_output=True, text=True)
    built = (ROOT / ".vercel-static/index.html").read_text(encoding="utf-8")
    runtime = ROOT / ".vercel-static/assets/chat-canonical-runtime.js"
    assert runtime.exists()
    assert "/assets/feature-loader.js" in built
    assert "chat-canonical-bootstrap.js" not in built
    assert "DEVPILOT_BOOTSTRAP_TOKEN" not in built
