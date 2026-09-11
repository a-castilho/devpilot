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

// Nunca publique uma segunda cópia navegável do shell legado em /assets/index.html.
rmSync(join(assetsOutput, 'index.html'), { force: true });

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

function removeLegacyBootstrapTokenFallback(value) {
  const safeAuthShell = `<dialog id="auth-modal"><div class="modal"><span class="eyebrow">ACESSO</span><h2>Preparando acesso seguro…</h2><p>Carregando autenticação por e-mail e senha.</p></div></dialog>`;
  const next = value.replace(/<dialog id="auth-modal">[\s\S]*?<\/dialog>/, safeAuthShell);
  if (next === value) {
    throw new Error('Vercel build could not replace the legacy authentication fallback');
  }
  return next;
}

function hardenCopiedAuthRuntime() {
  const authPath = join(assetsOutput, 'auth-ui.js');
  const current = readFileSync(authPath, 'utf8');
  const legacyGuard = "await readStatus(); window.clearTimeout(fallback);\n    if (modal.open) return;";
  if (!current.includes(legacyGuard)) {
    throw new Error('Vercel build could not locate the legacy modal-open auth guard');
  }
  const hardened = current.replace(
    legacyGuard,
    "await readStatus(); window.clearTimeout(fallback);\n    // O auth-ui é o dono do pré-login mesmo se outro script abriu o dialog antes."
  );
  writeFileSync(authPath, hardened);
}

hardenCopiedAuthRuntime();

let html = normalizeHead(readFileSync(join(source, 'index.html'), 'utf8'));
html = removeLegacyBootstrapTokenFallback(html);

for (const name of scripts) {
  const sourceAssetPath = join(source, name);
  const deployedAssetPath = join(assetsOutput, name);
  try {
    statSync(sourceAssetPath);
  } catch {
    throw new Error(`Vercel build requires missing frontend asset: ${name}`);
  }

  if (!html.includes(`/assets/${name}`)) {
    const tag = `<script src="/assets/${name}?v=${revision(deployedAssetPath)}" defer></script>`;
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
  throw new Error('Vercel static shell still exposes the legacy bootstrap-token login');
}

const deployedAuth = readFileSync(join(assetsOutput, 'auth-ui.js'), 'utf8');
if (deployedAuth.includes('if (modal.open) return;')) {
  throw new Error('Vercel auth runtime can still abandon an already-open authentication shell');
}

writeFileSync(join(output, 'index.html'), html);
console.log(`DevPilot Vercel frontend built at ${output}`);
