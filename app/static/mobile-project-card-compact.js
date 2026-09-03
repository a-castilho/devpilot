(() => {
  'use strict';

  const STYLE_ID = 'devpilot-mobile-project-card-compact-style';
  const WRAP_FLAG = '__devpilotProjectsMemoryGuard';
  const LOAD_WRAP_FLAG = '__devpilotProjectsLoadGuard';
  const GAME_PROJECT_KEY = 'devpilot-build-game-project';
  const GAME_MISSION_KEY = 'devpilot-build-game-mission';
  const GAME_URL = '/game/index.html';

  const mobileViewport = () => window.matchMedia?.('(max-width: 900px)')?.matches === true;
  const lowPower = () => document.documentElement.classList.contains('devpilot-low-power') || mobileViewport();
  const batchSize = () => lowPower() ? 6 : 15;
  const fetchLimit = () => lowPower() ? 12 : 50;

  let renderLimit = batchSize();
  let projectsSource = null;

  const hashText = value => {
    let hash = 2166136261;
    for (const char of String(value || 'projeto')) {
      hash ^= char.charCodeAt(0);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  };

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

      .project-lite-ship-hangar {
        --lite-accent:#35e58a;
        position:relative;
        min-height:138px;
        margin:10px 0 12px;
        overflow:hidden;
        border:1px solid color-mix(in srgb,var(--lite-accent) 40%,#17344a);
        border-radius:16px;
        background:
          radial-gradient(circle at 50% 78%,color-mix(in srgb,var(--lite-accent) 18%,transparent),transparent 42%),
          linear-gradient(180deg,#06111b,#081925 58%,#07120f);
        contain:layout paint;
      }
      .project-lite-ship-hangar::before {
        content:'NAVE';
        position:absolute;
        top:8px;
        left:10px;
        z-index:2;
        color:var(--lite-accent);
        font-size:8px;
        font-weight:900;
        letter-spacing:.14em;
      }
      .project-lite-ship-svg {
        display:block;
        width:100%;
        height:104px;
        margin-top:18px;
      }
      .project-lite-ship-status {
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
        letter-spacing:.08em;
      }
      .project-lite-ship-status strong { color:var(--lite-accent); }

      #projects-list [data-project-game] {
        border-color:rgba(155,108,255,.42);
      }

      html.devpilot-low-power #projects-view .project-visual-overview {
        display:none !important;
      }
      html.devpilot-low-power #projects-view #projects-list .project-card {
        contain:layout paint;
        content-visibility:auto;
        contain-intrinsic-size:260px;
        min-height:0;
        box-shadow:none !important;
        transition:none !important;
      }

      @media (max-width:900px) {
        #projects-view .project-visual-overview { display:none !important; }

        #projects-view #projects-list .project-card {
          contain:layout paint;
          content-visibility:auto;
          contain-intrinsic-size:260px;
          box-shadow:none !important;
          transition:none !important;
        }

        #projects-view .project-card > p,
        #projects-view .project-card > code,
        #projects-view .project-card .list-row > small {
          display:none !important;
        }

        #projects-view .project-card {
          min-height:0;
          padding:18px;
        }

        #projects-view .project-card h3 { margin:8px 0 10px; }

        #projects-view .project-card .list-row {
          display:flex;
          justify-content:flex-end;
          padding:0;
          border-top:0;
        }

        #projects-view .project-card .list-row > div:last-child {
          display:flex;
          width:100%;
          justify-content:flex-start;
          gap:8px;
          flex-wrap:wrap;
        }

        #projects-view .project-card .list-row button {
          min-height:42px;
          flex:1 1 120px;
        }

        .projects-memory-footer {
          align-items:stretch;
          flex-direction:column;
        }
        .projects-memory-footer button { width:100%; }
      }
    `;
    document.head.appendChild(style);
  }

  function liteShipMarkup(project, index) {
    const key = `${project?.name || ''}|${project?.repository_url || ''}|${index}`;
    const hash = hashText(key);
    const accents = ['#35e58a','#31a8ff','#9b6cff','#29dfe4','#ffba43','#ff6d8d'];
    const accent = accents[hash % accents.length];
    const operational = Boolean(String(project?.repository_url || '').trim());
    const energy = 82 + (hash % 17);
    const shield = 74 + ((hash >>> 4) % 24);
    return `
      <div class="project-lite-ship-hangar" style="--lite-accent:${accent}" aria-label="Nave do projeto ${String(project?.name || '')}">
        <svg class="project-lite-ship-svg" viewBox="0 0 360 170" role="img" aria-hidden="true">
          <path d="M180 18 C204 43 218 73 221 116 L204 143 L156 143 L139 116 C142 73 156 43 180 18 Z" fill="#aab7c5" stroke="${accent}" stroke-width="3"/>
          <path d="M154 81 L67 127 L139 119 L166 101 Z" fill="#273442" stroke="${accent}" stroke-opacity=".7"/>
          <path d="M206 81 L293 127 L221 119 L194 101 Z" fill="#273442" stroke="${accent}" stroke-opacity=".7"/>
          <path d="M180 47 C193 59 199 72 200 85 L190 96 L170 96 L160 85 C161 72 167 59 180 47 Z" fill="#07131d" stroke="${accent}" stroke-width="3"/>
          <rect x="151" y="137" width="23" height="7" rx="3" fill="${accent}"/>
          <rect x="186" y="137" width="23" height="7" rx="3" fill="${accent}"/>
        </svg>
        <div class="project-lite-ship-status"><span>ENERGIA ${energy}% · ESCUDO ${shield}%</span><strong>${operational ? 'OPERACIONAL' : 'PENDENTE'}</strong></div>
      </div>`;
  }

  function ensureGameButton(card, project) {
    if (!card || !project?.id || card.querySelector('[data-project-game]')) return;
    const actions = card.querySelector('.list-row > div:last-child') || card.querySelector('.list-row') || card;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'link project-game-action';
    button.dataset.projectGame = String(project.id);
    button.textContent = 'Jogar';
    button.setAttribute('aria-label', `Jogar com o projeto ${project.name || ''}`);
    actions.appendChild(button);
  }

  function ensureLiteShip(card, project, index) {
    if (!lowPower() || !card || card.querySelector('.project-lite-ship-hangar')) return;
    const host = card.querySelector('h3 + p') || card.querySelector('h3');
    if (!host) return;
    host.insertAdjacentHTML('afterend', liteShipMarkup(project, index));
    card.dataset.shipLiteEnhanced = '1';
  }

  function decorateProjectCards(projects, target) {
    const cards = Array.from(target.children).filter(node => node.classList?.contains('project-card'));
    cards.forEach((card, index) => {
      const project = projects[index];
      if (!project) return;
      ensureGameButton(card, project);
      ensureLiteShip(card, project, index);
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
        decorateProjectCards(visibleProjects, target);
        renderFooter(target, fullProjects.length, visibleProjects.length);
      }
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
            projects = await api(`/ui/projects?limit=${fetchLimit()}`, {signal:controller.signal});
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

  function openGame(projectId) {
    const id = String(projectId || '').trim();
    if (!id) return;
    const previous = String(localStorage.getItem(GAME_PROJECT_KEY) || '');
    if (previous && previous !== id) localStorage.removeItem(GAME_MISSION_KEY);
    localStorage.setItem(GAME_PROJECT_KEY, id);
    window.location.assign(GAME_URL);
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

  document.addEventListener('click', event => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;

    const game = target.closest('[data-project-game]');
    if (game) {
      event.preventDefault();
      openGame(game.dataset.projectGame);
      return;
    }

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

  console.info('[DevPilot] Mobile Projects Runtime V33 ativo');
})();
