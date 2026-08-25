/* DevPilot Game Training 01: Linux first steps inside the isolated game session. */
(() => {
  'use strict';

  const TRAINING_ID = 'linux-first-steps-v2';
  const STORAGE_PREFIX = 'devpilot-game-training';
  const HOST_ID = 'game-linux-training-host';
  const STYLE_ID = 'game-linux-training-style';
  const POLL_INTERVAL_MS = 200;
  const POLL_ATTEMPTS = 40;

  const steps = [
    {
      id: 'where',
      number: 1,
      title: 'Descobrir onde estou',
      description: 'Mostra a pasta isolada onde esta sessão começou.',
      command: 'pwd',
    },
    {
      id: 'files',
      number: 2,
      title: 'Ver arquivos',
      description: 'Lista somente o conteúdo da pasta atual.',
      command: 'ls -lah',
    },
    {
      id: 'workspace',
      number: 3,
      title: 'Explorar o workspace',
      description: 'Mostra pastas próximas sem sair do workspace da sessão.',
      command: 'printf "Workspace: "; pwd; find . -maxdepth 2 -type d -print | head -40',
    },
    {
      id: 'git',
      number: 4,
      title: 'Consultar o Git',
      description: 'Consulta o Git somente se o repositório estiver no diretório atual.',
      command: 'if [ -d .git ]; then git status --short --branch; else printf "Workspace sem repositório Git neste nível.\\n"; fi',
    },
  ];

  let sessionId = '';
  let busy = false;
  let mountScheduled = false;

  const token = () => localStorage.getItem('devpilot-token') || '';
  const sleep = ms => new Promise(resolve => window.setTimeout(resolve, ms));
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);

  const cleanOutput = value => String(value || '')
    .replace(/\u001b\][^\u0007]*(?:\u0007|\u001b\\)/g, '')
    .replace(/\u001b\[[0-?]*[ -\/]*[@-~]/g, '')
    .replace(/\r/g, '')
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, '');

  const currentUserId = () => {
    try {
      return String(typeof state !== 'undefined' && state.currentUser?.id || 'anonymous');
    } catch (_) {
      return 'anonymous';
    }
  };

  const progressKey = () => `${STORAGE_PREFIX}:${TRAINING_ID}:${currentUserId()}`;

  function readProgress() {
    try {
      const parsed = JSON.parse(localStorage.getItem(progressKey()) || '{}');
      const completed = Array.isArray(parsed.completed)
        ? parsed.completed.filter(id => steps.some(step => step.id === id))
        : [];
      return {completed: [...new Set(completed)], finishedAt: parsed.finishedAt || ''};
    } catch (_) {
      return {completed: [], finishedAt: ''};
    }
  }

  function saveProgress(progress) {
    try { localStorage.setItem(progressKey(), JSON.stringify(progress)); }
    catch (_) { /* Progresso local é opcional; execução continua. */ }
  }

  async function apiRequest(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/json',
        ...(token() ? {Authorization: `Bearer ${token()}`} : {}),
        ...(options.headers || {}),
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`);
    }
    return data;
  }

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .game-training-linux{display:grid;gap:12px;padding:16px;border:1px solid rgba(91,224,255,.28);border-radius:16px;background:rgba(5,15,27,.72)}
      .game-training-linux-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}
      .game-training-linux-head h3{margin:3px 0 5px}.game-training-linux-head p{margin:0;color:var(--muted,#9eacc2);font-size:.78rem;line-height:1.45;max-width:760px}
      .game-training-linux-badge{padding:6px 10px;border:1px solid rgba(91,224,255,.38);border-radius:999px;color:#71e7ff;font-size:.68rem;font-weight:900}
      .game-training-linux-progress{height:8px;overflow:hidden;border-radius:999px;background:rgba(255,255,255,.07)}
      .game-training-linux-progress i{display:block;height:100%;background:linear-gradient(90deg,#58d8ff,#68f0bb)}
      .game-training-linux-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
      .game-training-linux-step{display:grid;gap:5px;min-height:110px;padding:11px;border:1px solid var(--line,#233047);border-radius:12px;background:rgba(4,11,20,.72);color:var(--text,#eef7ff);text-align:left}
      .game-training-linux-step.current{border-color:rgba(91,224,255,.55)}.game-training-linux-step.done{border-color:rgba(104,240,187,.45)}.game-training-linux-step:disabled{opacity:.45}
      .game-training-linux-step small{color:#65dfff;font-weight:900}.game-training-linux-step span{color:var(--muted,#9eacc2);font-size:.7rem;line-height:1.35}
      .game-training-linux-terminal{overflow:hidden;border:1px solid #26364b;border-radius:12px;background:#04080d}
      .game-training-linux-toolbar{display:flex;justify-content:space-between;gap:8px;padding:8px 10px;border-bottom:1px solid #26364b;background:#0b1420;font-size:.72rem}
      .game-training-linux-output{min-height:105px;max-height:220px;overflow:auto;margin:0;padding:11px;color:#d8f7dd;font:11px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}
      .game-training-linux-actions{display:flex;justify-content:space-between;gap:8px;align-items:center;flex-wrap:wrap}.game-training-linux-actions small{color:var(--muted,#9eacc2);font-size:.7rem}
      @media(max-width:900px){.game-training-linux-steps{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @media(max-width:560px){.game-training-linux-steps{grid-template-columns:1fr}.game-training-linux-actions button{width:100%}}
    `;
    document.head.appendChild(style);
  }

  const markerFor = step => `__DEVPILOT_TRAINING_${TRAINING_ID}_${step.id}__`;
  const wrappedCommand = step => `(${step.command}); __dp_training_status=$?; printf '\\n${markerFor(step)}:%s\\n' "$__dp_training_status"`;

  function render(host) {
    const progress = readProgress();
    const completed = new Set(progress.completed);
    const count = completed.size;
    const finished = count === steps.length;
    const nextIndex = steps.findIndex(step => !completed.has(step.id));
    const percent = Math.round((count / steps.length) * 100);

    host.className = 'game-training-linux';
    host.innerHTML = `
      <div class="game-training-linux-head">
        <div>
          <span class="eyebrow">TREINAMENTO 01 · SISTEMAS DA NAVE</span>
          <h3>🐧 Linux: primeiros comandos de bordo</h3>
          <p>Treinamento somente leitura. Os comandos trabalham a partir do diretório isolado da sessão e não usam HOME, caminhos absolutos do host nem navegação para fora do workspace.</p>
        </div>
        <span class="game-training-linux-badge">${finished ? '✓ CONCLUÍDO' : `${count}/${steps.length} ETAPAS`}</span>
      </div>
      <div class="game-training-linux-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}"><i style="width:${percent}%"></i></div>
      <div class="game-training-linux-steps">
        ${steps.map((step, index) => {
          const done = completed.has(step.id);
          const unlocked = done || index === nextIndex;
          return `<button type="button" class="game-training-linux-step ${done ? 'done' : unlocked ? 'current' : ''}" data-game-linux-training-step="${escapeHtml(step.id)}" ${unlocked ? '' : 'disabled'}>
            <small>ETAPA ${step.number}/${steps.length}${done ? ' · ✓' : ''}</small>
            <strong>${escapeHtml(step.title)}</strong>
            <span>${escapeHtml(step.description)}</span>
          </button>`;
        }).join('')}
      </div>
      <article class="game-training-linux-terminal" aria-label="Terminal do treinamento Linux">
        <div class="game-training-linux-toolbar"><strong>TERMINAL DE TREINAMENTO</strong><span data-game-linux-training-state>${sessionId ? 'sessão aberta' : 'sessão fechada'}</span></div>
        <pre class="game-training-linux-output" data-game-linux-training-output aria-live="polite">${finished ? 'Treinamento concluído.\n' : 'Escolha a etapa liberada para executar o comando de consulta.\n'}</pre>
      </article>
      <div class="game-training-linux-actions">
        <small data-game-linux-training-hint>${finished ? 'Treinamento concluído. Você pode refazer quando quiser.' : 'As etapas são liberadas em sequência.'}</small>
        <button type="button" class="ghost" data-game-linux-training-reset>${finished ? 'Refazer treinamento' : 'Reiniciar progresso'}</button>
      </div>`;

    bind(host);
  }

  function setState(host, text) {
    const target = host.querySelector('[data-game-linux-training-state]');
    if (target) target.textContent = text;
  }

  function setHint(host, text) {
    const target = host.querySelector('[data-game-linux-training-hint]');
    if (target) target.textContent = text;
  }

  function setOutput(host, text) {
    const target = host.querySelector('[data-game-linux-training-output]');
    if (!target) return;
    target.textContent = cleanOutput(text) || 'Sem saída.\n';
    target.scrollTop = target.scrollHeight;
  }

  async function ensureSession(host) {
    if (sessionId) return sessionId;
    setState(host, 'abrindo sessão…');
    const session = await apiRequest('/api/linux/terminal/sessions', {
      method: 'POST',
      body: JSON.stringify({columns: 120, rows: 30}),
    });
    sessionId = String(session.id || '');
    if (!sessionId) throw new Error('A API não retornou o identificador da sessão Linux');
    setState(host, session.linux_user ? `aberta · ${session.linux_user}` : 'sessão aberta');
    return sessionId;
  }

  async function readAllOutput() {
    if (!sessionId) return '';
    const data = await apiRequest(`/api/linux/terminal/sessions/${encodeURIComponent(sessionId)}/output?after=0`);
    return cleanOutput((data.chunks || []).map(chunk => chunk.text || '').join(''));
  }

  async function waitForResult(step, host) {
    const marker = `${markerFor(step)}:`;
    for (let attempt = 0; attempt < POLL_ATTEMPTS; attempt += 1) {
      await sleep(POLL_INTERVAL_MS);
      const output = await readAllOutput();
      setOutput(host, output || 'Aguardando saída do terminal…\n');
      const match = output.match(new RegExp(`${marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(\\d+)`));
      if (match) return Number(match[1]);
    }
    throw new Error('O terminal não confirmou o resultado da etapa no tempo esperado');
  }

  function completeStep(step, host) {
    const progress = readProgress();
    if (!progress.completed.includes(step.id)) progress.completed.push(step.id);
    if (progress.completed.length === steps.length) progress.finishedAt = new Date().toISOString();
    saveProgress(progress);
    render(host);
  }

  async function runStep(stepId, host) {
    if (busy) return;
    const step = steps.find(item => item.id === stepId);
    if (!step) return;

    const completed = new Set(readProgress().completed);
    const expected = steps.find(item => !completed.has(item.id));
    if (!completed.has(step.id) && expected?.id !== step.id) {
      setHint(host, 'Conclua a etapa anterior antes de avançar.');
      return;
    }

    busy = true;
    host.querySelectorAll('button').forEach(button => { button.disabled = true; });
    try {
      await ensureSession(host);
      setHint(host, `Executando: ${step.command}`);
      await apiRequest(`/api/linux/terminal/sessions/${encodeURIComponent(sessionId)}/input`, {
        method: 'POST',
        body: JSON.stringify({data: `${wrappedCommand(step)}\n`}),
      });
      const status = await waitForResult(step, host);
      if (status !== 0) throw new Error(`O comando terminou com status ${status}`);
      completeStep(step, host);
    } catch (error) {
      setHint(host, `Falha no treinamento: ${error.message}`);
      host.querySelectorAll('button').forEach(button => { button.disabled = false; });
    } finally {
      busy = false;
    }
  }

  function bind(host) {
    host.querySelectorAll('[data-game-linux-training-step]').forEach(button => {
      button.addEventListener('click', () => void runStep(button.dataset.gameLinuxTrainingStep, host), {once: true});
    });
    host.querySelector('[data-game-linux-training-reset]')?.addEventListener('click', () => {
      saveProgress({completed: [], finishedAt: ''});
      render(host);
    }, {once: true});
  }

  function mount() {
    mountScheduled = false;
    const view = document.querySelector('#build-game-view');
    if (!view) return;

    let host = view.querySelector(`#${HOST_ID}`);
    if (!host) {
      host = document.createElement('section');
      host.id = HOST_ID;
      const map = view.querySelector('.build-game-map');
      if (map) map.insertAdjacentElement('afterend', host);
      else view.appendChild(host);
    }
    ensureStyle();
    render(host);
  }

  function scheduleMount() {
    if (mountScheduled) return;
    mountScheduled = true;
    queueMicrotask(mount);
  }

  document.addEventListener('devpilot:build-game-loaded', scheduleMount);
  document.addEventListener('devpilot:build-game-new-session', scheduleMount);
  document.addEventListener('click', event => {
    if (event.target?.closest?.('.nav[data-view="build-game"], [data-project-build-game]')) {
      window.setTimeout(scheduleMount, 0);
    }
  }, true);

  const observer = new MutationObserver(scheduleMount);
  observer.observe(document.body, {childList: true, subtree: true});

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scheduleMount, {once: true});
  } else {
    scheduleMount();
  }
})();
