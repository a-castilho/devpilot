from contextlib import asynccontextmanager
from pathlib import Path
import json
import re

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401
import app.platform_models  # noqa: F401
from app.ai_budget_dependency import require_ai_budget_access
from app.api import router
from app.audit_routes import router as audit_router
from app.auth_routes import router as auth_router
from app.career_routes import router as career_router
from app.chat_control_routes import require_chat_available, router as chat_control_router
from app.chat_mode_routes import router as chat_mode_router
from app.cloud_admin_routes import router as cloud_admin_router
from app.config import get_settings
from app.delivery_url_recovery import install_delivery_url_recovery
from app.deploy_routes import router as deploy_router
from app.embedded_worker import EmbeddedWorker
from app.host_action_routes import router as host_action_router
from app.investia_admin_routes import router as investia_admin_router
from app.investia_public_routes import router as investia_public_router
from app.linux_routes import router as linux_router
from app.local_test_routes import router as local_test_router
from app.ollama_provider_routes import router as ollama_provider_router
from app.product_delivery_routes import router as product_delivery_router
from app.project_connect_routes import router as project_connect_router
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
_PREAUTH_SCRIPT_NAMES = {"app.js", "auth-ui.js"}

# Keep the authenticated shell intentionally small. Optional features are no
# longer all booted simply because a token exists: they are loaded by active
# view or explicit interaction so low-RAM browsers keep their main thread free.
_CORE_AUTHENTICATED_SCRIPTS = [
    "super-admin-chat-control.js",
    "profile.js",
    "users.js",
    "consolidated-ui.js",
    "workspace-skins.js",
    "simplified-nav.js",
]

_VIEW_AUTHENTICATED_SCRIPTS = {
    "organizations": [
        "organization-normalization-ui.js",
    ],
    "projects": [
        "project-provisioning.js",
        "project-builder.js",
        "project-description-profile.js",
        "project-ships.js",
        "mobile-project-card-compact.js",
        "product-delivery-ui.js",
    ],
    "tasks": [
        "task-modal.js",
        "task-analytics.js",
        "task-failures.js",
        "task-image-upload.js",
        "tasks-lazy-load.js",
        "analysis-commercial-proposal.js",
        "analysis-failure-actions.js",
        "analysis-incomplete-commercial.js",
        "approval-slider.js",
    ],
    "providers": [
        "provider-models.js",
        "provider-ollama.js",
    ],
    "reports": [
        "reports.js",
    ],
    "audit": [
        "audit-integrity.js",
    ],
}

_FEATURE_AUTHENTICATED_SCRIPTS = {
    "example": [
        "example-project.js",
        "example-project-mobile-training.js",
        "example-project-graphs-fix.js",
        "repeatai-analysis-scroll.js",
        "repeatai-live-graphs.js",
        "repeatai-dashboard-graphs.js",
        "repeatai-pattern-graphs.js",
        "tws-example.js",
    ],
    "voice": [
        "super-admin-voice.js",
        "voice-project-start.js",
        "voice-local-update.js",
        "voice-microphone-permission.js",
        "voice-playback.js",
        "voice-enhanced-ui.js",
        "voice-chatgpt-layout.js",
        "voice-insecure-lan-guard.js",
    ],
    "game": [
        "build-game-cockpit.js",
        "build-game.js",
        "mobile-game-mode.js",
        "game-linux-training.js",
        "mission-control.js",
        "system-tests.js",
        "build-game-subphases.js",
        "build-game-new-session.js",
        "build-game-url-bonus.js",
        "build-game-weapons.js",
    ],
}

# These modules create secondary admin/navigation capabilities or background
# observability. They wait for real user interaction instead of competing with
# first paint and authentication.
_INTERACTION_AUTHENTICATED_SCRIPTS = [
    "token-usage.js",
    "token-usage-mobile-fix.js",
    "deploy-admin.js",
    "cloud-admin.js",
    "super-admin-local-test.js",
    "investia-admin.js",
    "investia-homologation.js",
    "career-linkedin.js",
    "linux-terminal.js",
    "linux-beginner-coach.js",
    "telemetry-capture.js",
    "telemetry-replay-capture.js",
]

_MOBILE_SHELL_AUTHENTICATED_SCRIPTS = [
    "mobile-accordion-menu.js",
    "ui-literal-newline-cleanup.js",
]

# Compatibility export used by tests and older integrations. This remains a
# complete inventory, but the loader no longer iterates over it automatically.
_DEFERRED_AUTHENTICATED_SCRIPTS = [
    *[name for names in _VIEW_AUTHENTICATED_SCRIPTS.values() for name in names],
    *[name for names in _FEATURE_AUTHENTICATED_SCRIPTS.values() for name in names],
    *_INTERACTION_AUTHENTICATED_SCRIPTS,
    *_MOBILE_SHELL_AUTHENTICATED_SCRIPTS,
]

_CHAT_AUTHENTICATED_SCRIPTS = {
    "super-admin-voice.js",
    "voice-project-start.js",
    "voice-local-update.js",
    "voice-microphone-permission.js",
    "voice-playback.js",
    "voice-enhanced-ui.js",
    "voice-chatgpt-layout.js",
    "voice-insecure-lan-guard.js",
}


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


def _strip_pre_auth_heavy_scripts(html: str) -> str:
    """Keep login boot tiny; authenticated features are loaded after a valid token exists."""

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


def _script_group_urls(groups: dict[str, list[str]]) -> dict[str, list[str]]:
    return {
        group: _script_urls(_unique_script_names(names, set(_PREAUTH_SCRIPT_NAMES)))
        for group, names in groups.items()
    }


def _authenticated_script_loader() -> str:
    core_names = _unique_script_names(_CORE_AUTHENTICATED_SCRIPTS, set(_PREAUTH_SCRIPT_NAMES))
    core_urls = json.dumps(_script_urls(core_names), ensure_ascii=False)
    view_urls = json.dumps(_script_group_urls(_VIEW_AUTHENTICATED_SCRIPTS), ensure_ascii=False)
    feature_urls = json.dumps(_script_group_urls(_FEATURE_AUTHENTICATED_SCRIPTS), ensure_ascii=False)
    interaction_urls = json.dumps(
        _script_urls(_unique_script_names(_INTERACTION_AUTHENTICATED_SCRIPTS, set(_PREAUTH_SCRIPT_NAMES))),
        ensure_ascii=False,
    )
    mobile_shell_urls = json.dumps(
        _script_urls(_unique_script_names(_MOBILE_SHELL_AUTHENTICATED_SCRIPTS, set(_PREAUTH_SCRIPT_NAMES))),
        ensure_ascii=False,
    )
    chat_urls = json.dumps(_script_urls(sorted(_CHAT_AUTHENTICATED_SCRIPTS)), ensure_ascii=False)

    return f"""<script>
(() => {{
  'use strict';
  const coreSources = {core_urls};
  const viewGroups = {view_urls};
  const featureGroups = {feature_urls};
  const interactionSources = {interaction_urls};
  const mobileShellSources = {mobile_shell_urls};
  const chatSources = new Set({chat_urls});
  const groupPromises = new Map();
  const boot = window.__devpilotBoot = window.__devpilotBoot || {{
    phase: 'waiting',
    loaded: [],
    failed: [],
    skipped: [],
    groups: [],
    startedAt: Date.now()
  }};

  const tokenExists = () => Boolean(localStorage.getItem('devpilot-token'));
  const sleep = ms => new Promise(resolve => window.setTimeout(resolve, ms));
  const nextPaint = () => new Promise(resolve => requestAnimationFrame(() => resolve()));
  const whenIdle = () => new Promise(resolve => {{
    if ('requestIdleCallback' in window) {{
      window.requestIdleCallback(() => resolve(), {{timeout: 1800}});
    }} else {{
      window.setTimeout(resolve, 180);
    }}
  }});

  const currentView = () => {{
    const active = document.querySelector('.view.active');
    return active?.id?.replace(/-view$/, '') || 'overview';
  }};

  const markLegacyProjectShipsLoader = () => {{
    if (document.querySelector('script[data-project-ships-loader="1"]')) return;
    const marker = document.createElement('script');
    marker.type = 'application/json';
    marker.dataset.projectShipsLoader = '1';
    marker.textContent = '{{"managedBy":"devpilot-boot"}}';
    document.head.appendChild(marker);
  }};

  const sameAsset = (script, src) => {{
    if (!script.src) return false;
    try {{
      const current = new URL(script.src, location.href);
      const expected = new URL(src, location.href);
      return current.pathname === expected.pathname;
    }} catch (_) {{
      return false;
    }}
  }};

  const loadScript = src => new Promise(resolve => {{
    const existing = [...document.scripts].find(script => sameAsset(script, src));
    if (existing) {{
      if (!boot.loaded.includes(src)) boot.loaded.push(src);
      resolve(true);
      return;
    }}

    if (chatSources.has(src) && boot.chatEnabled === false) {{
      boot.skipped.push(src);
      resolve(true);
      return;
    }}

    const script = document.createElement('script');
    script.src = src;
    script.async = false;
    script.dataset.devpilotLazy = 'authenticated';
    script.onload = () => {{
      boot.loaded.push(src);
      document.dispatchEvent(new CustomEvent('devpilot:asset-loaded', {{detail: {{src}}}}));
      resolve(true);
    }};
    script.onerror = () => {{
      boot.failed.push(src);
      resolve(false);
    }};
    document.body.appendChild(script);
  }});

  const loadGroup = (name, sources, gap = 150) => {{
    if (!sources?.length) return Promise.resolve(true);
    if (groupPromises.has(name)) return groupPromises.get(name);

    const promise = (async () => {{
      for (const src of sources) {{
        if (!tokenExists()) return false;
        while (document.hidden && tokenExists()) await sleep(900);
        await whenIdle();
        await loadScript(src);
        await nextPaint();
        await sleep(gap);
      }}
      if (!boot.groups.includes(name)) boot.groups.push(name);
      document.dispatchEvent(new CustomEvent('devpilot:asset-group-ready', {{detail: {{name}}}}));
      return true;
    }})();

    groupPromises.set(name, promise);
    return promise;
  }};

  const resolveChatControl = async () => {{
    const chatControl = window.__devpilotChatControl;
    if (chatControl?.ready) {{
      try {{ await chatControl.ready; }} catch (_) {{}}
    }}
    boot.chatEnabled = Boolean(window.__devpilotChatControl?.enabled);
  }};

  const loadCore = async () => {{
    boot.phase = 'core';
    for (const src of coreSources) {{
      if (!tokenExists()) return false;
      await loadScript(src);
      await nextPaint();
      await sleep(40);
    }}
    await resolveChatControl();
    boot.phase = 'interactive';
    document.dispatchEvent(new CustomEvent('devpilot:authenticated-core-ready'));
    return true;
  }};

  const loadView = view => loadGroup(`view:${{view}}`, viewGroups[view] || [], 120);
  const loadFeature = feature => loadGroup(`feature:${{feature}}`, featureGroups[feature] || [], 220);

  const featureFromTarget = target => {{
    if (!target) return '';
    if (target.closest('[data-example-project]')) return 'example';
    if (target.closest('#voice-hero, #voice-dock, #voice-start, [data-voice-action]')) return 'voice';
    if (target.closest('.project-ship-play, [data-build-game], [data-game-mode], [data-open-game]')) return 'game';
    return '';
  }};

  document.addEventListener('click', event => {{
    const target = event.target instanceof Element ? event.target : null;
    const viewTarget = target?.closest('[data-view]');
    const view = viewTarget?.dataset?.view;
    if (view && viewGroups[view]) void loadView(view);

    const feature = featureFromTarget(target);
    if (!feature || !featureGroups[feature]) return;
    const groupName = `feature:${{feature}}`;
    if (boot.groups.includes(groupName)) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    const replayTarget = target.closest(
      '[data-example-project], #voice-hero, #voice-dock, #voice-start, [data-voice-action], ' +
      '.project-ship-play, [data-build-game], [data-game-mode], [data-open-game]'
    );
    void loadFeature(feature).then(() => replayTarget?.click());
  }}, true);

  let interactionQueueStarted = false;
  const startInteractionQueue = () => {{
    if (interactionQueueStarted || !tokenExists()) return;
    interactionQueueStarted = true;
    window.setTimeout(() => {{
      void loadGroup('interaction', interactionSources, 400);
    }}, 6000);
  }};

  ['pointerdown', 'touchstart', 'keydown'].forEach(type => {{
    window.addEventListener(type, startInteractionQueue, {{once: true, passive: true}});
  }});

  const start = async () => {{
    if (!tokenExists() || boot.phase !== 'waiting') return;
    markLegacyProjectShipsLoader();
    const coreReady = await loadCore();
    if (!coreReady) return;

    if (document.body.classList.contains('mobile-route')) {{
      await loadGroup('mobile-shell', mobileShellSources, 160);
    }}

    await loadView(currentView());
    boot.phase = 'ready';
    boot.finishedAt = Date.now();
    document.dispatchEvent(new CustomEvent('devpilot:authenticated-ui-ready'));
  }};

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', start, {{once: true}});
  }} else {{
    void start();
  }}
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
app.include_router(router)
app.include_router(audit_router)
app.include_router(career_router)
app.include_router(chat_control_router)
app.include_router(chat_mode_router, dependencies=[Depends(require_chat_available)])
app.include_router(host_action_router)
app.include_router(investia_admin_router)
app.include_router(investia_public_router)
app.include_router(linux_router)
app.include_router(local_test_router)
app.include_router(ollama_provider_router)
app.include_router(task_run_router)
app.include_router(task_image_router)
app.include_router(project_connect_router)
app.include_router(project_provisioning_router)
app.include_router(product_delivery_router)
app.include_router(provider_models_router)
app.include_router(super_admin_voice_router)
app.include_router(cloud_admin_router)
app.include_router(deploy_router)
app.include_router(reports_router)
app.include_router(telemetry_router)
app.include_router(telemetry_replay_router)
app.include_router(voice_conversation_router, dependencies=[Depends(require_chat_available)])
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
    html = _strip_pre_auth_heavy_scripts(html)
    if mobile_route:
        html = _mark_mobile_route(html)

    auth_script = '<script src="/assets/auth-ui.js" defer></script>'
    if not _has_frontend_script(html, "auth-ui.js"):
        html = html.replace("</body>", f"  {auth_script}\n</body>")
    html = html.replace("</body>", f"  {_authenticated_script_loader()}\n</body>")

    html = _inject_stylesheet(html, "super-admin-voice.css")
    html = _inject_mobile_scroll_unlock(html)
    html = _inject_stylesheet(html, "frontend-performance.css")
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
