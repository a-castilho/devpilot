(() => {
  'use strict';

  if (window.__devpilotGamePilotPanelReady) return;
  window.__devpilotGamePilotPanelReady = true;

  const PROJECT_KEY = 'devpilot-build-game-project';
  const REFRESH_MS = 15000;
  const ACTIVE = new Set(['running', 'review']);
  const WAITING = new Set(['queued', 'awaiting_approval']);
  const ATTENTION = new Set(['failed', 'blocked']);
  let timer = null;
  let refreshInFlight = null;

  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  })[char]);
  const norm = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const token = () => String(localStorage.getItem('devpilot-token') || '').trim();
  const projectId = () => String(document.querySelector('#build-game-project')?.value || localStorage.getItem(PROJECT_KEY) || '').trim();

  async function request(path, options = {}) {
    const headers = {...(options.headers || {})};
    if (token()) headers.Authorization = `Bearer ${token()}`;
    if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
    const response = await fetch(`/api${path}`, {...options, headers, cache: 'no-store'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`);
    return data;
  }

  function weapon(task) {
    const text = `${task?.title || ''} ${task?.prompt || ''}`.toLowerCase();
    if (/pytest|teste|test\b|spec\b/.test(text)) return ['🛡️', 'Escudo de testes', 'Testes transformam comportamento esperado em uma verificação repetível.'];
    if (/seguran|security|auth|permiss|autoriz/.test(text)) return ['📡', 'Scanner de segurança', 'Segurança verifica quem pode fazer o quê e quais dados podem ser alcançados.'];
    if (/deploy|vercel|render|publica|produção|producao/.test(text)) return ['🚀', 'Lançador de deploy', 'Deploy leva uma revisão validada para um ambiente executável e observável.'];
    if (/bug|fix|corrig|repar|falha|erro/.test(text)) return ['🔧', 'Canhão de reparo', 'Correção de bug deve eliminar a causa e deixar uma regressão automatizada quando possível.'];
    if (/refactor|refator/.test(text)) return ['🎯', 'Ferramenta de precisão', 'Refatoração melhora estrutura sem mudar o contrato observável do sistema.'];
    if (/diagn|analis|investig|auditoria/.test(text)) return ['🛰️', 'Radar de diagnóstico', 'Diagnóstico reduz incerteza antes de uma alteração e deve terminar com evidência verificável.'];
    return ['🧰', 'Ferramenta de construção', 'Construção transforma uma necessidade em mudança persistida e verificável no projeto.'];
  }

  function learning(task) {
    const state = norm(task?.status);
    if (ACTIVE.has(state)) return {
      now: 'O DevPilot está executando trabalho real desta tarefa no worker.',
      why: 'A interface acompanha o estado; fechar o jogo não interrompe a execução no servidor.'
    };
    if (WAITING.has(state)) return {
      now: 'A tarefa foi aceita e está aguardando a próxima etapa de execução.',
      why: 'Fila e aprovação separam intenção de execução e evitam trabalho concorrente ou não autorizado.'
    };
    if (state === 'completed') return {
      now: 'A tarefa terminou e o resultado ficou persistido no DevPilot.',
      why: 'Conclusão deve estar sustentada por evidência de execução, teste ou resultado técnico.'
    };
    if (ATTENTION.has(state)) return {
      now: 'A tarefa parou e precisa de atenção antes de continuar.',
      why: 'Falhas não são convertidas em sucesso; o erro é preservado para diagnóstico e retry controlado.'
    };
    if (state === 'cancelled') return {
      now: 'A execução foi cancelada e não está mais ativa.',
      why: 'Cancelamento encerra aquela tentativa sem apagar o histórico técnico.'
    };
    return {now: 'O DevPilot registrou esta tarefa.', why: 'O histórico permite entender o que foi pedido e como o sistema evoluiu.'};
  }

  function statusLabel(value) {
    const state = norm(value);
    return ({running:'Executando',review:'Em revisão',queued:'Na fila',awaiting_approval:'Aguardando aprovação',completed:'Concluída',failed:'Falhou',blocked:'Bloqueada',cancelled:'Cancelada'})[state] || value || 'Desconhecido';
  }

  function latestRunMap(runs) {
    const map = new Map();
    (Array.isArray(runs) ? runs : []).forEach(run => map.set(String(run.task_id), run));
    return map;
  }

  function card(task, run) {
    const [icon, weaponName, concept] = weapon(task);
    const lesson = learning(task);
    const state = norm(task.status);
    const canRetry = ATTENTION.has(state);
    const runButton = run?.run_id ? `<button class="ghost" type="button" data-pilot-run="${esc(run.run_id)}">${state === 'completed' ? 'Ver resultado' : 'Ver execução'}</button>` : '';
    const retryButton = canRetry ? `<button class="primary" type="button" data-pilot-retry="${esc(task.id)}">Tentar novamente</button>` : '';
    return `<article class="game-pilot-card" data-pilot-task="${esc(task.id)}">
      <div class="game-pilot-card-head"><div><span class="eyebrow">${icon} ${esc(weaponName)}</span><h4>${esc(task.title || 'Tarefa')}</h4><p>${esc(statusLabel(task.status))}</p></div><span class="game-pilot-chip">${esc(statusLabel(task.status))}</span></div>
      <div class="game-pilot-meta"><span class="game-pilot-chip">Prioridade ${esc(task.priority ?? '—')}</span>${run?.run_status ? `<span class="game-pilot-chip">Run ${esc(run.run_status)}</span>` : ''}</div>
      <div class="game-pilot-learning"><div><b>Agora</b><span>${esc(lesson.now)}</span></div><div><b>Por quê</b><span>${esc(lesson.why)}</span></div><div><b>Aprenda</b><span>${esc(concept)}</span></div></div>
      <div class="game-pilot-actions">${runButton}${retryButton}<button class="link" type="button" data-pilot-refresh>Atualizar</button></div>
    </article>`;
  }

  function ensureDialog() {
    let dialog = document.getElementById('game-pilot-dialog');
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.id = 'game-pilot-dialog';
    dialog.className = 'game-pilot-dialog';
    dialog.innerHTML = '<div data-pilot-dialog-body></div><div class="game-pilot-dialog-actions"><button class="ghost" type="button" data-pilot-close>Fechar</button></div>';
    dialog.querySelector('[data-pilot-close]')?.addEventListener('click', () => dialog.close());
    document.body.appendChild(dialog);
    return dialog;
  }

  function render(tasks, runs) {
    const shell = document.querySelector('#build-game-view .build-game-shell');
    if (!shell) return false;
    const map = latestRunMap(runs);
    const list = Array.isArray(tasks) ? tasks : [];
    const counts = list.reduce((acc, task) => {
      const state = norm(task.status);
      if (ACTIVE.has(state)) acc.running += 1;
      if (WAITING.has(state)) acc.waiting += 1;
      if (state === 'completed') acc.completed += 1;
      if (ATTENTION.has(state)) acc.attention += 1;
      return acc;
    }, {running:0, waiting:0, completed:0, attention:0});
    const visible = list.slice(0, 12);
    const markup = `<section class="game-pilot-panel" data-game-pilot-panel aria-label="Painel do Piloto">
      <div class="panel-title"><div><span class="eyebrow">PAINEL DO PILOTO</span><h3>Tarefas, armamentos e aprendizagem</h3></div><button class="link" type="button" data-pilot-refresh>Atualizar</button></div>
      <div class="game-pilot-summary"><div><span>Executando</span><strong>${counts.running}</strong></div><div><span>Na fila</span><strong>${counts.waiting}</strong></div><div><span>Concluídas</span><strong>${counts.completed}</strong></div><div><span>Atenção</span><strong>${counts.attention}</strong></div></div>
      <div class="game-pilot-grid">${visible.length ? visible.map(task => card(task, map.get(String(task.id)))).join('') : '<div class="game-pilot-empty">Nenhuma tarefa real neste projeto ainda. Inicie uma fase para criar a primeira missão.</div>'}</div>
    </section>`;
    shell.querySelector('[data-game-pilot-panel]')?.remove();
    const score = shell.querySelector('.build-game-score');
    if (score) score.insertAdjacentHTML('afterend', markup);
    else shell.insertAdjacentHTML('afterbegin', markup);
    return true;
  }

  async function refresh() {
    if (document.hidden || !token()) return false;
    if (refreshInFlight) return refreshInFlight;
    const id = projectId();
    if (!id) return false;
    refreshInFlight = Promise.all([
      request(`/tasks?project_id=${encodeURIComponent(id)}&limit=100`),
      request('/task-runs/latest?limit=500')
    ]).then(([tasks, runs]) => render(tasks, runs)).catch(error => {
      console.error('[DevPilot Pilot Panel]', error);
      return false;
    }).finally(() => { refreshInFlight = null; });
    return refreshInFlight;
  }

  async function showRun(runId) {
    const dialog = ensureDialog();
    const body = dialog.querySelector('[data-pilot-dialog-body]');
    if (body) body.innerHTML = '<p>Carregando execução…</p>';
    dialog.showModal();
    try {
      const run = await request(`/task-runs/${encodeURIComponent(runId)}`);
      const logs = typeof run.logs === 'string' ? run.logs : JSON.stringify(run.logs || {}, null, 2);
      if (body) body.innerHTML = `<span class="eyebrow">EXECUÇÃO REAL</span><h3>${esc(run.status || 'Run')}</h3><p>${esc(run.summary || run.failure?.message || 'Sem resumo registrado.')}</p><pre>${esc(logs || 'Sem log disponível.')}</pre>`;
    } catch (error) {
      if (body) body.innerHTML = `<h3>Falha ao abrir execução</h3><p>${esc(error.message)}</p>`;
    }
  }

  async function retry(taskId, button) {
    if (button) button.disabled = true;
    try {
      await request(`/tasks/${encodeURIComponent(taskId)}/retry`, {method:'POST'});
      await refresh();
    } catch (error) {
      window.alert?.(error.message);
    } finally {
      if (button?.isConnected) button.disabled = false;
    }
  }

  function scheduleRefresh(delay = 250) {
    window.setTimeout(() => void refresh(), delay);
  }

  document.addEventListener('click', event => {
    const retryButton = event.target.closest?.('[data-pilot-retry]');
    if (retryButton) return void retry(retryButton.dataset.pilotRetry, retryButton);
    const runButton = event.target.closest?.('[data-pilot-run]');
    if (runButton) return void showRun(runButton.dataset.pilotRun);
    if (event.target.closest?.('[data-pilot-refresh]')) return void refresh();
    if (event.target.closest?.('[data-play-phase], [data-game-refresh], #build-game-new')) scheduleRefresh(900);
  });
  document.addEventListener('change', event => {
    if (event.target?.id === 'build-game-project') scheduleRefresh(350);
  });
  document.addEventListener('devpilot:game:standalone-ready', () => {
    void refresh();
    if (!timer) timer = window.setInterval(() => void refresh(), REFRESH_MS);
  });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) void refresh(); });
  const stop = () => { if (timer) window.clearInterval(timer); timer = null; };
  window.addEventListener('pagehide', stop, {once:true});
  window.addEventListener('beforeunload', stop, {once:true});
})();
