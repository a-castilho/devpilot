(() => {
  'use strict';

  if (window.__devpilotTaskQueueCleanupReady) return;
  window.__devpilotTaskQueueCleanupReady = true;

  function isSuperAdmin() {
    try {
      return String(state?.currentUser?.role || '').toUpperCase() === 'SUPER_ADMIN';
    } catch (_) {
      return false;
    }
  }

  function ensureButton() {
    if (!isSuperAdmin()) return;
    const view = document.getElementById('tasks-view');
    if (!view || document.getElementById('task-queue-cleanup')) return;
    const head = view.querySelector('.section-head');
    if (!head) return;

    const button = document.createElement('button');
    button.id = 'task-queue-cleanup';
    button.type = 'button';
    button.className = 'ghost';
    button.textContent = 'Excluir paradas';
    button.title = 'Remove definitivamente da fila apenas tarefas QUEUED que nunca iniciaram execução';
    head.appendChild(button);

    button.addEventListener('click', async () => {
      if (button.disabled) return;
      if (!window.confirm(`Excluir todas as tarefas paradas que nunca iniciaram?\n\nAções já executadas e tarefas com histórico de execução serão preservadas.`)) return;

      const original = button.textContent;
      button.disabled = true;
      button.textContent = 'Excluindo…';
      try {
        const result = await api('/tasks/queued', {method: 'DELETE'});
        const deleted = Number(result?.deleted || 0);
        toast(deleted ? `${deleted} tarefa(s) parada(s) excluída(s)` : 'Nenhuma tarefa elegível para exclusão');
        state.tasksLoadedAll = false;
        await loadAllTasks(true);
        await loadDashboard();
      } catch (error) {
        toast(error?.message || 'Falha ao excluir tarefas paradas');
      } finally {
        button.disabled = false;
        button.textContent = original;
      }
    });
  }

  ensureButton();
  document.addEventListener('devpilot:feature-ready', event => {
    if (event.detail?.feature === 'tasks') ensureButton();
  });
  document.addEventListener('devpilot:dashboard-revealed', ensureButton);
})();
