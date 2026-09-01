(() => {
  'use strict';

  const STYLE_ID = 'devpilot-mobile-project-card-compact-style';
  const WRAP_FLAG = '__devpilotProjectsMemoryGuard';
  const lowPower = () => document.documentElement.classList.contains('devpilot-low-power');
  const batchSize = () => lowPower() ? 6 : 15;

  let renderLimit = batchSize();
  let projectsSource = null;

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

      html.devpilot-low-power #projects-view .project-visual-overview {
        display: none !important;
      }
      html.devpilot-low-power #projects-view #projects-list .project-card {
        contain: layout paint;
        content-visibility: auto;
        contain-intrinsic-size: 180px;
        min-height: 0;
        box-shadow: none !important;
        transition: none !important;
      }
      html.devpilot-low-power #projects-view .project-ship-svg,
      html.devpilot-low-power #projects-view .project-ship-hangar {
        display: none !important;
        animation: none !important;
        filter: none !important;
      }

      @media (max-width: 900px) {
        #projects-view .project-card > p,
        #projects-view .project-card > code,
        #projects-view .project-card .list-row > small {
          display: none !important;
        }

        #projects-view .project-card {
          min-height: 0;
          padding: 18px;
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
      // project-ships.js checks this marker before creating the SVG/hangar.
      // On low-memory devices we preserve the functional card and skip the
      // expensive animated visual tree entirely.
      card.dataset.shipEnhanced = '1';
      card.dataset.shipPending = operational ? '0' : '1';
      card.dataset.shipEnergy = operational ? '92' : '55';
      card.dataset.shipShield = operational ? '90' : '50';
      card.dataset.shipReadiness = operational ? '90' : '45';
    });
  }

  function renderFooter(target, total, visible) {
    target.querySelector('.projects-memory-footer')?.remove();
    const remaining = Math.max(0, total - visible);
    if (!remaining && !lowPower()) return;

    const footer = document.createElement('div');
    footer.className = 'projects-memory-footer';
    const mode = lowPower() ? 'Modo leve · ' : '';
    footer.innerHTML = `
      <small>${mode}exibindo ${visible} de ${total} projeto(s)</small>
      ${remaining ? `<button type="button" class="ghost" data-projects-load-more>Mostrar mais ${Math.min(batchSize(), remaining)}</button>` : ''}
    `;
    target.appendChild(footer);
  }

  function installRenderGuard() {
    const original = window.renderProjects;
    if (typeof original !== 'function' || original[WRAP_FLAG]) return;

    const guarded = function (...args) {
      const fullProjects = typeof state !== 'undefined' && Array.isArray(state.projects)
        ? state.projects
        : [];

      if (fullProjects !== projectsSource) {
        projectsSource = fullProjects;
        renderLimit = batchSize();
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

    guarded[WRAP_FLAG] = true;
    guarded.__devpilotProjectsOriginal = original;
    window.renderProjects = guarded;
  }

  function loadMore() {
    const projects = typeof state !== 'undefined' && Array.isArray(state.projects)
      ? state.projects
      : [];
    if (!projects.length) return;
    renderLimit = Math.min(projects.length, renderLimit + batchSize());
    if (typeof window.renderProjects === 'function') window.renderProjects();
  }

  injectStyles();
  installRenderGuard();

  document.addEventListener('click', event => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target?.closest('[data-projects-load-more]')) return;
    event.preventDefault();
    loadMore();
  });
})();
