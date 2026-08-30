(() => {
  'use strict';

  if (window.__devpilotExecutionsV18) return;
  window.__devpilotExecutionsV18 = true;

  const qs = (selector, root = document) => root.querySelector(selector);
  const qsa = (selector, root = document) => [...root.querySelectorAll(selector)];

  function executionLabels() {
    const nav = qs('.nav[data-view="tasks"]');
    if (nav) nav.textContent = 'Execuções';

    const active = qs('#tasks-view.active');
    const pageTitle = qs('#page-title');
    if (active && pageTitle) pageTitle.textContent = 'Execuções';

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
    }

    qsa('[data-open="task-modal"]').forEach(button => {
      const text = String(button.textContent || '').trim().toLowerCase();
      if (text.includes('nova tarefa') || text.includes('novo desenvolvimento')) {
        button.textContent = '+ Nova execução';
      }
    });

    const smartAction = qs('.dp-smart-action');
    if (smartAction) smartAction.textContent = '+ Nova execução';

    const analytics = qs('#task-analytics');
    if (analytics) {
      const heading = qs('.task-analytics-head h2', analytics);
      if (heading) heading.textContent = 'Indicadores das execuções';

      qsa('.task-chart h3', analytics).forEach(node => {
        node.textContent = String(node.textContent || '')
          .replace('Tarefas por status', 'Execuções por status')
          .replace('Origem das tarefas', 'Origem das execuções');
      });
    }
  }

  function directOpenTaskModal(source = 'execution') {
    const modal = qs('#task-modal');

    if (!modal) {
      console.warn('[DevPilot] modal de execução indisponível');
      return false;
    }

    if (typeof window.devpilotOpenTaskModal === 'function') {
      const result = window.devpilotOpenTaskModal({source});
      if (result !== false && modal.open) return true;
    }

    modal.dataset.taskSource = source;

    try {
      if (!modal.open) modal.showModal();
    } catch (_) {
      modal.setAttribute('open', '');
    }

    window.requestAnimationFrame(() => {
      qs('#task-context')?.focus?.();
    });

    return true;
  }

  document.addEventListener('click', event => {
    const trigger = event.target.closest?.('[data-open="task-modal"]');
    if (!trigger) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    directOpenTaskModal(
      trigger.closest('#tasks-view') ? 'executions' : 'global'
    );
  }, true);

  document.addEventListener('click', event => {
    const trigger = event.target.closest?.('.dp-smart-action');
    if (!trigger) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    qs('.mobile-simple-close')?.click();
    directOpenTaskModal('mobile-smart-menu');
  }, true);

  const scheduleLabels = () => window.requestAnimationFrame(executionLabels);

  document.addEventListener('devpilot:view-changed', scheduleLabels);
  document.addEventListener('devpilot:tasks-rendered', scheduleLabels);
  document.addEventListener('devpilot:feature-ready', scheduleLabels);
  document.addEventListener('devpilot:viewport-adapted', scheduleLabels);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scheduleLabels, {once: true});
  } else {
    scheduleLabels();
  }

  [80, 250, 700, 1400].forEach(delay => {
    window.setTimeout(executionLabels, delay);
  });

  document.documentElement.dataset.devpilotExecutions = 'v18';
  console.info('[DevPilot] Execuções V18 ativo');
})();
