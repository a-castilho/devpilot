(() => {
  'use strict';

  const tableBody = document.querySelector('#tasks-table');
  if (!tableBody) return;

  function taskByRow(row, index) {
    const id = row?.dataset?.taskId;
    if (id && typeof state !== 'undefined' && Array.isArray(state.tasks)) {
      const found = state.tasks.find(task => String(task.id) === String(id));
      if (found) return found;
    }
    return typeof state !== 'undefined' && Array.isArray(state.tasks) ? state.tasks[index] : null;
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
    button.className = 'link task-orchestrator-action';
    button.dataset.taskOrchestratorAction = action;
    button.dataset.taskId = taskId;
    button.textContent = label;
    return button;
  }

  function renderLearning(panel, runtime) {
    const learning = Array.isArray(runtime?.learning) ? runtime.learning : [];
    const latest = learning.length ? learning[learning.length - 1] : null;
    panel.replaceChildren();
    panel.className = 'task-orchestrator-panel';
    panel.dataset.taskOrchestratorPanel = runtime?.task_id || '';

    const status = document.createElement('div');
    status.className = 'task-orchestrator-status';
    const gate = runtime?.gate?.blocked ? ` · gate: ${(runtime.gate.reasons || []).join(', ') || 'autorização'}` : '';
    status.textContent = `Estado: ${runtime?.state || 'indisponível'} · próximo: ${runtime?.next_action || 'none'}${gate}`;
    panel.appendChild(status);

    if (runtime?.last_message) {
      const message = document.createElement('div');
      message.className = 'muted';
      message.textContent = runtime.last_message;
      panel.appendChild(message);
    }

    if (latest) {
      const title = document.createElement('strong');
      title.textContent = 'Aprendizado contextual';
      panel.appendChild(title);
      const details = document.createElement('div');
      details.className = 'muted';
      details.textContent = [
        `O que aconteceu: ${latest.happened || '—'}`,
        `Por que: ${latest.rationale || '—'}`,
        `Conceito: ${latest.concept || '—'}`,
        `Observe: ${latest.observe || '—'}`,
        `Aprendizado: ${latest.learned || '—'}`,
      ].join(' · ');
      panel.appendChild(details);
    }
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
      const cell = row?.lastElementChild;
      const panel = cell?.querySelector('[data-task-orchestrator-panel]') || document.createElement('div');
      if (cell && !panel.isConnected) cell.appendChild(panel);
      renderLearning(panel, runtime);
      if (runtime.state === 'archived') {
        row?.setAttribute('data-task-archived', '1');
        row?.setAttribute('hidden', 'hidden');
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
      const actionCell = row.lastElementChild;
      if (!actionCell || actionCell.dataset.taskOrchestratorEnhanced === '1') return;
      actionCell.dataset.taskOrchestratorEnhanced = '1';
      if (actionCell.textContent.trim() === '—') actionCell.textContent = '';

      const status = String(task.status || '');
      if (status === 'running') {
        actionCell.appendChild(actionButton('Parar', 'pause', task.id));
        actionCell.appendChild(actionButton('Cancelar', 'cancel', task.id));
      } else if (String(task.status) !== 'completed') {
        actionCell.appendChild(actionButton('Próximo', 'next', task.id));
        actionCell.appendChild(actionButton('Continuar automaticamente', 'auto', task.id));
        actionCell.appendChild(actionButton('Retomar', 'resume', task.id));
        actionCell.appendChild(actionButton('Excluir', 'archive', task.id));
      }

      if (status === 'completed') {
        const documentation = document.createElement('button');
        documentation.type = 'button';
        documentation.className = 'link task-documentation-generate';
        documentation.dataset.taskDocumentation = task.id;
        documentation.textContent = 'Gerar documentação';
        documentation.title = 'Gera um Markdown com contexto, runs, evidências, validação e aprendizado desta tarefa concluída.';
        actionCell.appendChild(documentation);
        actionCell.appendChild(actionButton('Arquivar', 'archive', task.id));
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

  document.addEventListener('devpilot:tasks-rendered', schedule);
  document.addEventListener('devpilot:authenticated-ui-ready', schedule);
  schedule();
})();
