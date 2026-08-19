from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401
from app.api import router
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
app.include_router(router)
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
    capture_script = '<script src="/assets/telemetry-capture.js" defer></script>'
    if capture_script not in html:
        html = html.replace("</body>", f"  {capture_script}\n</body>")
    return HTMLResponse(html)
