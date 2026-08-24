(() => {
  'use strict';

  const STYLE_ID = 'mission-control-ai-dashboard-style';
  const CHAT_MODE_STORAGE_KEY = 'devpilot-chat-mode';
  const ACTIVE_PROJECT_STORAGE_KEY = 'devpilot-chat-active-project-id';
  const HISTORY_LIMIT = 8;

  let chatHistory = [];
  let chatBusy = false;
  let chartFrame = 0;

  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);

  const getAppState = () => {
    try {
      return typeof state !== 'undefined' ? state : {projects: [], tasks: [], currentUser: null};
    } catch (_) {
      return {projects: [], tasks: [], currentUser: null};
    }
  };

  const ensureStylesheet = () => {
    if (document.querySelector(`link[data-${STYLE_ID}]`)) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/assets/mission-control-ai-dashboard.css?v=20260824-1';
    link.setAttribute(`data-${STYLE_ID}`, '1');
    document.head.appendChild(link);
  };

  const numberFrom = value => {
    const parsed = Number(String(value ?? '').replace(/[^0-9.-]/g, ''));
    return Number.isFinite(parsed) ? parsed : 0;
  };

  const readMetricSnapshot = target => {
    const snapshot = {};
    target.querySelectorAll(':scope > div').forEach(card => {
      const label = card.querySelector('span')?.textContent?.trim().toUpperCase();
      const value = numberFrom(card.querySelector('strong')?.textContent);
      if (!label) return;
      if (label === 'PROJETOS') snapshot.projects = value;
      if (label === 'TAREFAS') snapshot.tasks = value;
      if (label === 'EM ANDAMENTO') snapshot.active = value;
      if (label === 'CONCLUÍDAS') snapshot.completed = value;
      if (label.includes('APROVA')) snapshot.pending = value;
    });
    return snapshot;
  };

  const statusBuckets = () => {
    const tasks = getAppState().tasks || [];
    const buckets = {active: 0, completed: 0, pending: 0, failed: 0, other: 0};
    tasks.forEach(task => {
      const value = String(task?.status || '').toLowerCase();
      if (['running', 'in_progress', 'processing', 'queued'].includes(value)) buckets.active += 1;
      else if (['completed', 'done', 'success'].includes(value)) buckets.completed += 1;
      else if (['awaiting_approval', 'pending', 'review'].includes(value)) buckets.pending += 1;
      else if (['failed', 'error', 'blocked', 'cancelled', 'rejected'].includes(value)) buckets.failed += 1;
      else buckets.other += 1;
    });
    return buckets;
  };

  const recentActivityPoints = () => {
    const tasks = getAppState().tasks || [];
    const now = new Date();
    const values = Array.from({length: 7}, () => 0);
    tasks.forEach(task => {
      if (!task?.created_at) return;
      const date = new Date(task.created_at);
      if (Number.isNaN(date.getTime())) return;
      const diffDays = Math.floor((new Date(now.getFullYear(), now.getMonth(), now.getDate()) - new Date(date.getFullYear(), date.getMonth(), date.getDate())) / 86400000);
      if (diffDays >= 0 && diffDays < 7) values[6 - diffDays] += 1;
    });
    const max = Math.max(1, ...values);
    return values.map((value, index) => {
      const x = 8 + (index * 84 / 6);
      const y = 42 - (value / max) * 32;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  };

  const renderCharts = () => {
    const target = document.querySelector('#mc-metrics');
    if (!target || target.querySelector('.mc-chart-grid')) return;

    const snapshot = readMetricSnapshot(target);
    const buckets = statusBuckets();
    const total = snapshot.tasks || (buckets.active + buckets.completed + buckets.pending + buckets.failed + buckets.other);
    const completed = snapshot.completed || buckets.completed;
    const active = snapshot.active || buckets.active;
    const pending = snapshot.pending || buckets.pending;
    const failed = buckets.failed;
    const other = Math.max(0, total - completed - active - pending - failed);
    const completion = total > 0 ? Math.max(0, Math.min(100, Math.round((completed / total) * 100))) : 0;

    const categories = [
      ['Concluídas', completed, 'ok'],
      ['Em andamento', active, 'active'],
      ['Aguardando', pending, 'warning'],
      ['Falhas', failed, 'danger'],
      ['Outras', other, 'neutral'],
    ].filter(([, value]) => value > 0);
    const safeTotal = Math.max(1, categories.reduce((sum, [, value]) => sum + value, 0));

    target.innerHTML = `
      <div class="mc-chart-grid" aria-label="Gráficos operacionais">
        <article class="mc-chart-card mc-chart-progress">
          <div class="mc-chart-heading"><span>PROGRESSO</span><small>fluxo concluído</small></div>
          <div class="mc-donut" style="--mc-progress:${completion * 3.6}deg" role="img" aria-label="${completion}% das tarefas concluídas">
            <div><strong>${completion}%</strong><span>concluído</span></div>
          </div>
        </article>

        <article class="mc-chart-card mc-chart-status">
          <div class="mc-chart-heading"><span>DISTRIBUIÇÃO</span><small>estado das missões</small></div>
          <div class="mc-stacked-chart" role="img" aria-label="Distribuição das tarefas por estado">
            ${categories.map(([label, value, tone]) => `<i class="${tone}" style="flex:${Math.max(1, value)}" title="${escapeHtml(label)}: ${value}"></i>`).join('') || '<i class="neutral" style="flex:1"></i>'}
          </div>
          <div class="mc-chart-legend">
            ${categories.map(([label, value, tone]) => `<span><i class="${tone}"></i>${escapeHtml(label)} <small>${Math.round((value / safeTotal) * 100)}%</small></span>`).join('') || '<span><i class="neutral"></i>Sem tarefas</span>'}
          </div>
        </article>

        <article class="mc-chart-card mc-chart-activity">
          <div class="mc-chart-heading"><span>RITMO</span><small>atividade recente</small></div>
          <svg viewBox="0 0 100 50" role="img" aria-label="Atividade recente em sete dias" preserveAspectRatio="none">
            <path d="M8 42H92" class="mc-chart-axis"></path>
            <polyline points="${recentActivityPoints()}" class="mc-chart-line"></polyline>
          </svg>
          <div class="mc-chart-days"><span>-6d</span><span>hoje</span></div>
        </article>
      </div>
    `;
  };

  const scheduleCharts = () => {
    if (chartFrame) cancelAnimationFrame(chartFrame);
    chartFrame = requestAnimationFrame(() => {
      chartFrame = 0;
      renderCharts();
    });
  };

  const observeMetrics = () => {
    const target = document.querySelector('#mc-metrics');
    if (!target || target.dataset.aiChartsObserved === '1') return;
    target.dataset.aiChartsObserved = '1';
    new MutationObserver(scheduleCharts).observe(target, {childList: true, subtree: true, characterData: true});
    scheduleCharts();
  };

  const normalizeMode = value => value === 'build' ? 'build' : 'planning';
  const currentMode = () => {
    try {
      return normalizeMode(window.devpilotChatMode?.getMode?.() || localStorage.getItem(CHAT_MODE_STORAGE_KEY));
    } catch (_) {
      return normalizeMode(localStorage.getItem(CHAT_MODE_STORAGE_KEY));
    }
  };

  const activeProjectId = () => {
    try {
      return String(window.devpilotChatProjectContext?.getProjectId?.() || localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY) || '').trim();
    } catch (_) {
      return String(localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY) || '').trim();
    }
  };

  const createAiChat = () => {
    if (document.querySelector('#mc-ai-drawer')) return;

    const launcher = document.createElement('button');
    launcher.id = 'mc-ai-launcher';
    launcher.className = 'mc-ai-launcher';
    launcher.type = 'button';
    launcher.setAttribute('aria-label', 'Abrir chat de IA');
    launcher.setAttribute('title', 'Chat de IA');
    launcher.innerHTML = '<span aria-hidden="true">✦</span><strong>IA</strong>';

    const drawer = document.createElement('aside');
    drawer.id = 'mc-ai-drawer';
    drawer.className = 'mc-ai-drawer';
    drawer.setAttribute('aria-hidden', 'true');
    drawer.innerHTML = `
      <header class="mc-ai-header">
        <div><span>IA DE BORDO</span><strong>Chat DevPilot</strong></div>
        <button type="button" data-mc-ai-close aria-label="Fechar chat">×</button>
      </header>
      <div class="mc-ai-context">
        <label>Projeto
          <select id="mc-ai-project"><option value="">Geral — sem projeto</option></select>
        </label>
        <div class="mc-ai-modes" role="group" aria-label="Modo do chat">
          <button type="button" data-mc-ai-mode="planning">Planejar</button>
          <button type="button" data-mc-ai-mode="build">Construir</button>
        </div>
      </div>
      <div id="mc-ai-log" class="mc-ai-log" aria-live="polite">
        <div class="mc-ai-empty">Chame a IA a qualquer momento. O contexto do projeto acompanha a conversa.</div>
      </div>
      <form id="mc-ai-form" class="mc-ai-composer">
        <textarea id="mc-ai-input" rows="1" maxlength="4000" placeholder="Pergunte ou peça uma ação…" aria-label="Mensagem para o DevPilot"></textarea>
        <button id="mc-ai-send" type="submit" aria-label="Enviar mensagem">↑</button>
      </form>
      <div id="mc-ai-status" class="mc-ai-status">Pronto</div>
    `;

    document.body.append(launcher, drawer);

    const headerActions = document.querySelector('header .header-actions');
    if (headerActions && !document.querySelector('#mc-ai-header-button')) {
      const button = document.createElement('button');
      button.id = 'mc-ai-header-button';
      button.className = 'ghost mc-ai-header-button';
      button.type = 'button';
      button.textContent = '✦ Chat IA';
      button.setAttribute('aria-label', 'Abrir chat de IA');
      headerActions.prepend(button);
      button.addEventListener('click', () => openAiChat(true));
    }

    launcher.addEventListener('click', () => openAiChat());
    drawer.querySelector('[data-mc-ai-close]')?.addEventListener('click', closeAiChat);
    drawer.querySelectorAll('[data-mc-ai-mode]').forEach(button => {
      button.addEventListener('click', () => setMode(button.dataset.mcAiMode));
    });
    drawer.querySelector('#mc-ai-project')?.addEventListener('change', event => {
      const projectId = String(event.target.value || '');
      localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, projectId);
      try {
        if (projectId) window.devpilotChatProjectContext?.setProjectId?.(projectId);
      } catch (_) {}
      window.dispatchEvent(new CustomEvent('devpilot:active-project-changed', {detail: {project_id: projectId || null}}));
      chatHistory = [];
      renderChatHistory();
    });
    drawer.querySelector('#mc-ai-form')?.addEventListener('submit', submitChat);
    drawer.querySelector('#mc-ai-input')?.addEventListener('keydown', event => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        drawer.querySelector('#mc-ai-form')?.requestSubmit();
      }
    });

    syncProjects();
    syncModeButtons();
  };

  const openAiChat = focusInput => {
    const drawer = document.querySelector('#mc-ai-drawer');
    if (!drawer) return;
    syncProjects();
    syncModeButtons();
    drawer.classList.add('open');
    drawer.setAttribute('aria-hidden', 'false');
    document.body.classList.add('mc-ai-open');
    if (focusInput !== false) window.setTimeout(() => drawer.querySelector('#mc-ai-input')?.focus(), 80);
  };

  const closeAiChat = () => {
    const drawer = document.querySelector('#mc-ai-drawer');
    if (!drawer) return;
    drawer.classList.remove('open');
    drawer.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('mc-ai-open');
  };

  const syncProjects = () => {
    const select = document.querySelector('#mc-ai-project');
    if (!select) return;
    const projects = getAppState().projects || [];
    const wanted = activeProjectId();
    const options = ['<option value="">Geral — sem projeto</option>']
      .concat(projects.map(project => `<option value="${escapeHtml(project.id)}">${escapeHtml(project.name)}</option>`));
    select.innerHTML = options.join('');
    if ([...select.options].some(option => String(option.value) === wanted)) select.value = wanted;
  };

  const setMode = mode => {
    const value = normalizeMode(mode);
    localStorage.setItem(CHAT_MODE_STORAGE_KEY, value);
    try {
      window.devpilotChatMode?.setMode?.(value);
    } catch (_) {}
    syncModeButtons();
    chatHistory = [];
    renderChatHistory();
  };

  const syncModeButtons = () => {
    const mode = currentMode();
    document.querySelectorAll('[data-mc-ai-mode]').forEach(button => {
      const active = button.dataset.mcAiMode === mode;
      button.dataset.active = active ? '1' : '0';
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  };

  const renderChatHistory = () => {
    const log = document.querySelector('#mc-ai-log');
    if (!log) return;
    if (!chatHistory.length) {
      log.innerHTML = '<div class="mc-ai-empty">Chame a IA a qualquer momento. O contexto do projeto acompanha a conversa.</div>';
      return;
    }
    log.innerHTML = chatHistory.map(turn => `
      <article class="mc-ai-turn" data-role="${turn.role}">
        <strong>${turn.role === 'assistant' ? 'DevPilot' : 'Você'}</strong>
        <p>${escapeHtml(turn.text)}</p>
      </article>
    `).join('');
    log.scrollTop = log.scrollHeight;
  };

  const setChatBusy = busy => {
    chatBusy = busy;
    const send = document.querySelector('#mc-ai-send');
    const input = document.querySelector('#mc-ai-input');
    if (send) send.disabled = busy;
    if (input) input.disabled = busy;
  };

  const submitChat = async event => {
    event?.preventDefault?.();
    if (chatBusy) return;
    const input = document.querySelector('#mc-ai-input');
    const projectSelect = document.querySelector('#mc-ai-project');
    const status = document.querySelector('#mc-ai-status');
    const log = document.querySelector('#mc-ai-log');
    const text = String(input?.value || '').trim();
    const projectId = String(projectSelect?.value || '').trim();
    const mode = currentMode();
    if (!text) return;

    if (mode === 'build' && !projectId) {
      if (status) status.textContent = 'Selecione um projeto para usar Construir.';
      projectSelect?.focus();
      return;
    }

    if (typeof api !== 'function') {
      if (status) status.textContent = 'API de IA indisponível.';
      return;
    }

    const previousHistory = chatHistory.slice(-HISTORY_LIMIT);
    chatHistory.push({role: 'user', text});
    if (input) input.value = '';
    renderChatHistory();
    const thinking = document.createElement('div');
    thinking.className = 'mc-ai-thinking';
    thinking.innerHTML = '<i></i><i></i><i></i>';
    log?.appendChild(thinking);
    if (log) log.scrollTop = log.scrollHeight;
    if (status) status.textContent = mode === 'build' ? 'Preparando construção…' : 'Analisando…';
    setChatBusy(true);

    try {
      const data = await api('/chat', {
        method: 'POST',
        body: JSON.stringify({
          transcript: text,
          project_id: projectId || null,
          history: previousHistory,
          mode,
        }),
      });
      thinking.remove();
      const reply = String(data?.reply || 'Resposta recebida.').trim();
      chatHistory.push({role: 'assistant', text: reply});
      chatHistory = chatHistory.slice(-(HISTORY_LIMIT * 2));
      renderChatHistory();
      if (status) {
        const execution = data?.execution;
        status.textContent = execution?.task_id
          ? `Tarefa ${execution.task_id} preparada · aguardando aprovação`
          : `${data?.profile || 'DevPilot'} · ${data?.provider || 'IA'}`;
      }
      if (data?.execution?.task_id && typeof load === 'function') {
        try { await load(); } catch (_) {}
      }
    } catch (error) {
      thinking.remove();
      const message = error?.message || 'Falha ao conversar com o DevPilot.';
      chatHistory.push({role: 'assistant', text: message});
      renderChatHistory();
      if (status) status.textContent = message;
      if (typeof toast === 'function') toast(message);
    } finally {
      setChatBusy(false);
      input?.focus();
    }
  };

  const bindGlobalSync = () => {
    window.addEventListener('devpilot:active-project-changed', syncProjects);
    window.addEventListener('devpilot:chat-mode-changed', syncModeButtons);
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && document.querySelector('#mc-ai-drawer.open')) closeAiChat();
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'i') {
        event.preventDefault();
        openAiChat(true);
      }
    });
  };

  const init = () => {
    ensureStylesheet();
    createAiChat();
    observeMetrics();
    bindGlobalSync();

    const panel = document.querySelector('#mission-control-panel');
    if (panel && panel.dataset.aiDashboardObserved !== '1') {
      panel.dataset.aiDashboardObserved = '1';
      new MutationObserver(() => {
        observeMetrics();
        scheduleCharts();
        syncProjects();
      }).observe(panel, {childList: true, subtree: true});
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();
