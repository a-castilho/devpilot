(() => {
  'use strict';

  if (window.__devpilotExecutionsV18) return;
  window.__devpilotExecutionsV18 = true;

  const qs = (selector, root = document) => root.querySelector(selector);
  const qsa = (selector, root = document) => [...root.querySelectorAll(selector)];

  let operationalRenderer = null;
  let tasksFeaturePromise = null;

  function removeParallelLegacyStyle() {
    // Esse CSS pertence aos detalhes/orquestração e será recolocado pelo
    // tasksDetails quando necessário. Mantê-lo no shell base mistura duas
    // gerações da tela de Execuções.
    document.getElementById('devpilot-task-development-v2')?.remove();
  }

  function renderCurrentLoadingState() {
    const table = qs('#tasks-table');
    if (table) {
      table.innerHTML = '<tr><td colspan="3" class="tasks-v9-empty">Carregando interface atual de execuções…</td></tr>';
    }
    const count = qs('#tasks-v9-count');
    if (count) count.textContent = 'Carregando execuções…';
  }

  function adoptOperationalRenderer() {
    const current = typeof window.renderTasks === 'function' ? window.renderTasks : null;
    if (!window.__devpilotTasksOperationalV9 || !current || current === guardedRenderTasks) return false;

    operationalRenderer = current;
    window.__devpilotOperationalRenderTasks = current;
    document.documentElement.dataset.devpilotTasksRuntime = 'operational-v9';
    return true;
  }

  function requestOperationalTasksUi() {
    if (tasksFeaturePromise || typeof window.__devpilotLoadFeature !== 'function') return tasksFeaturePromise;

    tasksFeaturePromise = Promise.resolve(window.__devpilotLoadFeature('tasks'))
      .then(() => {
        if (!adoptOperationalRenderer()) return false;
        operationalRenderer();
        return true;
      })
      .catch(error => {
        console.error('[DevPilot] Falha ao carregar runtime atual de Execuções', error);
        return false;
      })
      .finally(() => {
        tasksFeaturePromise = null;
      });

    return tasksFeaturePromise;
  }

  function guardedRenderTasks() {
    if (typeof operationalRenderer === 'function') return operationalRenderer();

    if (adoptOperationalRenderer()) return operationalRenderer();

    // Nunca deixa o renderer legado de cinco colunas reaparecer enquanto o
    // bundle atual está sendo preparado. Isso também cobre chamadas diretas a
    // showView('tasks') feitas por cards/atalhos fora da navegação principal.
    renderCurrentLoadingState();
    if (qs('#tasks-view.active')) void requestOperationalTasksUi();
    return undefined;
  }

  function installSingleRuntimeAuthority() {
    removeParallelLegacyStyle();

    const current = typeof window.renderTasks === 'function' ? window.renderTasks : null;
    if (window.__devpilotTasksOperationalV9 && current) {
      operationalRenderer = current;
      window.__devpilotOperationalRenderTasks = current;
      document.documentElement.dataset.devpilotTasksRuntime = 'operational-v9';
      return;
    }

    if (current && !window.__devpilotLegacyRenderTasks) {
      window.__devpilotLegacyRenderTasks = current;
    }

    window.renderTasks = guardedRenderTasks;
    try { renderTasks = guardedRenderTasks; } catch (_) {}
    document.documentElement.dataset.devpilotTasksRuntime = 'guarded';

    if (qs('#tasks-view.active')) guardedRenderTasks();
  }

  const replacements = [
    [/\bTarefas por status\b/g, 'Execuções por status'],
    [/\bOrigem das tarefas\b/g, 'Origem das execuções'],
    [/\bIndicadores das tarefas\b/g, 'Indicadores das execuções'],
    [/\bProgresso das tarefas recentes\b/g, 'Progresso das execuções recentes'],
    [/\bNenhuma tarefa corresponde aos filtros\b/g, 'Nenhuma execução corresponde aos filtros'],
    [/\bTarefa sem título\b/g, 'Execução sem título'],
    [/\bEsta tarefa\b/g, 'Esta execução'],
    [/\besta tarefa\b/g, 'esta execução'],
    [/\bNova tarefa\b/g, 'Nova execução'],
    [/\bnova tarefa\b/g, 'nova execução'],
    [/\bTarefas\b/g, 'Execuções'],
    [/\btarefas\b/g, 'execuções'],
  ];

  function replaceTextNodes(target) {
    if (!target) return;
    const walker = document.createTreeWalker(target, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(node => {
      const original = String(node.nodeValue || '');
      if (!original.trim()) return;
      let next = original;
      replacements.forEach(([pattern, value]) => { next = next.replace(pattern, value); });
      if (next !== original) node.nodeValue = next;
    });
  }

  function executionLabels() {
    const nav = qs('.nav[data-view="tasks"]');
    if (nav) nav.textContent = 'Execuções';

    qsa('.mobile-simple-nav button, .mobile-simple-nav a, .bottom-nav button, .bottom-nav a, [data-mobile-view="tasks"]').forEach(item => {
      const text = String(item.textContent || '').trim();
      if (/^(tarefas|desenvolvimento)$/i.test(text)) item.textContent = 'Execuções';
    });

    const view = qs('#tasks-view');
    if (view) {
      const eyebrow = qs('.tasks-v9-header .eyebrow', view);
      const title = qs('.tasks-v9-header h2', view);
      const description = qs('.tasks-v9-header p', view);
      if (eyebrow) eyebrow.textContent = 'EXECUÇÕES';
      if (title) title.textContent = 'Execuções';
      if (description) {
        description.textContent = 'Acompanhe análises, correções e implementações em execução. Abra os detalhes somente quando precisar do contexto completo.';
      }
      replaceTextNodes(view);
    }

    if (qs('#tasks-view.active')) {
      const pageTitle = qs('#page-title');
      if (pageTitle) pageTitle.textContent = 'Execuções';
    }

    qsa('[data-open="task-modal"]').forEach(button => {
      const text = String(button.textContent || '').trim().toLowerCase();
      if (text.includes('nova tarefa') || text.includes('novo desenvolvimento') || text.includes('nova execução')) {
        button.textContent = '+ Nova execução';
      }
    });

    const modal = qs('#task-modal');
    if (modal) {
      replaceTextNodes(modal);
      const eyebrow = qs('.task-modal-heading .eyebrow, .eyebrow', modal);
      if (eyebrow && /tarefa|execução/i.test(eyebrow.textContent || '')) eyebrow.textContent = 'NOVA EXECUÇÃO';
      const submit = qs('#task-submit', modal);
      if (submit && !/salvando/i.test(submit.textContent || '')) submit.textContent = 'Salvar execução';
    }

    const analytics = qs('#task-analytics');
    if (analytics) {
      const heading = qs('.task-analytics-head h2', analytics);
      if (heading) heading.textContent = 'Indicadores das execuções';
      replaceTextNodes(analytics);
    }
  }

  const DELIVERY_CACHE_TTL_MS = 30000;
  const DELIVERY_VISIBLE_LIMIT = 12;
  const deliveryCache = new Map();
  const deliveryRequests = new Map();
  let accessLinkFrame = 0;

  const stateTasks = () => (typeof state !== 'undefined' && Array.isArray(state.tasks) ? state.tasks : []);
  const stateProjects = () => (typeof state !== 'undefined' && Array.isArray(state.projects) ? state.projects : []);
  const safePublicUrl = value => {
    const candidate = String(value || '').trim();
    return /^https:\/\//i.test(candidate) ? candidate : '';
  };
  const readyDelivery = delivery => String(delivery?.status || '').trim().toLowerCase() === 'ready' && Boolean(safePublicUrl(delivery?.url));
  const projectById = projectId => stateProjects().find(project => String(project?.id || '') === String(projectId || ''));

  async function fetchReadyDelivery(projectId) {
    const key = String(projectId || '').trim();
    if (!key || typeof api !== 'function') return null;
    const cached = deliveryCache.get(key);
    if (cached && Date.now() - cached.at < DELIVERY_CACHE_TTL_MS) return cached.value;
    if (deliveryRequests.has(key)) return deliveryRequests.get(key);

    const request = api(`/projects/${encodeURIComponent(key)}/delivery`)
      .then(value => {
        const delivery = readyDelivery(value) ? {status:'ready', url:safePublicUrl(value.url)} : null;
        deliveryCache.set(key, {at:Date.now(), value:delivery});
        return delivery;
      })
      .catch(() => null)
      .finally(() => deliveryRequests.delete(key));
    deliveryRequests.set(key, request);
    return request;
  }

  function accessLink(project, url, className) {
    const link = document.createElement('a');
    link.className = `project-ready-access-link ${className}`.trim();
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.title = `Abrir ${project?.name || 'projeto'} · ${url}`;
    link.setAttribute('aria-label', `Abrir projeto ${project?.name || ''}`.trim());
    link.innerHTML = '<span aria-hidden="true">🌐</span> Abrir projeto <span aria-hidden="true">↗</span>';
    link.addEventListener('click', event => event.stopPropagation());
    return link;
  }

  async function decorateExecutionProjectLinks() {
    const rows = qsa('#tasks-table tr.task-main-row[data-task-id], #tasks-table tr.tasks-v9-row[data-task-id]').slice(0, DELIVERY_VISIBLE_LIMIT);
    if (!rows.length) return;
    const byTask = new Map(stateTasks().map(task => [String(task?.id || ''), task]));
    const projectIds = [...new Set(rows.map(row => String(byTask.get(String(row.dataset.taskId || ''))?.project_id || '')).filter(Boolean))];
    const deliveries = new Map(await Promise.all(projectIds.map(async projectId => [projectId, await fetchReadyDelivery(projectId)])));

    rows.forEach(row => {
      const task = byTask.get(String(row.dataset.taskId || ''));
      const projectId = String(task?.project_id || '');
      const project = projectById(projectId);
      const delivery = deliveries.get(projectId);
      const host = qs('.tasks-v9-main, .task-primary-cell, td', row);
      const current = qs('.project-ready-access-link-execution', row);
      if (!project || !delivery?.url || !host) {
        current?.remove();
        return;
      }
      if (current) {
        current.href = delivery.url;
        current.title = `Abrir ${project.name || 'projeto'} · ${delivery.url}`;
        return;
      }
      const link = accessLink(project, delivery.url, 'project-ready-access-link-execution');
      link.style.cssText = 'display:inline-flex;align-items:center;gap:5px;margin-top:7px;padding:6px 9px;border:1px solid rgba(54,211,153,.28);border-radius:9px;color:#7ce7cf;text-decoration:none;font-size:.76rem;font-weight:800;max-width:100%';
      host.appendChild(link);
    });
  }

  async function decorateOverviewProjectLinks() {
    const recent = qs('#recent-tasks');
    if (!recent) return;
    const recentProjectIds = [...new Set(stateTasks().slice(0, 6).map(task => String(task?.project_id || '')).filter(Boolean))];
    if (!recentProjectIds.length) {
      qs('#overview-project-ready-links')?.remove();
      return;
    }

    const deliveries = new Map(await Promise.all(recentProjectIds.map(async projectId => [projectId, await fetchReadyDelivery(projectId)])));
    const ready = recentProjectIds
      .map(projectId => ({project:projectById(projectId), delivery:deliveries.get(projectId)}))
      .filter(item => item.project && item.delivery?.url)
      .slice(0, 6);

    if (!ready.length) {
      qs('#overview-project-ready-links')?.remove();
      return;
    }

    let host = qs('#overview-project-ready-links');
    if (!host) {
      host = document.createElement('div');
      host.id = 'overview-project-ready-links';
      host.style.cssText = 'display:grid;gap:7px;margin-top:12px;padding-top:12px;border-top:1px solid rgba(255,255,255,.08)';
      recent.insertAdjacentElement('afterend', host);
    }
    host.innerHTML = '<strong style="font-size:.76rem;letter-spacing:.04em;color:#9eacc2">PROJETOS DISPONÍVEIS PARA TESTE</strong>';

    ready.forEach(({project, delivery}) => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:8px;min-width:0';
      const name = document.createElement('span');
      name.textContent = project.name || 'Projeto';
      name.style.cssText = 'min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.8rem;color:#c8d3e6';
      row.appendChild(name);
      const link = accessLink(project, delivery.url, 'project-ready-access-link-overview');
      link.style.cssText = 'display:inline-flex;align-items:center;gap:4px;flex:0 0 auto;padding:6px 8px;border:1px solid rgba(54,211,153,.28);border-radius:9px;color:#7ce7cf;text-decoration:none;font-size:.72rem;font-weight:800';
      row.appendChild(link);
      host.appendChild(row);
    });
  }

  function scheduleProjectAccessLinks() {
    if (accessLinkFrame) return;
    accessLinkFrame = window.requestAnimationFrame(() => {
      accessLinkFrame = 0;
      if (qs('#tasks-view.active')) void decorateExecutionProjectLinks();
      if (qs('#overview-view.active')) void decorateOverviewProjectLinks();
    });
  }

  let labelFrame = 0;
  function scheduleLabels() {
    if (labelFrame) return;
    labelFrame = window.requestAnimationFrame(() => {
      labelFrame = 0;
      executionLabels();
      scheduleProjectAccessLinks();
    });
  }

  installSingleRuntimeAuthority();

  document.addEventListener('devpilot:view-changed', event => {
    if (event.detail?.view === 'tasks' && !adoptOperationalRenderer()) {
      renderCurrentLoadingState();
      void requestOperationalTasksUi();
    }
    scheduleLabels();
    if (event.detail?.view === 'tasks' || event.detail?.view === 'overview') scheduleProjectAccessLinks();
  });
  document.addEventListener('devpilot:page-ready', scheduleLabels);
  document.addEventListener('devpilot:tasks-rendered', scheduleLabels);
  document.addEventListener('devpilot:feature-ready', event => {
    if (event.detail?.feature === 'tasks') {
      adoptOperationalRenderer();
      removeParallelLegacyStyle();
    }
    scheduleLabels();
  });
  document.addEventListener('devpilot:execution-created', scheduleLabels);
  document.addEventListener('devpilot:authenticated-ui-ready', scheduleProjectAccessLinks);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scheduleLabels, {once:true});
  } else {
    scheduleLabels();
  }

  document.documentElement.dataset.devpilotExecutions = 'v47';
  console.info('[DevPilot] Execuções V47 · runtime único operacional + acesso ao projeto publicado');
})();
