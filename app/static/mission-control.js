(() => {
  'use strict';

  const STORAGE_KEY = 'devpilot-workspace-mode';
  const MODE_MISSION = 'mission';
  const MODE_PROFESSIONAL = 'professional';
  let overviewSnapshot = null;
  let providersSnapshot = [];
  let providersLoaded = false;

  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);

  const getState = () => {
    try {
      return typeof state !== 'undefined' ? state : {projects: [], tasks: [], currentUser: null};
    } catch (_) {
      return {projects: [], tasks: [], currentUser: null};
    }
  };

  const statusLabel = value => {
    const normalized = String(value || 'unknown').replaceAll('_', ' ').trim();
    return normalized || 'desconhecido';
  };

  const statusTone = value => {
    const normalized = String(value || '').toLowerCase();
    if (['failed', 'error', 'blocked', 'cancelled', 'rejected'].some(term => normalized.includes(term))) return 'danger';
    if (['running', 'active', 'in_progress', 'processing', 'queued'].some(term => normalized.includes(term))) return 'active';
    if (['awaiting', 'pending', 'review', 'approval'].some(term => normalized.includes(term))) return 'warning';
    if (['completed', 'done', 'success', 'ready', 'healthy', 'operational'].some(term => normalized.includes(term))) return 'ok';
    return 'neutral';
  };

  const projectTaskCount = projectId => {
    const current = getState();
    return (current.tasks || []).filter(task => String(task.project_id) === String(projectId)).length;
  };

  const ensureStylesheet = () => {
    if (document.querySelector('link[data-mission-control-style]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/assets/mission-control.css';
    link.dataset.missionControlStyle = 'true';
    document.head.appendChild(link);
  };

  const ensureEnhancements = () => {
    if (document.querySelector('script[data-mission-control-ai-dashboard]')) return;
    const script = document.createElement('script');
    script.src = '/assets/mission-control-ai-dashboard.js?v=20260824-1';
    script.defer = true;
    script.dataset.missionControlAiDashboard = '1';
    document.head.appendChild(script);
  };

  const createPanel = () => {
    const overview = document.querySelector('#overview-view');
    if (!overview || document.querySelector('#mission-control-panel')) return;

    const panel = document.createElement('section');
    panel.id = 'mission-control-panel';
    panel.className = 'mc-panel';
    panel.setAttribute('aria-label', 'DevPilot Mission Control');
    panel.innerHTML = `
      <div class="mc-stars" aria-hidden="true"></div>
      <div class="mc-topline">
        <div>
          <span class="mc-kicker">DEV PILOT · MISSION CONTROL</span>
          <h2>Ponte de comando</h2>
          <p id="mc-mission-summary">Conectando aos sistemas da nave…</p>
        </div>
        <div class="mc-ship-mark" aria-hidden="true">
          <svg viewBox="0 0 160 90" role="img">
            <path d="M20 55 65 30h48l28 22-31 8-16 20H62L48 64z" />
            <path class="mc-ship-line" d="M49 54h70M71 31l-9 29m37-29 11 28M31 55l18 9" />
            <circle cx="83" cy="48" r="7" />
          </svg>
        </div>
      </div>

      <div class="mc-command-grid">
        <article class="mc-command-card mc-primary-card">
          <div class="mc-card-head"><span>STATUS DA MISSÃO</span><i class="mc-live-dot" aria-hidden="true"></i></div>
          <strong id="mc-system-status">AGUARDANDO DADOS</strong>
          <p id="mc-system-detail">O painel usa somente dados já registrados no DevPilot.</p>
          <div class="mc-actions">
            <button class="mc-action mc-action-primary" type="button" data-mc-action="new-task">＋ Nova missão</button>
            <button class="mc-action" type="button" data-mc-action="projects">Abrir frota</button>
          </div>
        </article>
        <article class="mc-radar-card" aria-label="Radar operacional">
          <div class="mc-radar" aria-hidden="true"><span></span><i></i><b></b></div>
          <div><span class="mc-kicker">RADAR</span><strong id="mc-radar-title">Sincronizando</strong><small id="mc-radar-detail">Lendo projetos e tarefas recentes</small></div>
        </article>
      </div>

      <div class="mc-metrics" id="mc-metrics"></div>

      <div class="mc-sector-grid">
        <article class="mc-sector"><span class="mc-sector-icon">⌖</span><div><small>NAVEGAÇÃO</small><strong id="mc-sector-navigation">—</strong><span>projetos conectados</span></div></article>
        <article class="mc-sector"><span class="mc-sector-icon">⚙</span><div><small>ENGENHARIA</small><strong id="mc-sector-engineering">—</strong><span>tarefas em andamento</span></div></article>
        <article class="mc-sector"><span class="mc-sector-icon">◈</span><div><small>IA DE BORDO</small><strong id="mc-sector-ai">—</strong><span>conexões ativas</span></div></article>
        <article class="mc-sector"><span class="mc-sector-icon">✓</span><div><small>HANGAR</small><strong id="mc-sector-hangar">—</strong><span>tarefas concluídas</span></div></article>
      </div>

      <div class="mc-main-grid">
        <article class="mc-module">
          <div class="mc-module-title"><div><span class="mc-kicker">FROTA</span><h3>Naves / projetos</h3></div><button type="button" data-mc-action="projects">Ver projetos</button></div>
          <div id="mc-fleet" class="mc-fleet"></div>
        </article>
        <article class="mc-module">
          <div class="mc-module-title"><div><span class="mc-kicker">MISSÕES RECENTES</span><h3>Fluxo operacional</h3></div><button type="button" data-mc-action="tasks">Ver tarefas</button></div>
          <div id="mc-task-feed" class="mc-task-feed"></div>
        </article>
      </div>

      <div class="mc-flight-path" aria-label="Fluxo de missão do DevPilot">
        <span>ESCANEAR</span><i>›</i><span>PLANEJAR</span><i>›</i><span>EXECUTAR</span><i>›</i><span>TESTAR</span><i>›</i><span>IMPLANTAR</span><i>›</i><span>REGISTRAR</span>
      </div>
    `;
    overview.prepend(panel);
  };

  const createToggle = () => {
    const actions = document.querySelector('header .header-actions');
    if (!actions || document.querySelector('#mission-control-toggle')) return;
    const button = document.createElement('button');
    button.id = 'mission-control-toggle';
    button.type = 'button';
    button.className = 'ghost mc-toggle';
    actions.prepend(button);
    button.addEventListener('click', () => {
      const next = document.body.classList.contains('mission-control-mode') ? MODE_PROFESSIONAL : MODE_MISSION;
      setMode(next, true);
    });
  };

  const renderMetrics = overview => {
    const target = document.querySelector('#mc-metrics');
    if (!target) return;
    const current = getState();
    const recentPending = (current.tasks || []).filter(task => String(task.status).toLowerCase() === 'awaiting_approval').length;
    const values = [
      ['PROJETOS', overview?.projects ?? (current.projects || []).length],
      ['TAREFAS', overview?.tasks ?? '—'],
      ['EM ANDAMENTO', overview?.active ?? '—'],
      ['CONCLUÍDAS', overview?.completed ?? '—'],
      ['APROVAÇÕES RECENTES', recentPending],
    ];
    target.innerHTML = values.map(([label, value]) => `<div><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`).join('');
  };

  const renderFleet = () => {
    const target = document.querySelector('#mc-fleet');
    if (!target) return;
    const projects = getState().projects || [];
    if (!projects.length) {
      target.innerHTML = '<div class="mc-empty">Nenhum projeto conectado à frota.</div>';
      return;
    }
    target.innerHTML = projects.slice(0, 8).map(project => {
      const tone = statusTone(project.status);
      const repo = project.repository_url || 'Repositório não informado';
      return `
        <button class="mc-ship-card" type="button" data-mc-project="${escapeHtml(project.id)}">
          <span class="mc-ship-icon" aria-hidden="true">▲</span>
          <span class="mc-ship-copy">
            <small>${escapeHtml(statusLabel(project.status)).toUpperCase()}</small>
            <strong>${escapeHtml(project.name)}</strong>
            <em>${escapeHtml(repo)}</em>
            <span>branch ${escapeHtml(project.default_branch || '—')} · ${projectTaskCount(project.id)} tarefa(s) carregada(s)</span>
          </span>
          <i class="mc-status-light ${tone}" aria-label="${escapeHtml(statusLabel(project.status))}"></i>
        </button>`;
    }).join('');
  };

  const renderTasks = () => {
    const target = document.querySelector('#mc-task-feed');
    if (!target) return;
    const tasks = getState().tasks || [];
    if (!tasks.length) {
      target.innerHTML = '<div class="mc-empty">Nenhuma missão registrada.</div>';
      return;
    }
    target.innerHTML = tasks.slice(0, 6).map(task => {
      const created = task.created_at ? new Date(task.created_at).toLocaleString('pt-BR') : 'data não informada';
      return `
        <div class="mc-task-row">
          <i class="mc-status-light ${statusTone(task.status)}" aria-hidden="true"></i>
          <div><strong>${escapeHtml(task.title)}</strong><span>${escapeHtml(task.source || 'DevPilot')} · ${escapeHtml(created)}</span></div>
          <small>${escapeHtml(statusLabel(task.status)).toUpperCase()}</small>
        </div>`;
    }).join('');
  };

  const renderProviders = () => {
    const active = providersSnapshot.filter(provider => provider && provider.enabled !== false).length;
    const target = document.querySelector('#mc-sector-ai');
    if (target) target.textContent = providersLoaded ? String(active) : '—';
  };

  const readOverviewFromDom = () => {
    const values = {};
    document.querySelectorAll('#metrics .metric').forEach(metric => {
      const label = metric.querySelector('span')?.textContent?.trim().toLowerCase();
      const raw = metric.querySelector('strong')?.textContent?.trim();
      const value = Number(raw);
      if (!label || !Number.isFinite(value)) return;
      if (label === 'projetos') values.projects = value;
      if (label === 'tarefas') values.tasks = value;
      if (label === 'em andamento') values.active = value;
      if (label === 'concluídas') values.completed = value;
    });
    return Object.keys(values).length ? values : null;
  };

  const renderMission = overview => {
    if (overview) overviewSnapshot = overview;
    createPanel();
    const current = getState();
    const data = overviewSnapshot || readOverviewFromDom() || {};
    const projects = current.projects || [];
    const tasks = current.tasks || [];
    const active = data.active ?? tasks.filter(task => ['running', 'in_progress', 'processing', 'queued'].includes(String(task.status).toLowerCase())).length;
    const completed = data.completed ?? tasks.filter(task => ['completed', 'done', 'success'].includes(String(task.status).toLowerCase())).length;
    const pending = tasks.filter(task => String(task.status).toLowerCase() === 'awaiting_approval').length;

    renderMetrics(data);
    renderFleet();
    renderTasks();
    renderProviders();

    const nav = document.querySelector('#mc-sector-navigation');
    const engineering = document.querySelector('#mc-sector-engineering');
    const hangar = document.querySelector('#mc-sector-hangar');
    if (nav) nav.textContent = String(data.projects ?? projects.length);
    if (engineering) engineering.textContent = String(active ?? '—');
    if (hangar) hangar.textContent = String(completed ?? '—');

    const status = document.querySelector('#mc-system-status');
    const detail = document.querySelector('#mc-system-detail');
    const missionSummary = document.querySelector('#mc-mission-summary');
    const radarTitle = document.querySelector('#mc-radar-title');
    const radarDetail = document.querySelector('#mc-radar-detail');
    const authenticated = Boolean(current.currentUser);

    if (status) status.textContent = authenticated ? 'SESSÃO CONECTADA' : 'CONEXÃO NECESSÁRIA';
    if (detail) detail.textContent = authenticated
      ? `${projects.length} projeto(s) carregado(s) · ${tasks.length} tarefa(s) recente(s) disponíveis no painel.`
      : 'Autentique-se para carregar os dados operacionais da nave.';
    if (missionSummary) missionSummary.textContent = projects.length
      ? `Frota carregada com ${projects.length} projeto(s). Selecione uma missão ou abra um setor.`
      : 'Conecte um projeto para iniciar a primeira missão.';
    if (radarTitle) radarTitle.textContent = pending ? `${pending} aprovação(ões) recente(s)` : `${active || 0} tarefa(s) em andamento`;
    if (radarDetail) radarDetail.textContent = pending
      ? 'Há tarefas recentes aguardando autorização.'
      : 'Radar calculado a partir dos dados atualmente carregados.';
  };

  const loadProviders = async () => {
    if (providersLoaded) return;
    try {
      if (typeof api !== 'function') return;
      providersSnapshot = await api('/providers');
      providersLoaded = true;
      renderProviders();
    } catch (_) {
      providersLoaded = false;
      providersSnapshot = [];
      renderProviders();
    }
  };

  const setMode = (mode, persist = false) => {
    const mission = mode === MODE_MISSION;
    document.body.classList.toggle('mission-control-mode', mission);
    document.body.dataset.workspaceMode = mission ? MODE_MISSION : MODE_PROFESSIONAL;
    const button = document.querySelector('#mission-control-toggle');
    if (button) {
      button.setAttribute('aria-pressed', mission ? 'true' : 'false');
      button.textContent = mission ? '▣ Modo profissional' : '🚀 Mission Control';
      button.title = mission ? 'Voltar à interface profissional' : 'Abrir ponte de comando';
    }
    if (persist) localStorage.setItem(STORAGE_KEY, mission ? MODE_MISSION : MODE_PROFESSIONAL);
    if (mission) {
      try {
        if (typeof showView === 'function') showView('overview');
      } catch (_) {}
      renderMission(overviewSnapshot);
      loadProviders();
    }
  };

  const bindActions = () => {
    document.addEventListener('click', event => {
      const action = event.target.closest('[data-mc-action]');
      if (action) {
        const name = action.dataset.mcAction;
        if (name === 'new-task') document.querySelector('#task-modal')?.showModal();
        if (name === 'projects' && typeof showView === 'function') showView('projects');
        if (name === 'tasks' && typeof showView === 'function') showView('tasks');
      }
      const project = event.target.closest('[data-mc-project]');
      if (project && typeof showView === 'function') showView('projects');
    });
  };

  const hookExistingRender = () => {
    try {
      if (typeof renderOverview !== 'function' || renderOverview.__missionControlHooked) return;
      const original = renderOverview;
      const wrapped = function missionControlRenderOverview(overview) {
        const result = original(overview);
        renderMission(overview);
        return result;
      };
      wrapped.__missionControlHooked = true;
      renderOverview = wrapped;
    } catch (_) {}
  };

  const init = () => {
    ensureStylesheet();
    createPanel();
    createToggle();
    bindActions();
    hookExistingRender();
    renderMission(overviewSnapshot);
    ensureEnhancements();
    const saved = localStorage.getItem(STORAGE_KEY);
    setMode(saved === MODE_MISSION ? MODE_MISSION : MODE_PROFESSIONAL, false);
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();
