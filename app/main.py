from contextlib import asynccontextmanager
from pathlib import Path
import json
import re

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401
from app.ai_budget_dependency import require_ai_budget_access
from app.api import router
from app.audit_routes import router as audit_router
from app.auth_routes import router as auth_router
from app.career_routes import router as career_router
from app.chat_mode_routes import router as chat_mode_router
from app.cloud_admin_routes import router as cloud_admin_router
from app.config import get_settings
from app.delivery_url_recovery import install_delivery_url_recovery
from app.deploy_routes import router as deploy_router
from app.embedded_worker import EmbeddedWorker
from app.frontend_ui_routes import router as frontend_ui_router
from app.host_action_routes import router as host_action_router
from app.investia_admin_routes import router as investia_admin_router
from app.investia_public_routes import router as investia_public_router
from app.linux_routes import router as linux_router
from app.local_test_routes import router as local_test_router
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
from app.voice_all_provider_routes import router as voice_conversation_router
from app.voice_speech_routes import router as voice_speech_router
from app.voice_transcription_routes import router as voice_transcription_router
from app.db import Base, engine
from app.services.ollama_voice_bridge import install_voice_ollama_bridge
from app.services.schema import ensure_runtime_schema


install_delivery_url_recovery()
install_voice_ollama_bridge()

STATIC = Path(__file__).parent / "static"
_SCRIPT_SRC_RE = re.compile(
    r'(?P<prefix><script\s+src="/assets/(?P<name>[^"?]+\.js))(?:\?v=[^"]+)?(?P<suffix>"[^>]*></script>)'
)
_SCRIPT_TAG_RE = re.compile(
    r'\s*<script\s+[^>]*src="/assets/(?P<name>[^"?]+\.js)(?:\?[^"]*)?"[^>]*></script>',
    re.IGNORECASE,
)
_PREAUTH_SCRIPT_NAMES = {"acs-loader.js", "auth-ui.js"}

_CORE_AUTHENTICATED_SCRIPTS = [
    "app.js",
    "tasks-lazy-load.js",
    "profile.js",
    "users.js",
    "simplified-nav.js",
    "workspace-skins.js",
]

_DEFERRED_AUTHENTICATED_SCRIPTS = [
    "consolidated-ui.js",
    "project-provisioning.js",
    "project-builder.js",
    "project-description-profile.js",
    "task-modal.js",
    "task-analytics.js",
    "reports.js",
    "example-project.js",
    "example-project-mobile-training.js",
    "example-project-graphs-fix.js",
    "project-ships.js",
    "build-game-cockpit.js",
    "mobile-accordion-menu.js",
    "token-usage.js",
    "token-usage-mobile-fix.js",
    "provider-models.js",
    "provider-ollama.js",
    "super-admin-voice.js",
    "product-delivery-ui.js",
    "voice-project-start.js",
    "voice-local-update.js",
    "voice-microphone-permission.js",
    "voice-playback.js",
    "voice-enhanced-ui.js",
    "voice-chatgpt-layout.js",
    "voice-insecure-lan-guard.js",
    "task-failures.js",
    "task-image-upload.js",
    "analysis-commercial-proposal.js",
    "analysis-failure-actions.js",
    "analysis-incomplete-commercial.js",
    "organization-normalization-ui.js",
    "mobile-project-card-compact.js",
    "repeatai-analysis-scroll.js",
    "repeatai-live-graphs.js",
    "repeatai-dashboard-graphs.js",
    "repeatai-pattern-graphs.js",
    "approval-slider.js",
    "tws-example.js",
    "deploy-admin.js",
    "cloud-admin.js",
    "super-admin-local-test.js",
    "investia-admin.js",
    "investia-homologation.js",
    "career-linkedin.js",
    "ui-literal-newline-cleanup.js",
    "linux-terminal.js",
    "linux-beginner-coach.js",
    "build-game.js",
    "mobile-game-mode.js",
    "game-linux-training.js",
    "audit-integrity.js",
    "mission-control.js",
    "telemetry-capture.js",
    "telemetry-replay-capture.js",
]


def _asset_revision(name: str) -> str:
    try:
        return str((STATIC / name).stat().st_mtime_ns)
    except OSError:
        return "1"


def _version_frontend_scripts(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        revision = _asset_revision(match.group("name"))
        return f'{match.group("prefix")}?v={revision}{match.group("suffix")}'

    return _SCRIPT_SRC_RE.sub(replace, html)


def _has_frontend_script(html: str, name: str) -> bool:
    pattern = re.compile(
        rf'<script\s+[^>]*src="/assets/{re.escape(name)}(?:\?[^"<>]*)?"[^>]*></script>',
        re.IGNORECASE,
    )
    return bool(pattern.search(html))


def _normalize_index_head(html: str) -> str:
    start = html.find("<head>")
    end = html.find("</head>", start)
    if start < 0 or end < 0:
        return html
    head = html[start:end]
    head = head.replace("\\r\\n", "\n").replace("\\n", "\n")
    return f"{html[:start]}{head}{html[end:]}"


def _inject_stylesheet(html: str, name: str) -> str:
    revision = _asset_revision(name)
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


def _strip_boot_runtime_scripts(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        return match.group(0) if name in _PREAUTH_SCRIPT_NAMES else ""
    return _SCRIPT_TAG_RE.sub(replace, html)


def _unique_script_names(names: list[str], seen: set[str] | None = None) -> list[str]:
    result: list[str] = []
    known = set(seen or ())
    for name in names:
        if name in known:
            continue
        known.add(name)
        result.append(name)
    return result


def _script_urls(names: list[str]) -> list[str]:
    return [
        f"/assets/{name}?v={_asset_revision(name)}"
        for name in names
        if (STATIC / name).is_file()
    ]


def _authenticated_script_loader() -> str:
    core_names = _unique_script_names(_CORE_AUTHENTICATED_SCRIPTS, set(_PREAUTH_SCRIPT_NAMES))
    deferred_names = _unique_script_names(
        _DEFERRED_AUTHENTICATED_SCRIPTS,
        set(_PREAUTH_SCRIPT_NAMES) | set(core_names),
    )
    core_urls = json.dumps(_script_urls(core_names), ensure_ascii=False)
    deferred_urls = json.dumps(_script_urls(deferred_names), ensure_ascii=False)

    return f"""<script>
(() => {{
  'use strict';
  const coreSources = {core_urls};
  const deferredSources = {deferred_urls};
  const boot = window.__devpilotBoot = window.__devpilotBoot || {{
    phase: 'waiting', current: null, loaded: [], failed: [], timings: {{}}, startedAt: Date.now()
  }};
  const token = () => String(localStorage.getItem('devpilot-token') || '').trim();
  const tokenExists = () => Boolean(token());
  const sleep = ms => new Promise(resolve => window.setTimeout(resolve, ms));
  const nextPaint = () => new Promise(resolve => requestAnimationFrame(() => resolve()));
  const whenIdle = () => new Promise(resolve => {{
    if ('requestIdleCallback' in window) window.requestIdleCallback(() => resolve(), {{timeout: 2200}});
    else window.setTimeout(resolve, 180);
  }});

  const validateSession = async () => {{
    if (!tokenExists()) return false;
    if (window.__devpilotAuthReady) {{
      try {{ return Boolean(await window.__devpilotAuthReady); }} catch (_) {{ return false; }}
    }}
    try {{
      const response = await fetch('/api/auth/me', {{
        headers: {{Authorization: `Bearer ${{token()}}`}}, cache: 'no-store'
      }});
      if (response.ok) return true;
      if ([401, 403, 404].includes(response.status)) localStorage.removeItem('devpilot-token');
    }} catch (_) {{}}
    return false;
  }};

  const markLegacyProjectShipsLoader = () => {{
    if (document.querySelector('script[data-project-ships-loader="1"]')) return;
    const marker = document.createElement('script');
    marker.type = 'application/json';
    marker.dataset.projectShipsLoader = '1';
    marker.textContent = '{{"managedBy":"devpilot-progressive-boot"}}';
    document.head.appendChild(marker);
  }};

  const loadScript = src => new Promise(resolve => {{
    const absolute = new URL(src, location.href).href;
    const existing = [...document.scripts].find(script => script.src === absolute);
    if (existing) {{
      if (!boot.loaded.includes(src)) boot.loaded.push(src);
      resolve(true);
      return;
    }}
    const started = performance.now();
    boot.current = src;
    const script = document.createElement('script');
    script.src = src;
    script.async = false;
    script.dataset.devpilotProgressive = '1';
    script.onload = () => {{
      boot.timings[src] = Math.round(performance.now() - started);
      boot.loaded.push(src);
      boot.current = null;
      document.dispatchEvent(new CustomEvent('devpilot:asset-loaded', {{detail: {{src}}}}));
      resolve(true);
    }};
    script.onerror = () => {{
      boot.timings[src] = Math.round(performance.now() - started);
      boot.failed.push(src);
      boot.current = null;
      resolve(false);
    }};
    document.body.appendChild(script);
  }});

  const loadCore = async () => {{
    boot.phase = 'core';
    for (const src of coreSources) {{
      if (!tokenExists()) return false;
      await loadScript(src);
      await nextPaint();
    }}
    boot.phase = 'interactive';
    document.dispatchEvent(new CustomEvent('devpilot:authenticated-core-ready'));
    return true;
  }};

  const loadDeferred = async () => {{
    await sleep(1400);
    boot.phase = 'deferred';
    for (const src of deferredSources) {{
      if (!tokenExists()) break;
      while (document.hidden && tokenExists()) await sleep(1200);
      await whenIdle();
      await loadScript(src);
      await nextPaint();
      await sleep(120);
    }}
    boot.phase = 'ready';
    boot.finishedAt = Date.now();
    document.dispatchEvent(new CustomEvent('devpilot:authenticated-ui-ready'));
  }};

  const start = async () => {{
    if (boot.phase !== 'waiting') return;
    boot.phase = 'auth';
    const authenticated = await validateSession();
    boot.authenticated = authenticated;
    if (!authenticated) {{
      boot.phase = 'waiting-login';
      return;
    }}
    markLegacyProjectShipsLoader();
    const coreReady = await loadCore();
    if (coreReady) void loadDeferred();
  }};

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {{once: true}});
  else void start();
}})();
</script>"""


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
app.include_router(frontend_ui_router)
app.include_router(router)
app.include_router(audit_router)
app.include_router(career_router)
app.include_router(chat_mode_router)
app.include_router(host_action_router)
app.include_router(investia_admin_router)
app.include_router(investia_public_router)
app.include_router(linux_router)
app.include_router(local_test_router)
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
app.include_router(voice_transcription_router, dependencies=[Depends(require_ai_budget_access)])
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
    html = _strip_boot_runtime_scripts(html)
    if mobile_route:
        html = _mark_mobile_route(html)

    acs_script = '<script src="/assets/acs-loader.js" defer></script>'
    auth_script = '<script src="/assets/auth-ui.js" defer></script>'
    if not _has_frontend_script(html, "acs-loader.js"):
        html = html.replace("</body>", f"  {acs_script}\n</body>")
    if not _has_frontend_script(html, "auth-ui.js"):
        html = html.replace("</body>", f"  {auth_script}\n</body>")
    html = html.replace("</body>", f"  {_authenticated_script_loader()}\n</body>")

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
        },
    )