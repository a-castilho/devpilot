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

let html = normalizeHead(readFileSync(join(source, 'index.html'), 'utf8'));

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

writeFileSync(join(output, 'app.html'), html);

const loader = `<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="theme-color" content="#07111f">
  <title>DevPilot — iniciando</title>
  <style>
    *{box-sizing:border-box}html,body{margin:0;min-height:100%;background:#07111f;color:#eef7ff;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}body{min-height:100svh;display:grid;place-items:center;overflow:hidden}.boot{width:min(92vw,520px);padding:32px 26px;border:1px solid rgba(75,231,215,.22);border-radius:28px;background:radial-gradient(circle at 50% 0,rgba(65,210,242,.16),transparent 42%),linear-gradient(160deg,#0b1e2d,#07111f 70%);box-shadow:0 30px 90px rgba(0,0,0,.45);text-align:center}.mark{width:82px;height:82px;margin:0 auto 22px;border-radius:24px;display:grid;place-items:center;font-size:38px;font-weight:950;color:#03131c;background:linear-gradient(135deg,#55f3e4,#45bcf5);box-shadow:0 0 0 10px rgba(85,243,228,.06),0 18px 44px rgba(37,207,210,.22)}h1{margin:0 0 8px;font-size:clamp(2rem,9vw,3.2rem);letter-spacing:-.05em}p{margin:0;color:#93a9bc;line-height:1.55}.spinner{width:44px;height:44px;margin:28px auto 18px;border-radius:50%;border:4px solid rgba(255,255,255,.08);border-top-color:#55f3e4;animation:spin .85s linear infinite}.status{font-weight:850;color:#dffdfa}.detail{margin-top:8px;font-size:.9rem}.track{height:6px;margin:24px 0 0;overflow:hidden;border-radius:999px;background:rgba(255,255,255,.06)}.track i{display:block;width:38%;height:100%;border-radius:inherit;background:linear-gradient(90deg,#55f3e4,#45bcf5);animation:slide 1.35s ease-in-out infinite}.retry{display:none;margin:22px auto 0;padding:12px 18px;border:1px solid #2b5268;border-radius:14px;background:#0b2233;color:#e7f6ff;font-weight:800}.retry.show{display:block}@keyframes spin{to{transform:rotate(360deg)}}@keyframes slide{0%{transform:translateX(-120%)}50%{transform:translateX(125%)}100%{transform:translateX(300%)}}@media(max-width:520px){.boot{width:100vw;min-height:100svh;border:0;border-radius:0;display:flex;flex-direction:column;justify-content:center;padding:34px 28px}.mark{width:74px;height:74px}}
  </style>
</head>
<body>
  <main class="boot" role="status" aria-live="polite">
    <div class="mark">D</div>
    <h1>DevPilot</h1>
    <p>Seu ambiente de desenvolvimento está sendo preparado.</p>
    <div class="spinner" aria-hidden="true"></div>
    <div class="status" id="status">Iniciando serviços…</div>
    <p class="detail" id="detail">Você permanece aqui enquanto o backend acorda.</p>
    <div class="track" aria-hidden="true"><i></i></div>
    <button class="retry" id="retry" type="button">Tentar novamente</button>
  </main>
  <script>
    (() => {
      const status = document.getElementById('status');
      const detail = document.getElementById('detail');
      const retry = document.getElementById('retry');
      let attempt = 0;
      let timer = 0;
      let stopped = false;
      const next = () => {
        if (stopped) return;
        const delay = Math.min(3000, 650 + attempt * 220);
        window.clearTimeout(timer);
        timer = window.setTimeout(check, delay);
      };
      const openApp = () => {
        status.textContent = 'DevPilot pronto';
        detail.textContent = 'Abrindo seu ambiente…';
        window.setTimeout(() => location.replace('/app.html' + (location.hash || '')), 220);
      };
      const check = async () => {
        attempt += 1;
        retry.classList.remove('show');
        if (attempt > 2) {
          status.textContent = 'Acordando os serviços…';
          detail.textContent = 'Na primeira abertura isso pode levar alguns segundos.';
        }
        try {
          const response = await fetch('/health?boot=' + Date.now() + '&try=' + attempt, {
            cache: 'no-store',
            credentials: 'include',
          });
          if (response.ok) return openApp();
        } catch (_) {}
        if (attempt >= 24) {
          stopped = true;
          status.textContent = 'O serviço está demorando mais que o esperado';
          detail.textContent = 'Você pode tentar novamente sem sair desta tela.';
          retry.classList.add('show');
          return;
        }
        next();
      };
      retry.addEventListener('click', () => {
        stopped = false;
        attempt = 0;
        status.textContent = 'Reiniciando tentativa…';
        detail.textContent = 'Conectando ao DevPilot.';
        void check();
      });
      void check();
    })();
  </script>
</body>
</html>`;

writeFileSync(join(output, 'index.html'), loader);
console.log(`DevPilot Vercel frontend built at ${output} with cold-start loader`);
