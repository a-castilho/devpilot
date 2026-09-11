import { createHash } from 'node:crypto';
import { cpSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const source = 'app/static';
const output = '.vercel-static';
const assetsOutput = join(output, 'assets');
const gameOutput = join(output, 'game');

rmSync(output, { recursive: true, force: true });
mkdirSync(output, { recursive: true });
cpSync(source, assetsOutput, { recursive: true });

// The dashboard navigates to /game/index.html. Publish that document at the
// matching root-level path instead of relying on the assets copy/fallback.
mkdirSync(gameOutput, { recursive: true });
cpSync(join(source, 'game', 'index.html'), join(gameOutput, 'index.html'));

const scripts = [
  'telemetry-capture.js',
  'profile.js',
  'auth-ui.js',
  'users.js',
  'provider-models.js',
  'super-admin-voice.js',
  'project-provisioning.js',
  'voice-project-start.js',
  'voice-local-update.js',
  'voice-microphone-permission.js',
  'voice-browser-compat.js',
  'voice-playback.js',
  'voice-enhanced-ui.js',
  'voice-chatgpt-layout.js',
  'voice-insecure-lan-guard.js',
  'task-failures.js',
  'task-image-upload.js',
  'consolidated-ui.js',
  'workspace-skins.js',
  'analysis-failure-actions.js',
  'organization-normalization-ui.js',
  'mobile-project-card-compact.js',
  'example-project.js',
  'repeatai-analysis-scroll.js',
  'repeatai-live-graphs.js',
  'repeatai-pattern-graphs.js',
  'approval-slider.js',
  'tws-example.js',
  'cloud-admin.js',
  'linux-terminal.js',
  'linux-game-access.js',
  'linux-update-command.js',
  'audit-integrity.js',
  'mission-control.js',
];

const stylesheets = [
  'mobile-scroll-unlock.css',
  'super-admin-voice.css',
];

function revision(path) {
  const content = readFileSync(path);
  return createHash('sha256').update(content).digest('hex').slice(0, 12);
}

function normalizeHead(value) {
  return value.replace(/<head>[\s\S]*?<\/head>/, head => head.replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n'));
}

function removeLegacyBootstrapFallback(value) {
  const legacy = /<dialog id="auth-modal"><form method="dialog" class="modal"><span class="eyebrow">ACESSO<\/span><h2>Conectar ao DevPilot<\/h2><p>Informe o token configurado em <code>DEVPILOT_BOOTSTRAP_TOKEN<\/code>\.<\/p><label>Token<input id="token" type="password" autocomplete="current-password" required><\/label><button class="primary" id="save-token" value="default">Entrar<\/button><\/form><\/dialog>/;
  const safe = '<dialog id="auth-modal"><div class="modal" role="status" aria-live="polite"><span class="eyebrow">ACESSO</span><h2>Carregando DevPilot…</h2><p>Validando sua sessão e o estado da homologação.</p></div></dialog>';
  if (!legacy.test(value)) {
    throw new Error('Vercel build could not locate legacy bootstrap fallback in index.html');
  }
  return value.replace(legacy, safe);
}

let html = normalizeHead(readFileSync(join(source, 'index.html'), 'utf8'));
html = removeLegacyBootstrapFallback(html);

for (const name of scripts) {
  const assetPath = join(source, name);
  try {
    statSync(assetPath);
  } catch {
    throw new Error(`Vercel build requires missing frontend asset: ${name}`);
  }

  if (!html.includes(`/assets/${name}`)) {
    const tag = `<script src="/assets/${name}?v=${revision(assetPath)}" defer></script>`;
    html = html.replace('</body>', `  ${tag}\n</body>`);
  }
}

for (const name of stylesheets) {
  const assetPath = join(source, name);
  try {
    statSync(assetPath);
  } catch {
    throw new Error(`Vercel build requires missing frontend asset: ${name}`);
  }

  if (!html.includes(`/assets/${name}`)) {
    const tag = `<link rel="stylesheet" href="/assets/${name}?v=${revision(assetPath)}">`;
    html = html.replace('</head>', `  ${tag}\n</head>`);
  }
}

if (html.includes('DEVPILOT_BOOTSTRAP_TOKEN') || html.includes('id="save-token"')) {
  throw new Error('Vercel build must never publish the legacy bootstrap-token login form');
}

writeFileSync(join(output, 'index.html'), html);
console.log(`DevPilot Vercel frontend built at ${output}`);