/* DevPilot Game Training 01: Linux first steps inside the game only. */
(() => {
  'use strict';

  const TRAINING_ID = 'linux-first-steps-v1';
  const STORAGE_PREFIX = 'devpilot-game-training';
  const STYLE_ID = 'game-linux-training-style';
  const POLL_INTERVAL_MS = 180;
  const POLL_ATTEMPTS = 45;

  const steps = [
    {
      id: 'where',
      number: 1,
      title: 'Descobrir onde estou',
      description: 'Use pwd para descobrir a pasta atual sem alterar nada.',
      command: 'pwd',
    },
    {
      id: 'files',
      number: 2,
      title: 'Ver arquivos',
      description: 'Liste arquivos e pastas da localização atual.',
      command: 'ls -lah',
    },
    {
      id: 'projects',
      number: 3,
      title: 'Encontrar projetos',
      description: 'Navegue até Documents e veja os projetos disponíveis.',
      command: 'cd ~/Documents && printf "Pasta: " && pwd && ls -lah',
    },
    {
      id: 'devpilot',
      number: 4,
      title: 'Abrir DevPilot',
      description: 'Entre no projeto DevPilot e consulte o estado atual do Git.',
      command: 'cd ~/Documents/devpilot && printf "Projeto: " && pwd && git status --short --branch',
    },
  ];

  let sessionId = '';
  let busy = false;
  let observer = null;

  const sleep = ms => new Promise(resolve => window.setTimeout(resolve, ms));
  const token = () => localStorage.getItem('devpilot-token') || '';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
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

  const readProgress = () => {
    try {
      const parsed = JSON.parse(localStorage.getItem(progressKey()) || '{}');
      const completed = Array.isArray(parsed.completed) ? parsed.completed.filter(id => steps.some(step => step.id === id)) : [];
      return {completed: [...new Set(completed)], finishedAt: parsed.finishedAt || ''};
    } catch (_) {
      return {completed: [], finishedAt: ''};
    }
  };

  const saveProgress = progress => {
    localStorage.setItem(progressKey(), JSON.stringify(progress));
  };

  const apiRequest = async (path, options = {}) => {
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
      const detail = typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`;
      throw new Error(detail);
    }
    return data;
  };

  const ensureStyle = () => {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .game-training-linux{display:grid;gap:14px;padding:18px;border:1px solid rgba(91,224,255,.28);border-radius:18px;background:linear-gradient(145deg,rgba(7,25,38,.96),rgba(5,13,24,.98));box-shadow:0 14px 38px rgba(0,0,0,.18)}
      .game-training-linux-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;flex-wrap:wrap}
      .game-training-linux-head h3{margin:3px 0 5px}.game-training-linux-head p{max-width:760px;margin:0;color:var(--muted,#9eacc2);font-size:.78rem;line-height:1.5}
      .game-training-linux-badge{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border:1px solid rgba(91,224,255,.42);border-radius:999px;color:#71e7ff;font-size:.68rem;font-weight:900;letter-spacing:.08em;white-space:nowrap}
      .game-training-linux-progress{height:9px;overflow:hidden;border-radius:999px;background:rgba(255,255,255,.07)}
      .game-training-linux-progress i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#58d8ff,#68f0bb);transition:width .2s ease}
      .game-training-linux-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}
      .game-training-linux-step{display:grid;gap:5px;min-height:118px;padding:12px;border:1px solid var(--line,#233047);border-radius:14px;background:rgba(5,15,27,.72);color:var(--text,#eef7ff);text-align:left;cursor:pointer}
      .game-training-linux-step:not(:disabled):hover{border-color:rgba(91,224,255,.55)}
      .game-training-linux-step.done{border-color:rgba(104,240,187,.48);background:rgba(37,120,91,.13)}
      .game-training-linux-step.current{border-color:rgba(91,224,255,.52);box-shadow:0 0 0 1px rgba(91,224,255,.08)}
      .game-training-linux-step:disabled{cursor:not-allowed;opacity:.46}
      .game-training-linux-step small{color:#65dfff;font-size:.65rem;font-weight:900;letter-spacing:.08em}.game-training-linux-step strong{font-size:.82rem}.game-training-linux-step span{color:var(--muted,#9eacc2);font-size:.7rem;line-height:1.4}
      .game-training-linux-terminal{overflow:hidden;border:1px solid #26364b;border-radius:14px;background:#04080d}
      .game-training-linux-toolbar{display:flex;align-items:center;gap:8px;padding:9px 10px;border-bottom:1px solid #26364b;background:#0b1420;flex-wrap:wrap}.game-training-linux-toolbar strong{font-size:.72rem}.game-training-linux-toolbar span{margin-left:auto;color:var(--muted,#9eacc2);font-size:.68rem}
      .game-training-linux-output{min-height:118px;max-height:240px;overflow:auto;margin:0;padding:12px;color:#d8f7dd;font:11px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}
      .game-training-linux-actions{display:flex;gap:9px;align-items:center;justify-content:space-between;flex-wrap:wrap}.game-training-linux-actions small{color:var(--muted,#9eacc2);font-size:.7rem}.game-training-linux-actions>div{display:flex;gap:8px;flex-wrap:wrap}
      .game-training-linux.completed{border-color:rgba(104,240,187,.42)}.game-training-linux.completed .game-training-linux-badge{border-color:rgba(104,240,187,.5);color:#68f0bb}
      @media(max-width:900px){.game-training-linux-steps{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @media(max-width:560px){.game-training-linux-steps{grid-template-columns:1fr}.game-training-linux-toolbar span{width:100%;margin-left:0}.game-training-linux-actions>div{width:100%}.game-training-linux-actions button{flex:1}}
    `;
    document.head.appendChild(style);
  };

  const markerFor = step => `__DEVPILOT_TRAINING_${TRAINING_ID}_${step.id}__`;
  const wrappedCommand = step => `(${step.command}); __dp_training_status=$?; printf '\\n${markerFor(step)}:%s\\n' "$__dp_training_status"`;

  const render = host => {
    const progress = readProgress();
    const completed = new Set(progress.completed);
    const count = completed.size;
    const finished = count === steps.length;
    const percent = Math.round((count / steps.length) * 100);
    const nextIndex = steps.findIndex(step => !completed.has(step.id));

    host.className = `game-training-linux${finished ? ' completed' : ''}`;
    host.innerHTML = `
      <div class="game-training-linux-head">
        <div>
          <span class="eyebrow">TREINAMENTO 01 · SISTEMAS DA NAVE</span>
          <h3>🐧 Linux: primeiros comandos de bordo</h3>
          <p>A mesma experiência de primeiros passos do Linux agora acontece dentro do jogo. Você aprende fazendo em uma sessão Linux real do seu perfil, usando somente consulta e navegação guiadas.</p>
        </div>
        <span class="game-training-linux-badge">${finished ? '✓ CONCLUÍDO' : `${count}/${steps.length} ETAPAS`}</span>
      </div>
      <div class="game-training-linux-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}"><i style="width:${percent}%"></i></div>
      <div class="game-training-linux-steps">
        ${steps.map((step, index) => {
          const done = completed.has(step.id);
          const unlocked = done || index === nextIndex;
          return `<button type="button" class="game-training-linux-step ${done ? 'done' : unlocked ? 'current' : ''}" data-game-linux-training-step="${esc(step.id)}" ${unlocked && !finished ? '' : done ? '' : 'disabled'}>
            <small>ETAPA ${step.number}/${steps.length}${done ? ' · ✓' : ''}</small>
            <strong>${esc(step.title)}</strong>
            <span>${esc(step.description)}</span>
          </button>`;
        }).join('')}
      </div>
      <article class="game-training-linux-terminal" aria-label="Terminal do treinamento Linux">
        <div class="game-training-linux-toolbar"><strong>TERMINAL DE TREINAMENTO</strong><span data-game-linux-training-state>${sessionId ? 'sessão aberta' : 'sessão fechada'}</span></div>
        <pre class="game-training-linux-output" data-game-linux-training-output aria-live="polite">${finished ? 'Treinamento concluído. Você já sabe localizar-se, listar arquivos, encontrar projetos e consultar o Git.\n' : 'Clique em “Iniciar treinamento” ou na etapa liberada. Nenhum comando de alteração é oferecido neste treinamento.\n'}</pre>
      </article>
      <div class="game-training-linux-actions">
        <small data-game-linux-training-hint>${finished ? 'Treinamento 01 finalizado. O Super Admin e a página Linux permanecem independentes.' : 'As etapas são liberadas em sequência e o progresso fica salvo para este usuário.'}</small>
        <div>
          ${finished ? '<button type="button" class="ghost" data-game-linux-training-reset>Refazer treinamento</button>' : '<button type="button" class="primary" data-game-linux-training-start>Iniciar treinamento</button>'}
          ${sessionId ? '<button type="button" class="ghost" data-game-linux-training-close>Encerrar sessão</button>' : ''}
        </div>
      </div>`;

    bind(host);
  };

  const setState = (host, text) => {
    const target = host.querySelector('[data-game-linux-training-state]');
    if (target) target.textContent = text;
  };

  const setHint = (host, text) => {
    const target = host.querySelector('[data-game-linux-training-hint]');
    if (target) target.textContent = text;
  };

  const setOutput = (host, text, append = false) => {
    const target = host.querySelector('[data-game-linux-training-output]');
    if (!target) return;
    const value = cleanOutput(text);
    target.textContent = append ? `${target.textContent}${value}` : value;
    if (target.textContent.length > 80000) target.textContent = target.textContent.slice(-60000);
    target.scrollTop = target.scrollHeight;
  };

  const ensureSession = async host => {
    if (sessionId) return sessionId;
    setState(host, 'abrindo sessão…');
    setHint(host, 'Conectando ao Linux do seu perfil dentro do jogo…');
    const session = await apiRequest('/api/linux/terminal/sessions', {
      method: 'POST',
      body: JSON.stringify({columns: 120, rows: 30}),
    });
    sessionId = String(session.id || '');
    if (!sessionId) throw new Error('A API não retornou o identificador da sessão Linux');
    setState(host, session.linux_user ? `aberta · ${session.linux_user}` : 'sessão aberta');
    setOutput(host, 'Linux aberto para o treinamento.\n');
    return sessionId;
  };

  const readAllOutput = async () => {
    if (!sessionId) return '';
    const data = await apiRequest(`/api/linux/terminal/sessions/${encodeURIComponent(sessionId)}/output?after=0`);
    return cleanOutput((data.chunks || []).map(chunk => chunk.text || '').join(''));
  };

  const waitForResult = async (step, host) => {
    const marker = `${markerFor(step)}:`;
    for (let attempt = 0; attempt < POLL_ATTEMPTS; attempt += 1) {
      await sleep(POLL_INTERVAL_MS);
      const output = await readAllOutput();
      setOutput(host, output || 'Aguardando saída do terminal…\n');
      const match = output.match(new RegExp(`${marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(\\d+)`));
      if (match) return Number(match[1]);
    }
    throw new Error('O terminal não confirmou o resultado da etapa no tempo esperado');
  };

  const completeStep = (step, host) => {
    const progress = readProgress();
    if (!progress.completed.includes(step.id)) progress.completed.push(step.id);
    if (progress.completed.length === steps.length) progress.finishedAt = new Date().toISOString();
    saveProgress(progress);
    document.dispatchEvent(new CustomEvent('devpilot:game-training-progress', {
      detail: {
        training_id: TRAINING_ID,
        step_id: step.id,
        completed: progress.completed.length,
        total: steps.length,
        finished: progress.completed.length === steps.length,
      },
    }));
    render(host);
  };

  const runStep = async (stepId, host) => {
    if (busy) return;
    const step = steps.find(item => item.id === stepId);
    if (!step) return;

    const progress = readProgress();
    const completed = new Set(progress.completed);
    const expected = steps.find(item => !completed.has(item.id));
    if (!completed.has(step.id) && expected?.id !== step.id) {
      setHint(host, 'Conclua a etapa anterior antes de avançar.');
      return;
    }

    busy = true;
    host.querySelectorAll('button').forEach(button => { button.disabled = true; });
    try {
      await ensureSession(host);
      setHint(host, `Executando etapa ${step.number}: ${step.title}. Comando: ${step.command}`);
      setState(host, `executando etapa ${step.number}/${steps.length}`);
      await apiRequest(`/api/linux/terminal/sessions/${encodeURIComponent(sessionId)}/input`, {
        method: 'POST',
        body: JSON.stringify({data: `${wrappedCommand(step)}\n`}),
      });
      const exitCode = await waitForResult(step, host);
      if (exitCode !== 0) throw new Error(`O comando terminou com código ${exitCode}. A etapa não foi marcada como concluída.`);
      setHint(host, `Etapa ${step.number} concluída com evidência real do terminal.`);
      completeStep(step, host);
    } catch (error) {
      setState(host, sessionId ? 'sessão aberta · etapa falhou' : 'sessão indisponível');
      setHint(host, error?.message || 'Falha ao executar a etapa do treinamento');
      host.querySelectorAll('button').forEach(button => { button.disabled = false; });
    } finally {
      busy = false;
    }
  };

  const closeSession = async host => {
    if (!sessionId) return;
    const id = sessionId;
    sessionId = '';
    try {
      await apiRequest(`/api/linux/terminal/sessions/${encodeURIComponent(id)}`, {method: 'DELETE'});
      setHint(host, 'Sessão de treinamento encerrada. Seu progresso foi preservado.');
    } catch (error) {
      setHint(host, error?.message || 'Não foi possível encerrar a sessão');
    } finally {
      render(host);
    }
  };

  function bind(host) {
    host.querySelector('[data-game-linux-training-start]')?.addEventListener('click', () => {
      const progress = readProgress();
      const next = steps.find(step => !progress.completed.includes(step.id));
      if (next) void runStep(next.id, host);
    });
    host.querySelectorAll('[data-game-linux-training-step]').forEach(button => {
      button.addEventListener('click', () => void runStep(button.dataset.gameLinuxTrainingStep, host));
    });
    host.querySelector('[data-game-linux-training-close]')?.addEventListener('click', () => void closeSession(host));
    host.querySelector('[data-game-linux-training-reset]')?.addEventListener('click', () => {
      saveProgress({completed: [], finishedAt: ''});
      setOutput(host, 'Treinamento reiniciado.\n');
      render(host);
    });
  }

  const ensureTraining = () => {
    ensureStyle();
    const view = document.querySelector('#build-game-view');
    const shell = view?.querySelector('.build-game-shell');
    if (!view || !shell) return;

    let host = shell.querySelector('[data-game-linux-training]');
    if (!host) {
      host = document.createElement('section');
      host.dataset.gameLinuxTraining = '1';
      const wallet = shell.querySelector('[data-linux-wallet]');
      const cockpit = shell.querySelector('[data-build-game-cockpit]');
      if (wallet) wallet.insertAdjacentElement('afterend', host);
      else if (cockpit) cockpit.insertAdjacentElement('afterend', host);
      else shell.prepend(host);
    }
    if (!host.dataset.trainingRendered) {
      host.dataset.trainingRendered = '1';
      render(host);
    }
  };

  const boot = () => {
    ensureTraining();
    const root = document.querySelector('main') || document.body;
    if (!root || observer) return;
    observer = new MutationObserver(() => ensureTraining());
    observer.observe(root, {childList: true, subtree: true});
  };

  window.addEventListener('beforeunload', () => {
    if (!sessionId) return;
    fetch(`/api/linux/terminal/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
      keepalive: true,
      headers: token() ? {Authorization: `Bearer ${token()}`} : {},
    }).catch(() => {});
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();
