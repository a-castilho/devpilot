import { readFileSync, writeFileSync } from 'node:fs';

const path = 'app/static/auth-ui.js';
const source = readFileSync(path, 'utf8');
const startMarker = '  const boot = async () => {';
const endMarker = '\n\n  void boot();';
const start = source.indexOf(startMarker);
const end = source.indexOf(endMarker, start);

if (start < 0 || end < 0) {
  throw new Error('Não foi possível localizar o boot de autenticação para aplicar home-first.');
}

const replacement = `  const boot = async () => {\n    // Contrato canônico de homologação: toda abertura começa na home pública.\n    // Sessões previamente salvas nunca pulam a home nem materializam login sozinhas.\n    window.__devpilotPublicHomeFirst = true;\n    await readStatus();\n    const token = String(localStorage.getItem(TOKEN_KEY) || '').trim();\n    if (token && tokenExpired(token)) localStorage.removeItem(TOKEN_KEY);\n    renderPublicHome(consumeAuthMessage(''));\n  };`;

const output = source.slice(0, start) + replacement + source.slice(end);

for (const required of [
  'function renderPublicHome',
  "document.querySelector('#public-login')?.addEventListener('click', () => renderLoginForm())",
  'window.__devpilotPublicHomeFirst = true',
  "renderPublicHome(consumeAuthMessage(''))",
]) {
  if (!output.includes(required)) throw new Error(`Contrato home-first ausente: ${required}`);
}

writeFileSync(path, output);
console.log('DevPilot auth home-first aplicado com sucesso.');
