(() => {
  'use strict';
  if (typeof loadAllTasks !== 'function' || typeof renderTasks !== 'function' || typeof state === 'undefined') return;

  const originalLoadAllTasks = loadAllTasks;
  const originalRenderTasks = renderTasks;
  const PAGE_SIZE = 20;
  const MAX_LIMIT = 100;
  let currentLimit = Math.max(5, Number(state.tasks?.length || 0));
  let loadingMore = false;
  let hasMore = true;

  async function loadMoreTasks() {
    if (loadingMore || !hasMore) return;
    loadingMore = true;
    try {
      const nextLimit = Math.min(MAX_LIMIT, Math.max(PAGE_SIZE, currentLimit + PAGE_SIZE));
      const tasks = await api(`/ui/tasks?limit=${nextLimit}`);
      state.tasks = Array.isArray(tasks) ? tasks : [];
      currentLimit = state.tasks.length;
      hasMore = state.tasks.length >= nextLimit && nextLimit < MAX_LIMIT;
      state.tasksLoadedAll = !hasMore;
      renderTasks();
    } finally {
      loadingMore = false;
    }
  }

  function appendLoadMoreButton() {
    const table = document.querySelector('#tasks-table');
    if (!table || !state.tasks.length || !hasMore || table.querySelector('.load-more-tasks')) return;

    const row = document.createElement('tr');
    row.className = 'tasks-more';
    const cell = document.createElement('td');
    cell.colSpan = 5;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'link load-more-tasks';
    button.textContent = `Carregar mais ${PAGE_SIZE} tarefas`;
    button.addEventListener('click', async () => {
      button.disabled = true;
      button.textContent = 'Carregando…';
      try {
        await loadMoreTasks();
      } catch (error) {
        if (typeof toast === 'function') toast(error.message || 'Falha ao carregar tarefas');
      } finally {
        if (button.isConnected) {
          button.disabled = false;
          button.textContent = `Carregar mais ${PAGE_SIZE} tarefas`;
        }
      }
    });
    cell.appendChild(button);
    row.appendChild(cell);
    table.appendChild(row);
  }

  loadAllTasks = async function safeLoadAllTasks(force = false) {
    const result = await originalLoadAllTasks(force);
    currentLimit = Math.max(currentLimit, Number(state.tasks?.length || 0));
    hasMore = currentLimit >= PAGE_SIZE && currentLimit < MAX_LIMIT;
    appendLoadMoreButton();
    return result;
  };

  renderTasks = function safeRenderTasks() {
    originalRenderTasks();
    appendLoadMoreButton();
  };
})();
