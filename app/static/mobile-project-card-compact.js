(() => {
  'use strict';

  const STYLE_ID = 'devpilot-mobile-project-card-compact-style';
  const RENDER_WRAP_FLAG = '__devpilotProjectsMemoryGuard';
  const LOAD_WRAP_FLAG = '__devpilotProjectsFastLoader';
  const MAX_PROJECTS = 50;
  const LOAD_TIMEOUT_MS = 7000;

  const mobileViewport = () => window.matchMedia?.('(max-width: 900px)')?.matches === true;
  const lowPower = () => mobileViewport() || document.documentElement.classList.contains('devpilot-low-power');
  const batchSize = () => lowPower() ? 6 : 15;

  if (mobileViewport()) document.documentElement.classList.add('devpilot-low-power');

  let renderLimit = batchSize();
  let projectsSource = null;
  let fetchedLimit = 0;
  let remoteExhausted = false;
  let requestedRenderLimit = 0;

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;

    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #projects-view #projects-list > .project-card {
        content-visibility: auto;
        contain-intrinsic-size: 320px;
      }

      .projects-memory-footer {
        grid-column: 1 / -1;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding: 10px 12px;
        border: 1px solid rgba(127,127,127,.18);
        border-radius: 10px;
        background: rgba(7,17,31,.72);
      }
      .projects-memory-footer small { opacity: .74; }
      .projects-memory-footer button { flex: 0 0 auto; }

      html.devpilot-low-power #projects-view .project-visual-overview,
      html.devpilot-low-power #projects-view .project-ship-svg,
      html.devpilot-low-power #projects-view .project-ship-hangar {
        display: none !important;
        animation: none !important;
        filter: none !important;
      }

      html.devpilot-low-power #projects-view #projects-list .project-card {
        contain: layout paint;
        content-visibility: auto;
        contain-intrinsic-size: 180px;
        min-height: 0;
        box-shadow: none !important;
        transition: none !important;
      }

      @media (max-width: 900px) {
        #projects-view .project-visual-overview,
        #projects-view .project-ship-svg,
        #projects-view .project-ship-hangar {
          display: none !important;
          animation: none !important;
          filter: none !important;
        }

        #projects-view .project-card > p,
        #projects-view .project-card > code,
        #projects-view .project-card .list-row > small {
          display: none !important;
        }

        #projects-view .project-card {
          min-height: 0;
          padding: 18px;
          box-shadow: none !important;
          transition: none !important;
        }

        #projects-view .project-card h3 {
          margin: 8px 0 14px;
        }

        #projects-view .project-card .list-row {
          display: flex;
          justify-content: flex-end;
          padding: 0;
          border-top: 0;
        }

        #projects-view .project-card .list-row > div:last-child {
          display: flex;
          width: 100%;
          justify-content: flex-end;
          gap: 8px;
          flex-wrap: wrap;
        }

        .projects-memory-footer {
          align-items: stretch;
          flex-direction: column;
        }
        .projects-memory-footer button { width: 100%; }
      }
    `;
    document.head.appendChild(style);
  }

  function markLowPowerCards(projects, target) {
    if (!lowPower()) return;
    const cards = Array.from(target.children).filter(node => node.classList?.contains('project-card'));
    cards.forEach((card, index) => {
      const project = projects[index] || {};
      const operational = Boolean(String(project.repository_url || '').trim());
      // project-ships.js respeita este marcador e não cria SVG/hangar.
      card.dataset.shipEnhanced = '1';
      card.dataset.shipPending = operational ? '0' : '1';
      card.dataset.shipEnergy = operational ? '92' : '55';
      card.dataset.shipShield = operational ? '90' : '50';
      card.dataset.shipReadiness = operational ? '90' : '45';
    });
  }

  function canFetchMore(total) {
    return !remoteExhausted && fetchedLimit < MAX_PROJECTS && total >= fetchedLimit;
  }

  function renderFooter(target, total, visible) {
    target.querySelector('.projects-memory-footer')?.remove();
    const localRemaining = Math.max(0, total - visible);
    const remoteRemaining = canFetchMore(total);
    if (!localRemaining && !remoteRemaining && !lowPower()) return;

    const footer = document.createElement('div');
    footer.className = 'projects-memory-footer';
    const mode = lowPower() ? 'Modo leve · ' : '';
    const more = localRemaining || remoteRemaining;
    const visibleLabel = remoteRemaining ? `${visible} de pelo menos ${total}` : `${visible} de ${total}`;
    footer.innerHTML = `
      <small>${mode}exibindo ${visibleLabel} projeto(s)</small>
      ${more ? `<button type="button" class="ghost" data-projects-load-more>Mostrar mais</button>` : ''}
    `;
    target.appendChild(footer);
  }

  function installRenderGuard() {
    const original = window.renderProjects;
    if (typeof original !== 'function' || original[RENDER_WRAP_FLAG]) return;

    const guarded = function (...args) {
      const fullProjects = typeof state !== 'undefined' && Array.isArray(state.projects)
        ? state.projects
        : [];

      if (fullProjects !== projectsSource) {
        projectsSource = fullProjects;
        renderLimit = requestedRenderLimit
          ? Math.min(fullProjects.length || requestedRenderLimit, requestedRenderLimit)
          : batchSize();
        requestedRenderLimit = 0;
      }

      const visibleProjects = fullProjects.slice(0, Math.max(1, renderLimit));
      let result;
      if (typeof state !== 'undefined') state.projects = visibleProjects;
      try {
        result = original.apply(this, args);
      } finally {
        if (typeof state !== 'undefined') state.projects = fullProjects;
      }

      const target = document.getElementById('projects-list');
      if (target) {
        markLowPowerCards(visibleProjects, target);
        renderFooter(target, fullProjects.length, visibleProjects.length);
      }
      return result;
    };

    guarded[RENDER_WRAP_FLAG] = true;
    guarded.__devpilotProjectsOriginal = original;
    window.renderProjects = guarded;
    try { renderProjects = guarded; } catch (_) {}
  }

  async function requestProjectPage(requestedLimit, desiredVisible) {
    if (typeof api !== 'function' || typeof state === 'undefined') return [];
    if (state.projectsLoading) return state.projectsLoading;

    const target = document.getElementById('projects-list');
    if (target && !Array.isArray(state.projects)?.length) {
      target.innerHTML = '<div class="empty">Carregando projetos em modo leve…</div>';
    }

    const safeLimit = Math.max(1, Math.min(MAX_PROJECTS, Number(requestedLimit) || batchSize()));
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), LOAD_TIMEOUT_MS);

    state.projectsLoading = (async () => {
      try {
        const projects = await api(`/ui/projects?limit=${safeLimit}`, {
          signal: controller.signal,
          cache: 'no-store',
        });
        const rows = Array.isArray(projects) ? projects : [];
        fetchedLimit = safeLimit;
        remoteExhausted = rows.length < safeLimit || safeLimit >= MAX_PROJECTS;
        requestedRenderLimit = Math.max(batchSize(), Number(desiredVisible) || batchSize());
        state.projects = rows;
        window.renderProjects?.();
        if (typeof fillProjects === 'function') fillProjects();
        return rows;
      } catch (error) {
        const timedOut = error?.name === 'AbortError';
        const message = timedOut
          ? 'Projetos demoraram mais de 7 segundos. A tela foi liberada; toque em Atualizar para tentar novamente.'
          : (error?.message || 'Não foi possível carregar projetos.');
        if (target) target.innerHTML = `<div class="empty" role="alert">${typeof esc === 'function' ? esc(message) : message}</div>`;
        window.toast?.(message);
        return [];
      } finally {
        window.clearTimeout(timeoutId);
        state.projectsLoading = null;
      }
    })();

    return state.projectsLoading;
  }

  function installFastLoader() {
    const original = window.loadProjects;
    if (typeof original !== 'function' || original[LOAD_WRAP_FLAG]) return;

    const fast = function () {
      if (!lowPower()) return original.apply(this, arguments);
      const existing = typeof state !== 'undefined' && Array.isArray(state.projects) ? state.projects : [];
      const initial = Math.max(batchSize(), Math.min(existing.length || batchSize(), MAX_PROJECTS));
      return requestProjectPage(initial, batchSize());
    };

    fast[LOAD_WRAP_FLAG] = true;
    fast.__devpilotProjectsOriginalLoader = original;
    window.loadProjects = fast;
    try { loadProjects = fast; } catch (_) {}
  }

  async function loadMore() {
    const projects = typeof state !== 'undefined' && Array.isArray(state.projects)
      ? state.projects
      : [];
    const desiredVisible = Math.min(MAX_PROJECTS, renderLimit + batchSize());

    if (desiredVisible <= projects.length) {
      renderLimit = desiredVisible;
      window.renderProjects?.();
      return;
    }

    if (remoteExhausted || fetchedLimit >= MAX_PROJECTS) {
      renderLimit = Math.min(projects.length, desiredVisible);
      window.renderProjects?.();
      return;
    }

    const nextFetchLimit = Math.min(MAX_PROJECTS, Math.max(desiredVisible, fetchedLimit + batchSize()));
    await requestProjectPage(nextFetchLimit, desiredVisible);
  }

  injectStyles();
  installRenderGuard();
  installFastLoader();

  document.addEventListener('click', event => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target?.closest('[data-projects-load-more]')) return;
    event.preventDefault();
    void loadMore();
  });
})();
