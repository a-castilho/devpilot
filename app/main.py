from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401
from app.api import router
from app.auth_routes import router as auth_router
from app.host_action_routes import router as host_action_router
from app.project_provisioning_routes import router as project_provisioning_router
from app.provider_models_routes import router as provider_models_router
from app.task_run_routes import router as task_run_router
from app.user_routes import router as users_router
from app.reports import router as reports_router
from app.telemetry import router as telemetry_router
from app.db import Base, engine
from app.services.schema import ensure_runtime_schema


STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema(engine)
    yield


app = FastAPI(title="DevPilot API", version="1.0.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(router)
app.include_router(host_action_router)
app.include_router(task_run_router)
app.include_router(project_provisioning_router)
app.include_router(provider_models_router)
app.include_router(reports_router)
app.include_router(telemetry_router)
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


@app.get("/health")
def health():
    return {"status": "ok", "service": "devpilot", "version": "1.0.0"}


@app.get("/telemetry", include_in_schema=False)
def telemetry_page():
    return FileResponse(STATIC / "telemetry.html")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    candidate = STATIC / path
    if path and candidate.is_file():
        return FileResponse(candidate)
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    scripts = [
        '<script src="/assets/telemetry-capture.js" defer></script>',
        '<script src="/assets/profile.js" defer></script>',
        '<script src="/assets/auth-ui.js" defer></script>',
        '<script src="/assets/users.js" defer></script>',
        '<script src="/assets/provider-models.js" defer></script>',
        '<script src="/assets/project-provisioning.js" defer></script>',
        '<script src="/assets/voice-project-start.js" defer></script>',
        '<script src="/assets/task-failures.js" defer></script>',
        '<script src="/assets/example-project.js" defer></script>',
    ]
    for script in scripts:
        if script not in html:
            html = html.replace("</body>", f"  {script}\n</body>")
    return HTMLResponse(html)
