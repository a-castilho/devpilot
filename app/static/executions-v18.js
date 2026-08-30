(() => {
  'use strict';

  if (window.__devpilotExecutionsV18) return;
  window.__devpilotExecutionsV18 = true;

  const qs = (selector, root = document) => root.querySelector(selector);
  const qsa = (selector, root = document) => [...root.querySelectorAll(selector)];

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

  function replaceTextNodes(root) {
    if (!root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
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

      replaceTextNodes(view);
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
      const eyebrow = qs('.eyebrow', modal);
      if (eyebrow && /tarefa|execução/i.test(eyebrow.textContent || '')) eyebrow.textContent = 'NOVA EXECUÇÃO';
      const submit = qs('#task-submit', modal);
      if (submit && !/salvando/i.test(submit.textContent || '')) submit.textContent = 'Salvar execução';
    }

    const smartAction = qs('.dp-smart-action');
    if (smartAction) smartAction.textContent = '+ Nova execução';

    const analytics = qs('#task-analytics');
    if (analytics) {
      const heading = qs('.task-analytics-head h2', analytics);
      if (heading) heading.textContent = 'Indicadores das execuções';
      replaceTextNodes(analytics);
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
      if (result !== false && modal.open) {
        executionLabels();
        return true;
      }
    }

    modal.dataset.taskSource = source;

    try {
      if (!modal.open) modal.showModal();
    } catch (_) {
      modal.setAttribute('open', '');
    }

    executionLabels();
    window.requestAnimationFrame(() => qs('#task-context')?.focus?.());
    return true;
  }

  document.addEventListener('click', event => {
    const trigger = event.target.closest?.('[data-open="task-modal"]');
    if (!trigger) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    directOpenTaskModal(trigger.closest('#tasks-view') ? 'executions' : 'global');
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
  document.addEventListener('devpilot:execution-created', scheduleLabels);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scheduleLabels, {once: true});
  } else {
    scheduleLabels();
  }

  [80, 250, 700, 1400].forEach(delay => window.setTimeout(executionLabels, delay));

  document.documentElement.dataset.devpilotExecutions = 'v30';
  console.info('[DevPilot] Execuções V30 nomenclatura consolidada');
})();
