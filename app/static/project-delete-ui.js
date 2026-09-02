(() => {
  'use strict';

  const STYLE_ID = 'devpilot-delete-action-style';
  const PROJECT_BUTTON_CLASS = 'delete-project';
  const TASK_BUTTON_CLASS = 'delete-task';
  const GAME_PROJECT_KEY = 'devpilot-build-game-project';
  const GAME_MISSION_KEY = 'devpilot-build-game-mission';
  const GAME_URL = '/game/index.html';
  const DELETABLE_TASK_STATUSES = new Set([
    'awaiting_approval',
    'completed',
    'failed',
    'blocked',
  ]);

  let projectsObserver = null;
  let isSuperAdminUser = false;

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

      #projects-view .project-lite-ship-hangar {
        --lite-accent:#35e58a;
        position:relative;
        display:block !important;
        min-height:142px;
        margin:12px 0 14px;
        overflow:hidden;
        border:1px solid var(--lite-accent);
        border-radius:16px;
        background:radial-gradient(circle at 50% 72%,rgba(53,229,138,.14),transparent 42%),linear-gradient(180deg,#06111b,#081925 58%,#07120f);
        contain:layout paint;
      }
      #projects-view .project-lite-ship-hangar::before {
        content:'NAVE DO PROJETO';
        position:absolute;
        top:9px;
        left:11px;
        z-index:2;
        color:var(--lite-accent);
        font-size:9px;
        font-weight:900;
        letter-spacing:.13em;
      }
      #projects-view .project-lite-ship-svg {
        display:block !important;
        width:100%;
        height:108px;
        margin-top:19px;
        animation:none !important;
        filter:none !important;
      }
      #projects-view .project-lite-ship-status {
        position:absolute;
        right:10px;
        bottom:8px;
        left:10px;
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:8px;
        color:#9bb7c5;
        font-size:8px;
        font-weight:800;
        letter-spacing:.07em;
      }
      #projects-view .project-lite-ship-status strong { color:var(--lite-accent); }
      #projects-view [data-project-game] {
        border-color:rgba(155,108,255,.58) !important;
        color:#c9b5ff !important;
      }

      @media (max-width:900px) {
        body.mobile-route .sidebar > .mobile-simple-nav.devpilot-game-nav-five {
          grid-template-columns:repeat(5,minmax(0,1fr))!important;
        }
        .mobile-simple-item[data-simple-game] > span { color:#bfa7ff; }
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
    const task = card.querySelector('[data-project-task]');
    const name = card.querySelector('h3')?.textContent?.trim() || 'este projeto';
    const repository = card.querySelector('code')?.textContent?.trim() || '';
    return {
      id: String(analyze?.dataset?.id || task?.dataset?.projectTask || '').trim(),
      name,
      repository,
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

  function hashText(value) {
    let hash = 2166136261;
    for (const char of String(value || 'projeto')) {
      hash ^= char.charCodeAt(0);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function shipMarkup(project) {
    const hash = hashText(`${project.name}|${project.repository}|${project.id}`);
    const accents = ['#35e58a','#31a8ff','#9b6cff','#29dfe4','#ffba43','#ff6d8d'];
    const accent = accents[hash % accents.length];
    const operational = Boolean(project.repository);
    const energy = 82 + (hash % 17);
    const shield = 74 + ((hash >>> 4) % 24);
    return `
      <div class="project-lite-ship-hangar" style="--lite-accent:${accent}" aria-label="Nave do projeto ${project.name}">
        <svg class="project-lite-ship-svg" viewBox="0 0 360 170" role="img" aria-hidden="true">
          <path d="M180 17 C206 43 221 74 222 116 L204 144 L156 144 L138 116 C139 74 154 43 180 17 Z" fill="#aab7c5" stroke="${accent}" stroke-width="3"/>
          <path d="M154 80 L66 128 L139 119 L166 101 Z" fill="#273442" stroke="${accent}" stroke-opacity=".82"/>
          <path d="M206 80 L294 128 L221 119 L194 101 Z" fill="#273442" stroke="${accent}" stroke-opacity=".82"/>
          <path d="M180 45 C194 58 201 72 201 86 L190 98 L170 98 L159 86 C159 72 166 58 180 45 Z" fill="#07131d" stroke="${accent}" stroke-width="3"/>
          <path d="M169 142 L162 161 L176 148 Z" fill="${accent}" opacity=".9"/>
          <path d="M191 142 L198 161 L184 148 Z" fill="${accent}" opacity=".9"/>
          <rect x="149" y="137" width="25" height="8" rx="4" fill="${accent}"/>
          <rect x="186" y="137" width="25" height="8" rx="4" fill="${accent}"/>
        </svg>
        <div class="project-lite-ship-status"><span>ENERGIA ${energy}% · ESCUDO ${shield}%</span><strong>${operational ? 'OPERACIONAL' : 'PENDENTE'}</strong></div>
      </div>`;
  }

  function openGame(projectId = '') {
    const id = String(projectId || '').trim();
    if (id) {
      const previous = String(localStorage.getItem(GAME_PROJECT_KEY) || '');
      if (previous && previous !== id) localStorage.removeItem(GAME_MISSION_KEY);
      localStorage.setItem(GAME_PROJECT_KEY, id);
    }
    window.location.assign(GAME_URL);
  }

  function ensureShipAndGame(card) {
    const project = projectInfo(card);
    if (!project.id) return;

    if (!card.querySelector('.project-lite-ship-hangar')) {
      const anchor = card.querySelector('h3 + p') || card.querySelector('h3');
      anchor?.insertAdjacentHTML('afterend', shipMarkup(project));
      card.dataset.shipLiteEnhanced = '1';
    }

    if (!card.querySelector('[data-project-game]')) {
      const actions = card.querySelector('.list-row > div:last-child') || card.querySelector('.list-row');
      if (actions) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'link project-game-action';
        button.dataset.projectGame = project.id;
        button.textContent = 'Jogar';
        button.setAttribute('aria-label', `Abrir Modo Jogo do projeto ${project.name}`);
        button.addEventListener('click', event => {
          event.preventDefault();
          event.stopPropagation();
          openGame(project.id);
        });
        actions.appendChild(button);
      }
    }
  }

  function ensureGameNavigation() {
    const sourceNav = document.querySelector('.sidebar > nav, .sidebar nav');
    if (sourceNav && !sourceNav.querySelector('[data-devpilot-feature-placeholder="game"], [data-view="build-game"], [data-project-game-nav]')) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'nav';
      button.dataset.projectGameNav = '1';
      button.textContent = 'Modo Jogo';
      button.addEventListener('click', () => openGame());
      sourceNav.appendChild(button);
    }

    const mobile = document.querySelector('.mobile-simple-nav');
    if (!mobile || mobile.querySelector('[data-simple-game]')) return;
    const menuButton = mobile.querySelector('[data-simple-menu-open]');
    if (!menuButton) return;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'mobile-simple-item';
    button.dataset.simpleGame = '1';
    button.setAttribute('aria-label', 'Abrir Modo Jogo');
    button.innerHTML = '<span aria-hidden="true">🎮</span><small>Jogo</small>';
    button.addEventListener('click', () => openGame());
    mobile.insertBefore(button, menuButton);
    mobile.classList.add('devpilot-game-nav-five');
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
      const project = projectInfo(card);
      if (!project.id) return;

      ensureShipAndGame(card);

      if (!isSuperAdminUser || card.querySelector(`.${PROJECT_BUTTON_CLASS}`)) return;
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
    if (!isSuperAdminUser) return;
    const target = document.getElementById('tasks-table');
    if (!target) return;

    target.querySelectorAll('.task-main-row').forEach(row => {
      if (row.querySelector(`.${TASK_BUTTON_CLASS}`)) return;
      const task = taskInfo(row);
      if (!task.id || !DELETABLE_TASK_STATUSES.has(task.status)) return;

      const actionCell = row.lastElementChild;
      const actions = actionCell?.querySelector('[data-task-orchestrator-actions]') || actionCell;
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
    if (typeof original !== 'function' || original.__devpilotDeleteWrapped) return false;
    const wrapped = function (...args) {
      const result = original.apply(this, args);
      decorate();
      return result;
    };
    wrapped.__devpilotDeleteWrapped = true;
    wrapped.__devpilotDeleteOriginal = original;
    window[name] = wrapped;
    try { globalThis[name] = wrapped; } catch (_) {}
    return true;
  }

  function observeProjects() {
    const target = document.getElementById('projects-list');
    if (!target || projectsObserver) return;
    projectsObserver = new MutationObserver(() => decorateProjects());
    projectsObserver.observe(target, {childList:true, subtree:true});
  }

  function stabilizeUi(attempt = 0) {
    ensureGameNavigation();
    decorateProjects();
    decorateTasks();
    observeProjects();
    wrapRenderer('renderProjects', decorateProjects);
    wrapRenderer('renderTasks', decorateTasks);

    if (attempt < 20 && (!document.getElementById('projects-list') || !document.querySelector('.mobile-simple-nav'))) {
      window.setTimeout(() => stabilizeUi(attempt + 1), 100);
    }
  }

  async function start() {
    ensureStyle();
    isSuperAdminUser = await currentUserIsSuperAdmin();
    stabilizeUi();

    document.addEventListener('devpilot:view-changed', () => stabilizeUi());
    document.addEventListener('devpilot:feature-ready', () => stabilizeUi());
    document.addEventListener('devpilot:page-ready', () => stabilizeUi());
    document.addEventListener('devpilot:login-complete', () => stabilizeUi());
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => void start(), {once: true});
  } else {
    void start();
  }
})();
