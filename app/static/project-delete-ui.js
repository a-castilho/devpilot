(() => {
  'use strict';

  const STYLE_ID = 'devpilot-project-delete-style';
  const BUTTON_CLASS = 'delete-project';

  function token() {
    return String(localStorage.getItem('devpilot-token') || '').trim();
  }

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .delete-project {
        border: 1px solid rgba(239, 68, 68, .55) !important;
        color: #f87171 !important;
        background: rgba(127, 29, 29, .12) !important;
        margin-left: .35rem;
      }
      .delete-project:hover,
      .delete-project:focus-visible {
        border-color: #ef4444 !important;
        background: rgba(127, 29, 29, .28) !important;
        color: #fecaca !important;
      }
      .delete-project[disabled] {
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
      const response = await fetch(`/api/projects/${encodeURIComponent(project.id)}`, {
        method: 'DELETE',
        headers: {Authorization: `Bearer ${token()}`},
        cache: 'no-store',
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        const detail = typeof data?.detail === 'string' ? data.detail : 'Falha ao excluir o projeto';
        throw new Error(detail);
      }

      if (typeof window.toast === 'function') window.toast(`Projeto “${project.name}” excluído`);
      else console.info(`Projeto “${project.name}” excluído`);

      if (typeof window.loadProjects === 'function') await window.loadProjects();
      if (typeof window.loadDashboard === 'function') await window.loadDashboard();
    } catch (error) {
      if (typeof window.toast === 'function') window.toast(error?.message || 'Falha ao excluir o projeto');
      else window.alert(error?.message || 'Falha ao excluir o projeto');
      button.disabled = false;
      button.textContent = originalText;
    }
  }

  function decorateProjects() {
    const target = document.getElementById('projects-list');
    if (!target) return;

    target.querySelectorAll('.project-card').forEach(card => {
      if (card.querySelector(`.${BUTTON_CLASS}`)) return;
      const project = projectInfo(card);
      if (!project.id) return;

      const actions = card.querySelector('.list-row > div:last-child');
      if (!actions) return;

      const button = document.createElement('button');
      button.type = 'button';
      button.className = `link ${BUTTON_CLASS}`;
      button.dataset.id = project.id;
      button.textContent = 'Excluir';
      button.setAttribute('aria-label', `Excluir projeto ${project.name}`);
      button.addEventListener('click', () => void removeProject(button, project));
      actions.appendChild(button);
    });
  }

  async function start() {
    if (!(await currentUserIsSuperAdmin())) return;
    ensureStyle();
    decorateProjects();

    const target = document.getElementById('projects-list');
    if (!target) return;
    const observer = new MutationObserver(decorateProjects);
    observer.observe(target, {childList: true, subtree: true});
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => void start(), {once: true});
  } else {
    void start();
  }
})();
