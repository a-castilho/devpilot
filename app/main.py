from contextlib import asynccontextmanager
from pathlib import Path
import re

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401
from app.ai_budget_dependency import require_ai_budget_access
from app.api import router
from app.auth_routes import router as auth_router
from app.career_routes import router as career_router
from app.cloud_admin_routes import router as cloud_admin_router
from app.config import get_settings
from app.deploy_routes import router as deploy_router
from app.embedded_worker import EmbeddedWorker
from app.host_action_routes import router as host_action_router
from app.investia_admin_routes import router as investia_admin_router
from app.investia_public_routes import router as investia_public_router
from app.linux_routes import router as linux_router
from app.ollama_provider_routes import router as ollama_provider_router
from app.product_delivery_routes import router as product_delivery_router
from app.project_provisioning_routes import router as project_provisioning_router
from app.provider_models_routes import router as provider_models_router
from app.super_admin_voice_routes import router as super_admin_voice_router
from app.task_image_routes import router as task_image_router
from app.task_run_routes import router as task_run_router
from app.token_usage_routes import router as token_usage_router
from app.user_routes import router as users_router
from app.reports import router as reports_router
from app.telemetry import router as telemetry_router
from app.telemetry_replay import router as telemetry_replay_router
from app.version import __version__
from app.voice_conversation_routes import router as voice_conversation_router
from app.voice_speech_routes import router as voice_speech_router
from app.voice_transcription_routes import router as voice_transcription_router
from app.db import Base, engine
from app.services.ollama_voice_bridge import install_voice_ollama_bridge
from app.services.schema import ensure_runtime_schema


install_voice_ollama_bridge()

STATIC = Path(__file__).parent / "static"
_SCRIPT_SRC_RE = re.compile(
    r'(?P<prefix><script\s+src="/assets/(?P<name>[^"?]+\.js))(?:\?v=[^"]+)?(?P<suffix>"[^>]*></script>)'
)


def _version_frontend_scripts(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        asset = STATIC / match.group("name")
        try:
            revision = str(asset.stat().st_mtime_ns)
        except OSError:
            revision = "1"
        return f'{match.group("prefix")}?v={revision}{match.group("suffix")}'

    return _SCRIPT_SRC_RE.sub(replace, html)


def _normalize_index_head(html: str) -> str:
    start = html.find("<head>")
    end = html.find("</head>", start)
    if start < 0 or end < 0:
        return html

    head = html[start:end]
    head = head.replace("\\r\\n", "\n").replace("\\n", "\n")
    return f"{html[:start]}{head}{html[end:]}"


def _inject_stylesheet(html: str, name: str) -> str:
    asset = STATIC / name
    try:
        revision = str(asset.stat().st_mtime_ns)
    except OSError:
        revision = "1"
    link = f'<link rel="stylesheet" href="/assets/{name}?v={revision}">'
    if name not in html:
        html = html.replace("</head>", f"  {link}\n</head>")
    return html


def _inject_mobile_scroll_unlock(html: str) -> str:
    return _inject_stylesheet(html, "mobile-scroll-unlock.css")


def _is_mobile_route(path: str) -> bool:
    first_segment = path.strip("/").split("/", 1)[0].lower()
    return first_segment == "mobile"


def _mark_mobile_route(html: str) -> str:
    if 'class="mobile-route"' not in html:
        html = html.replace("<body>", '<body class="mobile-route">', 1)
    return html


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema(engine)

    embedded_worker: EmbeddedWorker | None = None
    if get_settings().embedded_worker:
        embedded_worker = EmbeddedWorker()
        embedded_worker.start()

    try:
        yield
    finally:
        if embedded_worker:
            embedded_worker.stop()


app = FastAPI(title="DevPilot API", version=__version__, lifespan=lifespan)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(router)
app.include_router(career_router)
app.include_router(host_action_router)
app.include_router(investia_admin_router)
app.include_router(investia_public_router)
app.include_router(linux_router)
app.include_router(ollama_provider_router)
app.include_router(task_run_router)
app.include_router(task_image_router)
app.include_router(project_provisioning_router)
app.include_router(product_delivery_router)
app.include_router(provider_models_router)
app.include_router(super_admin_voice_router)
app.include_router(cloud_admin_router)
app.include_router(deploy_router)
app.include_router(reports_router)
app.include_router(telemetry_router)
app.include_router(telemetry_replay_router)
app.include_router(voice_conversation_router)
app.include_router(voice_speech_router)
app.include_router(
    voice_transcription_router,
    dependencies=[Depends(require_ai_budget_access)],
)
app.include_router(token_usage_router)
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


@app.get("/health")
def health():
    return {"status": "ok", "service": "devpilot", "version": __version__}


@app.get("/telemetry", include_in_schema=False)
def telemetry_page():
    return FileResponse(
        STATIC / "telemetry.html",
        headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
    )


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    candidate = STATIC / path
    if path and candidate.is_file():
        headers = None
        if candidate.suffix.lower() in {".html", ".htm"}:
            headers = {"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"}
        return FileResponse(candidate, headers=headers)

    mobile_route = _is_mobile_route(path)
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    html = _normalize_index_head(html)
    if mobile_route:
        html = _mark_mobile_route(html)

    scripts = [
        '<script src="/assets/acs-loader.js" defer></script>',
        '<script src="/assets/telemetry-capture.js" defer></script>',
        '<script src="/assets/telemetry-replay-capture.js" defer></script>',
        '<script src="/assets/profile.js" defer></script>',
        '<script src="/assets/auth-ui.js" defer></script>',
        '<script src="/assets/users.js" defer></script>',
        '<script src="/assets/token-usage.js" defer></script>',
        '<script src="/assets/token-usage-mobile-fix.js" defer></script>',
        '<script src="/assets/provider-models.js" defer></script>',
        '<script src="/assets/provider-ollama.js" defer></script>',
        '<script src="/assets/super-admin-voice.js" defer></script>',
        '<script src="/assets/project-provisioning.js" defer></script>',
        '<script src="/assets/product-delivery-ui.js" defer></script>',
        '<script src="/assets/voice-project-start.js" defer></script>',
        '<script src="/assets/voice-local-update.js" defer></script>',
        '<script src="/assets/voice-microphone-permission.js" defer></script>',
        '<script src="/assets/voice-playback.js" defer></script>',
        '<script src="/assets/voice-enhanced-ui.js" defer></script>',
        '<script src="/assets/voice-chatgpt-layout.js" defer></script>',
        '<script src="/assets/voice-insecure-lan-guard.js" defer></script>',
        '<script src="/assets/task-failures.js" defer></script>',
        '<script src="/assets/task-image-upload.js" defer></script>',
        '<script src="/assets/consolidated-ui.js" defer></script>',
        '<script src="/assets/tasks-lazy-load.js" defer></script>',
        '<script src="/assets/workspace-skins.js" defer></script>',
        '<script src="/assets/analysis-commercial-proposal.js" defer></script>',
        '<script src="/assets/analysis-failure-actions.js" defer></script>',
        '<script src="/assets/analysis-incomplete-commercial.js" defer></script>',
        '<script src="/assets/organization-normalization-ui.js" defer></script>',
        '<script src="/assets/mobile-project-card-compact.js" defer></script>',
        '<script src="/assets/example-project.js" defer></script>',
        '<script src="/assets/repeatai-analysis-scroll.js" defer></script>',
        '<script src="/assets/repeatai-live-graphs.js" defer></script>',
        '<script src="/assets/repeatai-dashboard-graphs.js" defer></script>',
        '<script src="/assets/repeatai-pattern-graphs.js" defer></script>',
        '<script src="/assets/approval-slider.js" defer></script>',
        '<script src="/assets/tws-example.js" defer></script>',
        '<script src="/assets/deploy-admin.js" defer></script>',
        '<script src="/assets/cloud-admin.js" defer></script>',
        '<script src="/assets/investia-admin.js" defer></script>',
        '<script src="/assets/investia-homologation.js" defer></script>',
        '<script src="/assets/career-linkedin.js" defer></script>',
        '<script src="/assets/ui-literal-newline-cleanup.js" defer></script>',
        '<script src="/assets/linux-terminal.js" defer></script>',
    ]
    for script in scripts:
        if script not in html:
            html = html.replace("</body>", f"  {script}\n</body>")

    html = _inject_stylesheet(html, "super-admin-voice.css")
    html = _inject_mobile_scroll_unlock(html)
    if mobile_route:
        html = _inject_stylesheet(html, "mobile-route.css")
    html = _version_frontend_scripts(html)
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store, max-age=0, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Permissions-Policy": "microphone=(self)",
            "Feature-Policy": "microphone 'self'",
        },
    )
