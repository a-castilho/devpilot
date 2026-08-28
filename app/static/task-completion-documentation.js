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

  function enhanceCompletedTasks() {
    const rows = [...tableBody.querySelectorAll('tr.task-main-row')];
    rows.forEach((row, index) => {
      const task = taskByRow(row, index);
      if (!task || String(task.status) !== 'completed') return;

      const actionCell = row.lastElementChild;
      if (!actionCell || actionCell.querySelector('[data-task-documentation]')) return;

      if (actionCell.textContent.trim() === '—') actionCell.textContent = '';
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'link task-documentation-generate';
      button.dataset.taskDocumentation = task.id;
      button.textContent = 'Gerar documentação';
      button.title = 'Gera um Markdown com contexto, runs, evidências, validação e aprendizado desta tarefa concluída.';
      actionCell.appendChild(button);
    });
  }

  let scheduled = false;
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      enhanceCompletedTasks();
    });
  };

  tableBody.addEventListener('click', event => {
    const button = event.target.closest?.('[data-task-documentation]');
    if (!button) return;
    void generateDocumentation(button);
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
