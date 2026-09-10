(() => {
  'use strict';

  const tableBody = document.querySelector('#tasks-table');
  if (!tableBody) return;

  const TASK_STYLE_ID = 'devpilot-task-development-v2';
  const TASK_STYLE_HREF = '/assets/task-development-v2.css?v=20260829-1';

  function ensureStylesheet() {
    if (document.getElementById(TASK_STYLE_ID)) return;
    const link = document.createElement('link');
    link.id = TASK_STYLE_ID;
    link.rel = 'stylesheet';
    link.href = TASK_STYLE_HREF;
    document.head.appendChild(link);
  }

  function taskByRow(row, index) {
    const id = row?.dataset?.taskId;
    if (id && typeof state !== 'undefined' && Array.isArray(state.tasks)) {
      const found = state.tasks.find(task => String(task.id) === String(id));
      if (found) return found;
    }
    return typeof state !== 'undefined' && Array.isArray(state.tasks) ? state.tasks[index] : null;
  }

  function detailsRowFor(mainRow) {
    let row = mainRow?.nextElementSibling || null;
    while (row && !row.classList.contains('task-main-row')) {
      if (row.classList.contains('task-instructions-row')) return row;
      row = row.nextElementSibling;
    }
    return null;
  }

  function downloadMarkdown(filename, content) {
    const blob = new Blob([String(content || '')], {type: 'text/markdown;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename || 'implementacao.md';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function actionButton(label, action, taskId) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `link task-orchestrator-action task-action-${action}`;
    button.dataset.taskOrchestratorAction = action;
    button.dataset.taskId = taskId;
    button.textContent = label;
    return button;
  }

  function appendInfoChip(parent, label, value, tone = '') {
    const chip = document.createElement('span');
    chip.className = `task-runtime-chip${tone ? ` ${tone}` : ''}`;

    const key = document.createElement('small');
    key.textContent = label;
    const content = document.createElement('strong');
    content.textContent = String(value || '—');

    chip.append(key, content);
    parent.appendChild(chip);
  }

  function renderLearning(panel, runtime) {
    const learning = Array.isArray(runtime?.learning) ? runtime.learning : [];
    const latest = learning.length ? learning[learning.length - 1] : null;
    panel.replaceChildren();
    panel.className = 'task-orchestrator-panel';
    panel.dataset.taskOrchestratorPanel = runtime?.task_id || '';

    const summary = document.createElement('div');
    summary.className = 'task-runtime-summary';
    appendInfoChip(summary, 'Estado', runtime?.state || 'indisponível', runtime?.gate?.blocked ? 'blocked' : '');
    appendInfoChip(summary, 'Próxima ação', runtime?.next_action || 'nenhuma');
    if (runtime?.gate?.blocked) {
      appendInfoChip(summary, 'Gate', (runtime.gate.reasons || []).join(', ') || 'autorização', 'blocked');
    }
    panel.appendChild(summary);

    if (runtime?.last_message) {
      const message = document.createElement('p');
      message.className = 'task-runtime-message';
      message.textContent = runtime.last_message;
      panel.appendChild(message);
    }

    if (latest) {
      const section = document.createElement('section');
      section.className = 'task-learning-section';

      const title = document.createElement('strong');
      title.className = 'task-learning-title';
      title.textContent = 'Aprendizado contextual';
      section.appendChild(title);

      const grid = document.createElement('div');
      grid.className = 'task-learning-grid';
      const items = [
        ['O que aconteceu', latest.happened],
        ['Por que', latest.rationale],
        ['Conceito', latest.concept],
        ['Observe', latest.observe],
        ['Aprendizado', latest.learned],
      ];

      items.forEach(([label, value]) => {
        const item = document.createElement('article');
        item.className = 'task-learning-item';
        const key = document.createElement('small');
        key.textContent = label;
        const text = document.createElement('p');
        text.textContent = value || '—';
        item.append(key, text);
        grid.appendChild(item);
      });

      section.appendChild(grid);
      panel.appendChild(section);
    }
  }

  function panelHostFor(mainRow, taskId) {
    const detailsRow = detailsRowFor(mainRow);
    const cell = detailsRow?.querySelector('td') || mainRow?.lastElementChild;
    if (!cell) return null;

    let host = cell.querySelector(`[data-task-orchestrator-host="${CSS.escape(String(taskId))}"]`);
    if (!host) {
      host = document.createElement('div');
      host.className = 'task-orchestrator-panel-host';
      host.dataset.taskOrchestratorHost = String(taskId);
      cell.appendChild(host);
    }
    return host;
  }

  function actionGroupFor(actionCell) {
    if (!actionCell) return null;
    actionCell.classList.add('task-actions-cell');

    [...actionCell.childNodes].forEach(node => {
      if (node.nodeType === Node.TEXT_NODE && node.textContent.trim() === '—') node.remove();
    });

    let group = actionCell.querySelector(':scope > [data-task-orchestrator-actions]');
    if (!group) {
      group = document.createElement('div');
      group.className = 'task-orchestrator-actions';
      group.dataset.taskOrchestratorActions = '1';

      [...actionCell.children].forEach(child => {
        if (child.matches?.('button, a')) group.appendChild(child);
      });
      actionCell.appendChild(group);
    }
    return group;
  }

  async function orchestrate(button) {
    const taskId = button.dataset.taskId;
    const action = button.dataset.taskOrchestratorAction;
    if (!taskId || !action) return;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Executando…';
    try {
      const runtime = await api(`/tasks/${encodeURIComponent(taskId)}/${encodeURIComponent(action)}`, {method: 'POST'});
      const row = button.closest('tr.task-main-row');
      const host = panelHostFor(row, taskId);
      let panel = host?.querySelector('[data-task-orchestrator-panel]') || null;
      if (host && !panel) {
        panel = document.createElement('div');
        host.appendChild(panel);
      }
      if (panel) renderLearning(panel, runtime);

      if (runtime.state === 'archived') {
        row?.setAttribute('data-task-archived', '1');
        row?.setAttribute('hidden', 'hidden');
        detailsRowFor(row)?.setAttribute('hidden', 'hidden');
        toast('Tarefa arquivada; histórico e auditoria preservados');
      } else if (runtime.gate?.blocked) {
        toast('Fluxo parado no gate de autorização');
      } else {
        toast(`Tarefa: ${runtime.state}`);
      }
    } catch (error) {
      toast(error?.message || 'Falha no controle da tarefa');
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  async function generateDocumentation(button) {
    const taskId = button.dataset.taskDocumentation;
    if (!taskId) return;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Gerando…';
    try {
      const payload = await api(`/tasks/${encodeURIComponent(taskId)}/documentation`, {method: 'POST'});
      downloadMarkdown(payload.filename, payload.content);
      button.textContent = 'Gerar novamente';
      button.dataset.generated = '1';
      toast('Documentação da implementação gerada');
    } catch (error) {
      button.textContent = original;
      toast(error?.message || 'Falha ao gerar documentação');
    } finally {
      button.disabled = false;
    }
  }

  function enhanceTasks() {
    const rows = [...tableBody.querySelectorAll('tr.task-main-row')];
    rows.forEach((row, index) => {
      const task = taskByRow(row, index);
      if (!task) return;
      row.dataset.taskId = String(task.id);

      const actionCell = row.lastElementChild;
      if (!actionCell || actionCell.dataset.taskOrchestratorEnhanced === '1') return;
      actionCell.dataset.taskOrchestratorEnhanced = '1';
      const actions = actionGroupFor(actionCell);
      if (!actions) return;

      const statusValue = String(task.status || '').trim().toLowerCase();
      if (statusValue === 'running') {
        actions.appendChild(actionButton('Parar', 'pause', task.id));
        actions.appendChild(actionButton('Cancelar', 'cancel', task.id));
      } else if (statusValue === 'queued') {
        // Na fila o worker já é o dono do avanço. Não exibir comandos que
        // competem com a fila ou sugerem uma ação que não é necessária.
        actions.appendChild(actionButton('Arquivar', 'archive', task.id));
      } else if (['paused', 'pause_requested'].includes(statusValue)) {
        actions.appendChild(actionButton('Retomar', 'resume', task.id));
        actions.appendChild(actionButton('Arquivar', 'archive', task.id));
      } else if (statusValue !== 'completed') {
        actions.appendChild(actionButton('Próximo', 'next', task.id));
        actions.appendChild(actionButton('Continuar automaticamente', 'auto', task.id));
        actions.appendChild(actionButton('Arquivar', 'archive', task.id));
      }

      if (statusValue === 'completed') {
        const documentation = document.createElement('button');
        documentation.type = 'button';
        documentation.className = 'link task-documentation-generate';
        documentation.dataset.taskDocumentation = task.id;
        documentation.textContent = 'Gerar documentação';
        documentation.title = 'Gera um Markdown com contexto, runs, evidências, validação e aprendizado desta tarefa concluída.';
        actions.appendChild(documentation);
        actions.appendChild(actionButton('Arquivar', 'archive', task.id));
      }
    });
  }

  let runtimeSyncInFlight = false;
  async function syncRuntimeVisibility() {
    if (runtimeSyncInFlight) return;
    runtimeSyncInFlight = true;
    try {
      const payload = await api('/tasks/orchestrator/runtime');
      const states = payload?.states || {};
      [...tableBody.querySelectorAll('tr.task-main-row')].forEach((row, index) => {
        const task = taskByRow(row, index);
        const runtime = task ? states[String(task.id)] : null;
        const archived = runtime?.state === 'archived';
        row.toggleAttribute('hidden', archived);
        detailsRowFor(row)?.toggleAttribute('hidden', archived);
        if (archived) row.dataset.taskArchived = '1';
        else delete row.dataset.taskArchived;
      });
    } catch (error) {
      console.warn('[DevPilot] Falha ao sincronizar estado do orquestrador', error);
    } finally {
      runtimeSyncInFlight = false;
    }
  }

  let scheduled = false;
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      enhanceTasks();
      void syncRuntimeVisibility();
    });
  };

  tableBody.addEventListener('click', event => {
    const documentation = event.target.closest?.('[data-task-documentation]');
    if (documentation) {
      void generateDocumentation(documentation);
      return;
    }
    const action = event.target.closest?.('[data-task-orchestrator-action]');
    if (action) void orchestrate(action);
  });

  const originalRenderTasks = window.renderTasks;
  if (typeof originalRenderTasks === 'function' && !originalRenderTasks.__devpilotDocumentationWrapped) {
    const wrappedRenderTasks = function (...args) {
      const result = originalRenderTasks.apply(this, args);
      document.dispatchEvent(new CustomEvent('devpilot:tasks-rendered'));
      return result;
    };
    wrappedRenderTasks.__devpilotDocumentationWrapped = true;
    window.renderTasks = wrappedRenderTasks;
  }

  ensureStylesheet();
  document.addEventListener('devpilot:tasks-rendered', schedule);
  document.addEventListener('devpilot:authenticated-ui-ready', schedule);
  schedule();
})();
