(() => {
  'use strict';

  const STYLE_ID = 'devpilot-delete-action-style';
  const PROJECT_BUTTON_CLASS = 'delete-project';
  const TASK_BUTTON_CLASS = 'delete-task';
  const DELETABLE_TASK_STATUSES = new Set([
    'awaiting_approval',
    'completed',
    'failed',
    'blocked',
  ]);

  function token() {
    return String(localStorage.getItem('devpilot-token') || '').trim();
  }

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .delete-project,
      .delete-task {
        border: 1px solid rgba(239, 68, 68, .55) !important;
        color: #f87171 !important;
        background: rgba(127, 29, 29, .12) !important;
        margin-left: .35rem;
      }
      .delete-project:hover,
      .delete-project:focus-visible,
      .delete-task:hover,
      .delete-task:focus-visible {
        border-color: #ef4444 !important;
        background: rgba(127, 29, 29, .28) !important;
        color: #fecaca !important;
      }
      .delete-project[disabled],
      .delete-task[disabled] {
        opacity: .55;
        cursor: wait;
      }
    `;
    document.head.appendChild(style);
  }

  async function currentUserIsSuperAdmin() {
    if (!token()) return false;
    try {
      const response = await fetch('/api/auth/me', {
        headers: {Authorization: `Bearer ${token()}`},
        cache: 'no-store',
      });
      if (!response.ok) return false;
      const user = await response.json();
      return String(user?.role || '').toUpperCase() === 'SUPER_ADMIN';
    } catch (_) {
      return false;
    }
  }

  function projectInfo(card) {
    const analyze = card.querySelector('.analyze[data-id]');
    const name = card.querySelector('h3')?.textContent?.trim() || 'este projeto';
    return {
      id: String(analyze?.dataset?.id || '').trim(),
      name,
    };
  }

  function taskInfo(row) {
    const idSource = row.querySelector('[data-id]') || row.nextElementSibling?.querySelector('[data-id]');
    const title = row.querySelector('strong')?.textContent?.trim() || 'esta tarefa';
    const statusText = row.querySelector('.status')?.textContent?.trim().toLowerCase() || '';
    return {
      id: String(idSource?.dataset?.id || '').trim(),
      title,
      status: statusText.replaceAll(' ', '_'),
    };
  }

  async function deleteRequest(path, fallbackMessage) {
    const response = await fetch(path, {
      method: 'DELETE',
      headers: {Authorization: `Bearer ${token()}`},
      cache: 'no-store',
    });
    if (response.ok) return;
    const data = await response.json().catch(() => ({}));
    const detail = typeof data?.detail === 'string' ? data.detail : fallbackMessage;
    throw new Error(detail);
  }

  async function removeProject(button, project) {
    const confirmed = window.confirm(
      `Excluir o projeto “${project.name}”?\n\n` +
      'As tarefas e execuções vinculadas a ele também serão removidas. Esta ação não pode ser desfeita.'
    );
    if (!confirmed) return;

    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = 'Excluindo…';

    try {
      await deleteRequest(
        `/api/projects/${encodeURIComponent(project.id)}`,
        'Falha ao excluir o projeto'
      );
      if (typeof window.toast === 'function') window.toast(`Projeto “${project.name}” excluído`);
      if (typeof window.loadProjects === 'function') await window.loadProjects();
      if (typeof window.loadDashboard === 'function') await window.loadDashboard();
    } catch (error) {
      if (typeof window.toast === 'function') window.toast(error?.message || 'Falha ao excluir o projeto');
      else window.alert(error?.message || 'Falha ao excluir o projeto');
      button.disabled = false;
      button.textContent = originalText;
    }
  }

  async function removeTask(button, task, row) {
    const confirmed = window.confirm(
      `Excluir a tarefa “${task.title}”?\n\n` +
      'As execuções vinculadas a ela também serão removidas. Esta ação não pode ser desfeita.'
    );
    if (!confirmed) return;

    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = 'Excluindo…';

    try {
      await deleteRequest(
        `/api/tasks/${encodeURIComponent(task.id)}`,
        'Falha ao excluir a tarefa'
      );

      const detailsRow = row.nextElementSibling?.classList?.contains('task-instructions-row')
        ? row.nextElementSibling
        : null;
      detailsRow?.remove();
      row.remove();

      if (typeof window.toast === 'function') window.toast(`Tarefa “${task.title}” excluída`);
      if (typeof window.loadDashboard === 'function') await window.loadDashboard();
      if (typeof window.loadAllTasks === 'function') await window.loadAllTasks(true);
    } catch (error) {
      if (typeof window.toast === 'function') window.toast(error?.message || 'Falha ao excluir a tarefa');
      else window.alert(error?.message || 'Falha ao excluir a tarefa');
      button.disabled = false;
      button.textContent = originalText;
    }
  }

  function decorateProjects() {
    const target = document.getElementById('projects-list');
    if (!target) return;

    target.querySelectorAll('.project-card').forEach(card => {
      if (card.querySelector(`.${PROJECT_BUTTON_CLASS}`)) return;
      const project = projectInfo(card);
      if (!project.id) return;

      const actions = card.querySelector('.list-row > div:last-child');
      if (!actions) return;

      const button = document.createElement('button');
      button.type = 'button';
      button.className = `link ${PROJECT_BUTTON_CLASS}`;
      button.dataset.id = project.id;
      button.textContent = 'Excluir';
      button.setAttribute('aria-label', `Excluir projeto ${project.name}`);
      button.addEventListener('click', () => void removeProject(button, project));
      actions.appendChild(button);
    });
  }

  function decorateTasks() {
    const target = document.getElementById('tasks-table');
    if (!target) return;

    target.querySelectorAll('.task-main-row').forEach(row => {
      if (row.querySelector(`.${TASK_BUTTON_CLASS}`)) return;
      const task = taskInfo(row);
      if (!task.id || !DELETABLE_TASK_STATUSES.has(task.status)) return;

      const actions = row.lastElementChild;
      if (!actions) return;
      if (actions.textContent.trim() === '—') actions.textContent = '';

      const button = document.createElement('button');
      button.type = 'button';
      button.className = `link ${TASK_BUTTON_CLASS}`;
      button.dataset.id = task.id;
      button.textContent = 'Excluir';
      button.setAttribute('aria-label', `Excluir tarefa ${task.title}`);
      button.addEventListener('click', () => void removeTask(button, task, row));
      actions.appendChild(button);
    });
  }

  function wrapRenderer(name, decorate) {
    const original = window[name];
    if (typeof original !== 'function' || original.__devpilotDeleteWrapped) return;
    const wrapped = function (...args) {
      const result = original.apply(this, args);
      decorate();
      return result;
    };
    wrapped.__devpilotDeleteWrapped = true;
    window[name] = wrapped;
  }

  async function start() {
    if (!(await currentUserIsSuperAdmin())) return;
    ensureStyle();
    wrapRenderer('renderProjects', decorateProjects);
    wrapRenderer('renderTasks', decorateTasks);
    decorateProjects();
    decorateTasks();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => void start(), {once: true});
  } else {
    void start();
  }
})();
