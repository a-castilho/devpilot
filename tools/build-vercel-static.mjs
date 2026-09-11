import { createHash } from 'node:crypto';
import { cpSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const source = 'app/static';
const output = '.vercel-static';
const assetsOutput = join(output, 'assets');
const gameOutput = join(output, 'game');

const PREAUTH_SCRIPTS = ['acs-loader.js', 'auth-ui.js'];
const CORE_SCRIPTS = ['app.js', 'feature-loader.js'];
const DEFERRED_SCRIPTS = [
  'consolidated-ui.js','project-delete-ui.js','project-provisioning.js','project-builder.js','project-description-profile.js',
  'task-modal.js','task-completion-documentation.js','task-analytics.js','reports.js','example-project.js',
  'example-project-mobile-training.js','example-project-graphs-fix.js','project-ships.js','build-game-cockpit.js','mobile-accordion-menu.js',
  'token-usage.js','token-usage-mobile-fix.js','provider-models.js','provider-ollama.js','super-admin-voice.js','product-delivery-ui.js',
  'voice-project-start.js','voice-local-update.js','voice-microphone-permission.js','voice-playback.js','voice-enhanced-ui.js',
  'voice-chatgpt-layout.js','voice-insecure-lan-guard.js','task-failures.js','task-image-upload.js','analysis-commercial-proposal.js',
  'analysis-failure-actions.js','analysis-incomplete-commercial.js','organization-normalization-ui.js','mobile-project-card-compact.js',
  'repeatai-analysis-scroll.js','repeatai-live-graphs.js','repeatai-dashboard-graphs.js','repeatai-pattern-graphs.js','approval-slider.js',
  'tws-example.js','deploy-admin.js','cloud-admin.js','super-admin-local-test.js','investia-admin.js','investia-homologation.js','career-linkedin.js',
  'ui-literal-newline-cleanup.js','linux-terminal.js','linux-beginner-coach.js','build-game.js','mobile-game-mode.js','game-linux-training.js',
  'audit-integrity.js','mission-control.js','telemetry-capture.js','telemetry-replay-capture.js','viewport-adaptive-v15.js','page-navigation-v26.js',
  'dashboard-user-v21.js','executions-v18.js','executions-focus-v19.js','simplified-nav.js','profile.js','users.js','tasks-operational-ui.js',
  'task-recovery-flow.js','tasks-recovery-layout-v41.js','execution-results-v28.js','mobile-voice-capture-final.js','voice-project-autoload.js',
  'mobile-chat-project-picker.js','voice-runtime-stability.js','chat-request-watchdog.js','super-admin-task-panel.js','game-rules-admin.js',
  'rag-admin-ui.js','rag-jobs-ui.js','game-weapons.js'
];
const stylesheets = ['mobile-scroll-unlock.css', 'super-admin-voice.css'];

function revision(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex').slice(0, 12);
}
function assetPath(name) { return join(source, name); }
function requireAsset(name) {
  const path = assetPath(name);
  try { statSync(path); } catch { throw new Error(`Vercel build requires missing frontend asset: ${name}`); }
  return path;
}
function normalizeHead(value) {
  return value.replace(/<head>[\s\S]*?<\/head>/, head => head.replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n'));
}
function removeLegacyBootstrapFallback(value) {
  const legacy = /<dialog id="auth-modal"><form method="dialog" class="modal"><span class="eyebrow">ACESSO<\/span><h2>Conectar ao DevPilot<\/h2><p>Informe o token configurado em <code>DEVPILOT_BOOTSTRAP_TOKEN<\/code>\.<\/p><label>Token<input id="token" type="password" autocomplete="current-password" required><\/label><button class="primary" id="save-token" value="default">Entrar<\/button><\/form><\/dialog>/;
  const safe = '<dialog id="auth-modal" data-devpilot-auth-loading="true"><div class="modal" role="status" aria-live="polite"><span class="eyebrow">ACESSO</span><h2>Carregando DevPilot…</h2><p>Validando sua sessão e o estado da homologação.</p></div></dialog>';
  if (!legacy.test(value)) throw new Error('Vercel build could not locate legacy bootstrap fallback in index.html');
  return value.replace(legacy, safe);
}
function stripRuntimeScripts(value) {
  return value.replace(/\s*<script\s+[^>]*src="\/assets\/([^"?]+\.js)(?:\?[^\"]*)?"[^>]*><\/script>/gi, '');
}
function preauthTags() {
  return PREAUTH_SCRIPTS.map(name => {
    const path = requireAsset(name);
    return `  <script src="/assets/${name}?v=${revision(path)}" defer></script>`;
  }).join('\n');
}
function authenticatedLoader() {
  CORE_SCRIPTS.forEach(requireAsset);
  DEFERRED_SCRIPTS.forEach(requireAsset);
  const coreSources = CORE_SCRIPTS.map(name => `/assets/${name}?v=${revision(assetPath(name))}`);
  const assetRevisions = Object.fromEntries(DEFERRED_SCRIPTS.map(name => [name, revision(assetPath(name))]));
  return `  <script>
(() => {
  'use strict';
  const coreSources = ${JSON.stringify(coreSources)};
  window.__devpilotAssetRevisions = Object.freeze(${JSON.stringify(assetRevisions)});
  const boot = window.__devpilotBoot = {phase:'auth',current:null,loaded:[],failed:[],timings:{},startedAt:Date.now()};
  const token = () => String(localStorage.getItem('devpilot-token') || '').trim();
  const waitForAuthentication = async () => {
    if (window.__devpilotAuthReady) {
      try { return Boolean(await window.__devpilotAuthReady); } catch (_) { return false; }
    }
    if (!token()) return false;
    try {
      const response = await fetch('/api/auth/me', {headers:{Authorization:'Bearer ' + token()},cache:'no-store'});
      return response.ok;
    } catch (_) { return false; }
  };
  const loadScript = src => new Promise(resolve => {
    const absolute = new URL(src, location.href).href;
    const existing = Array.from(document.scripts).find(script => script.src === absolute);
    if (existing) { if (!boot.loaded.includes(src)) boot.loaded.push(src); resolve(true); return; }
    const started = performance.now();
    boot.current = src;
    const script = document.createElement('script');
    script.src = src; script.async = false; script.dataset.devpilotCore = '1';
    script.onload = () => { boot.timings[src] = Math.round(performance.now() - started); boot.loaded.push(src); boot.current = null; resolve(true); };
    script.onerror = () => { boot.timings[src] = Math.round(performance.now() - started); boot.failed.push(src); boot.current = null; resolve(false); };
    document.body.appendChild(script);
  });
  const start = async () => {
    const authenticated = await waitForAuthentication();
    boot.authenticated = authenticated;
    if (!authenticated || !token()) { boot.phase = 'waiting-login'; return; }
    boot.phase = 'core';
    for (const src of coreSources) {
      if (!token()) { boot.phase = 'logged-out'; return; }
      if (!(await loadScript(src))) { boot.phase = 'failed'; return; }
    }
    boot.phase = 'ready'; boot.finishedAt = Date.now();
    document.dispatchEvent(new CustomEvent('devpilot:authenticated-core-ready'));
    document.dispatchEvent(new CustomEvent('devpilot:authenticated-ui-ready'));
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => void start(), {once:true});
  else void start();
})();
</script>`;
}

rmSync(output, {recursive:true, force:true});
mkdirSync(output, {recursive:true});
cpSync(source, assetsOutput, {recursive:true});
mkdirSync(gameOutput, {recursive:true});
cpSync(join(source, 'game', 'index.html'), join(gameOutput, 'index.html'));

let html = normalizeHead(readFileSync(join(source, 'index.html'), 'utf8'));
html = removeLegacyBootstrapFallback(html);
html = stripRuntimeScripts(html);
for (const name of stylesheets) {
  const path = requireAsset(name);
  if (!html.includes(`/assets/${name}`)) html = html.replace('</head>', `  <link rel="stylesheet" href="/assets/${name}?v=${revision(path)}">\n</head>`);
}
html = html.replace('</body>', `${preauthTags()}\n${authenticatedLoader()}\n</body>`);

if (html.includes('DEVPILOT_BOOTSTRAP_TOKEN') || html.includes('id="save-token"')) throw new Error('Vercel build must never publish the legacy bootstrap-token login form');
if (!html.includes('data-devpilot-auth-loading="true"')) throw new Error('Vercel build must publish a detectable initial auth loading placeholder');
if ((html.match(/\/assets\/app\.js/g) || []).length !== 1) throw new Error('Vercel build must load app.js exactly once and only after authentication');
if ((html.match(/\/assets\/feature-loader\.js/g) || []).length !== 1) throw new Error('Vercel build must load feature-loader.js exactly once and only after authentication');

writeFileSync(join(output, 'index.html'), html);
console.log('DevPilot Vercel frontend built with authenticated runtime parity');
