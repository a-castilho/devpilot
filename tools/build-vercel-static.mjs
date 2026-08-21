import { createHash } from 'node:crypto';
import { cpSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const source = 'app/static';
const output = '.vercel-static';
const assetsOutput = join(output, 'assets');

rmSync(output, { recursive: true, force: true });
mkdirSync(output, { recursive: true });
cpSync(source, assetsOutput, { recursive: true });

const scripts = [
  'telemetry-capture.js',
  'profile.js',
  'auth-ui.js',
  'users.js',
  'provider-models.js',
  'project-provisioning.js',
  'voice-project-start.js',
  'voice-local-update.js',
  'voice-microphone-permission.js',
  'task-failures.js',
  'task-image-upload.js',
  'consolidated-ui.js',
  'analysis-failure-actions.js',
  'organization-normalization-ui.js',
  'example-project.js',
  'repeatai-analysis-scroll.js',
  'repeatai-live-graphs.js',
  'repeatai-pattern-graphs.js',
  'approval-slider.js',
  'tws-example.js',
];

function revision(path) {
  const content = readFileSync(path);
  return createHash('sha256').update(content).digest('hex').slice(0, 12);
}

let html = readFileSync(join(source, 'index.html'), 'utf8');

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

const mobileCss = 'mobile-scroll-unlock.css';
const mobileCssPath = join(source, mobileCss);
try {
  statSync(mobileCssPath);
} catch {
  throw new Error(`Vercel build requires missing frontend asset: ${mobileCss}`);
}

if (!html.includes(mobileCss)) {
  const tag = `<link rel="stylesheet" href="/assets/${mobileCss}?v=${revision(mobileCssPath)}">`;
  html = html.replace('</head>', `  ${tag}\n</head>`);
}

writeFileSync(join(output, 'index.html'), html);
console.log(`DevPilot Vercel frontend built at ${output}`);
