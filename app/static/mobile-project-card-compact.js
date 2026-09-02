(() => {
  'use strict';

  const STYLE_ID = 'devpilot-mobile-project-card-compact-style';
  const WRAP_FLAG = '__devpilotProjectsMemoryGuard';
  const LOAD_WRAP_FLAG = '__devpilotProjectsLoadGuard';
  const BUILDER_OPEN_FLAG = 'devpilotLowPowerOpening';
  const SHIPS_SCRIPT = 'project-ships.js';
  const mobileViewport = () => window.matchMedia?.('(max-width: 640px)')?.matches === true;
  const desktopShipsViewport = () => window.matchMedia?.('(min-width: 641px)')?.matches === true;
  const lowPower = () => mobileViewport();
  const batchSize = () => lowPower() ? 6 : 15;
  const fetchLimit = () => lowPower() ? 12 : 50;

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

      @media (min-width: 641px) {
        html.devpilot-low-power #projects-view .project-visual-overview {
          display: grid !important;
        }
        html.devpilot-low-power #projects-view .project-ship-svg,
        html.devpilot-low-power #projects-view .project-ship-hangar {
          display: block !important;
        }
        html.devpilot-low-power #projects-view .project-ship-svg {
          filter: drop-shadow(0 13px 12px #0009) !important;
        }
      }

      @media (max-width: 640px) {
        #projects-view .project-visual-overview {
          display: none !important;
        }

        #projects-view #projects-list .project-card {
          contain: layout paint;
          content-visibility: auto;
          contain-intrinsic-size: 180px;
          box-shadow: none !important;
          transition: none !important;
        }

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

  function ensureProjectShips() {
    if (!desktopShipsViewport()) return;
    if (document.documentElement.classList.contains('devpilot-project-ships-ready')) return;

    const existing = Array.from(document.scripts).find(script => {
      try {
        return new URL(script.src || '', location.href).pathname.endsWith(`/${SHIPS_SCRIPT}`);
      } catch (_) {
        return false;
      }
    });
    if (existing) return;

    const revision = String(window.__devpilotAssetRevisions?.[SHIPS_SCRIPT] || Date.now());
    const script = document.createElement('script');
    script.src = `/assets/${SHIPS_SCRIPT}?v=${encodeURIComponent(revision)}`;
    script.async = false;
    script.dataset.devpilotProjectShipsFallback = '1';
    script.onload = () => {
      document.documentElement.dataset.devpilotProjectShipsFallback = 'loaded';
    };
    script.onerror = () => {
      document.documentElement.dataset.devpilotProjectShipsFallback = 'failed';
      console.error('[DevPilot] Falha ao carregar naves dos projetos.');
    };
    document.body.appendChild(script);
  }

  function markLowPowerCards(projects, target) {
    if (!lowPower()) return;
    const cards = Array.from(target.children).filter(node => node.classList?.contains('project-card'));
    cards.forEach((card, index) => {
      const project = projects[index] || {};
      const operational = Boolean(String(project.repository_url || '').trim());
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
      ensureProjectShips();
      return result;
    };

    guarded[WRAP_FLAG] = true;
    guarded.__devpilotProjectsOriginal = original;
    window.renderProjects = guarded;
    try { renderProjects = guarded; } catch (_) {}
  }

  function installLoadGuard() {
    const original = window.loadProjects;
    if (typeof original !== 'function' || original[LOAD_WRAP_FLAG]) return;

    const guardedLoadProjects = async function (...args) {
      if (!lowPower()) return original.apply(this, args);
      if (typeof state === 'undefined') return original.apply(this, args);
      if (state.projectsLoading) return state.projectsLoading;

      const target = document.getElementById('projects-list');
      if (target && !Array.isArray(state.projects)) state.projects = [];
      if (target && !state.projects.length) {
        target.innerHTML = '<div class="empty">Carregando projetos em modo leve…</div>';
      }

      state.projectsLoading = (async () => {
        try {
          if (typeof api !== 'function') throw new Error('API indisponível');
          const controller = new AbortController();
          const timeoutId = window.setTimeout(() => controller.abort(), 12000);
          let projects;
          try {
            projects = await api(`/ui/projects?limit=${fetchLimit()}`, {
              signal:controller.signal,
            });
          } catch (requestError) {
            if (requestError?.name === 'AbortError') {
              throw new Error('A lista de projetos demorou demais para responder.');
            }
            throw requestError;
          } finally {
            window.clearTimeout(timeoutId);
          }
          state.projects = Array.isArray(projects) ? projects : [];
          renderLimit = batchSize();
          projectsSource = state.projects;
          if (typeof window.renderProjects === 'function') window.renderProjects();
          if (typeof fillProjects === 'function') fillProjects();
          return state.projects;
        } catch (error) {
          if (target) {
            target.textContent = '';
            const message = document.createElement('div');
            message.className = 'empty';
            message.setAttribute('role', 'alert');
            message.textContent = error?.message || 'Não foi possível carregar os projetos.';
            const retry = document.createElement('button');
            retry.type = 'button';
            retry.className = 'ghost';
            retry.dataset.projectsRetry = '1';
            retry.textContent = 'Tentar novamente';
            target.append(message, retry);
          }
          window.toast?.(error?.message || 'Não foi possível carregar os projetos.');
          return [];
        } finally {
          state.projectsLoading = null;
        }
      })();

      return state.projectsLoading;
    };

    guardedLoadProjects[LOAD_WRAP_FLAG] = true;
    guardedLoadProjects.__devpilotProjectsOriginal = original;
    window.loadProjects = guardedLoadProjects;
    try { loadProjects = guardedLoadProjects; } catch (_) {}
  }

  function showBuilderView() {
    if (typeof showView === 'function') {
      showView('new-project');
    } else {
      document.querySelectorAll('.view').forEach(view => {
        view.classList.toggle('active', view.id === 'new-project-view');
      });
    }
    const title = document.querySelector('#page-title');
    if (title) title.textContent = 'Novo projeto';
    window.scrollTo({top:0, left:0, behavior:'auto'});
  }

  function showBuilderLoading(message, error = false) {
    const host = document.querySelector('#project-builder-groups');
    if (!host || host.querySelector('.builder-group')) return;
    host.textContent = '';
    const notice = document.createElement('div');
    notice.className = 'empty';
    notice.dataset.projectBuilderLoading = error ? 'error' : 'loading';
    notice.setAttribute('role', error ? 'alert' : 'status');
    notice.textContent = message;
    host.appendChild(notice);
  }

  function syncBuilderOrganizations() {
    if (typeof state === 'undefined' || !Array.isArray(state.organizations)) return;
    const select = document.querySelector('#project-builder-organization');
    if (!select) return;
    const current = String(select.value || '');
    select.replaceChildren(new Option('Sem organização', ''));
    if (typeof isSuperAdmin === 'function' && isSuperAdmin()) {
      state.organizations.forEach(org => {
        select.add(new Option(String(org?.name || ''), String(org?.id || '')));
      });
    }
    const castilho = state.organizations.find(org => String(org?.external_login || '').toLowerCase() === 'a-castilho');
    if (castilho) select.value = String(castilho.id);
    else if (current && Array.from(select.options).some(option => option.value === current)) select.value = current;
  }

  function refreshBuilderOrganizations() {
    const admin = typeof isSuperAdmin === 'function' && isSuperAdmin();
    if (!admin || typeof loadOrganizations !== 'function') return;
    const organizations = typeof state !== 'undefined' && Array.isArray(state.organizations)
      ? state.organizations
      : [];
    if (organizations.length) {
      syncBuilderOrganizations();
      return;
    }
    void Promise.resolve(loadOrganizations())
      .then(syncBuilderOrganizations)
      .catch(error => console.warn('[DevPilot] Organizações não carregadas no Novo projeto', error));
  }

  async function openBuilderLowPower(trigger) {
    if (!trigger || trigger.dataset[BUILDER_OPEN_FLAG] === '1') return;
    trigger.dataset[BUILDER_OPEN_FLAG] = '1';
    trigger.setAttribute('aria-busy', 'true');

    showBuilderView();
    showBuilderLoading('Carregando cadastro de projeto…');

    try {
      if (typeof window.__devpilotLoadFeature !== 'function') {
        throw new Error('Carregador do cadastro indisponível.');
      }
      const ready = await window.__devpilotLoadFeature('projectBuilder');
      const groups = document.querySelector('#project-builder-groups');
      if (!groups?.querySelector('.builder-group')) {
        throw new Error('Não foi possível carregar o cadastro de projeto.');
      }
      if (!ready) window.toast?.('Cadastro aberto; algum recurso auxiliar ficou indisponível.');
      window.setTimeout(refreshBuilderOrganizations, 0);
    } catch (error) {
      console.error('[DevPilot] Falha ao abrir Novo projeto em modo leve', error);
      showBuilderLoading(error?.message || 'Não foi possível carregar o cadastro de projeto.', true);
      window.toast?.(error?.message || 'Não foi possível abrir o cadastro de projeto.');
    } finally {
      trigger.removeAttribute('aria-busy');
      delete trigger.dataset[BUILDER_OPEN_FLAG];
    }
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
  installLoadGuard();
  ensureProjectShips();

  window.matchMedia?.('(min-width: 641px)')?.addEventListener?.('change', event => {
    if (event.matches) ensureProjectShips();
  });

  document.addEventListener('devpilot:feature-ready', event => {
    if (event?.detail?.feature === 'projects') ensureProjectShips();
  });

  document.addEventListener('click', event => {
    if (!lowPower()) return;
    const target = event.target instanceof Element ? event.target : null;
    const trigger = target?.closest('[data-project-builder-open]');
    if (!trigger) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    void openBuilderLowPower(trigger);
  }, true);

  document.addEventListener('click', event => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    if (target.closest('[data-projects-retry]')) {
      event.preventDefault();
      renderLimit = batchSize();
      if (typeof window.loadProjects === 'function') void window.loadProjects();
      return;
    }
    if (!target.closest('[data-projects-load-more]')) return;
    event.preventDefault();
    loadMore();
  });
})();