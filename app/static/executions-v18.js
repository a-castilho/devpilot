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

  let labelFrame = 0;
  function scheduleLabels() {
    if (labelFrame) return;
    labelFrame = window.requestAnimationFrame(() => {
      labelFrame = 0;
      executionLabels();
    });
  }

  installSingleRuntimeAuthority();

  document.addEventListener('devpilot:view-changed', event => {
    if (event.detail?.view === 'tasks' && !adoptOperationalRenderer()) {
      renderCurrentLoadingState();
      void requestOperationalTasksUi();
    }
    scheduleLabels();
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

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scheduleLabels, {once:true});
  } else {
    scheduleLabels();
  }

  document.documentElement.dataset.devpilotExecutions = 'v46';
  console.info('[DevPilot] Execuções V46 · runtime único operacional');
})();
