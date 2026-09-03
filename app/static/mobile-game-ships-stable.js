(() => {
  'use strict';

  if (window.__devpilotMobileGameShipsStableV94) return;
  window.__devpilotMobileGameShipsStableV94 = true;

  const GAME_URL = '/game/index.html';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const STYLE_ID = 'devpilot-mobile-game-ships-stable-style';
  let syncFrame = 0;
  let observedProjectsHost = null;
  let projectsObserver = null;

  const isMobile = () => window.matchMedia?.('(max-width: 900px)')?.matches === true;

  const hashText = value => {
    let hash = 2166136261;
    for (const char of String(value || 'projeto')) {
      hash ^= char.charCodeAt(0);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  };

  function installStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      @media (max-width:900px) {
        .project-game-ship-stable {
          --ship-accent:#35e58a;
          position:relative;
          display:block!important;
          min-height:150px;
          margin:12px 0 14px;
          overflow:hidden;
          border:1px solid color-mix(in srgb,var(--ship-accent) 48%,#17344a);
          border-radius:18px;
          background:radial-gradient(circle at 50% 76%,color-mix(in srgb,var(--ship-accent) 20%,transparent),transparent 45%),linear-gradient(180deg,#06111b,#081925 60%,#07120f);
          contain:layout paint;
        }
        .project-game-ship-stable::before {
          content:'NAVE DO PROJETO';
          position:absolute;left:12px;top:9px;z-index:2;
          color:var(--ship-accent);font-size:9px;font-weight:900;letter-spacing:.14em;
        }
        .project-game-ship-stable svg {display:block!important;width:100%;height:116px;margin-top:19px;filter:none!important;animation:none!important}
        .project-game-ship-stable .ship-state {position:absolute;left:12px;right:12px;bottom:8px;display:flex;justify-content:space-between;gap:8px;font-size:9px;font-weight:800;color:#9bb7c5}
        .project-game-ship-stable .ship-state strong {color:var(--ship-accent)}
        #projects-list [data-project-game-stable] {border-color:rgba(155,108,255,.55)!important}
        .mobile-simple-nav {grid-template-columns:repeat(5,minmax(0,1fr))!important}
      }
    `;
    document.head.appendChild(style);
  }

  function stateProjects() {
    try {
      if (typeof state !== 'undefined' && Array.isArray(state.projects)) return state.projects;
    } catch (_) {}
    return [];
  }

  function projectForCard(card, index) {
    const id = String(
      card.querySelector('[data-project-task]')?.dataset.projectTask ||
      card.querySelector('.analyze[data-id]')?.dataset.id ||
      ''
    );
    const projects = stateProjects();
    if (id) {
      const found = projects.find(project => String(project?.id || '') === id);
      if (found) return found;
    }
    return projects[index] || {id, name:card.querySelector('h3')?.textContent?.trim() || `Projeto ${index + 1}`};
  }

  function shipMarkup(project, index) {
    const hash = hashText(`${project?.id || ''}|${project?.name || ''}|${index}`);
    const accents = ['#35e58a','#31a8ff','#9b6cff','#29dfe4','#ffba43','#ff6d8d'];
    const accent = accents[hash % accents.length];
    const energy = 84 + (hash % 15);
    const shield = 76 + ((hash >>> 4) % 22);
    return `
      <div class="project-game-ship-stable" style="--ship-accent:${accent}" aria-label="Nave do projeto ${String(project?.name || '')}">
        <svg viewBox="0 0 360 170" role="img" aria-hidden="true">
          <path d="M180 15 C205 42 220 74 222 117 L204 145 L156 145 L138 117 C140 74 155 42 180 15 Z" fill="#aab7c5" stroke="${accent}" stroke-width="3"/>
          <path d="M154 81 L64 129 L139 120 L166 101 Z" fill="#273442" stroke="${accent}" stroke-width="2"/>
          <path d="M206 81 L296 129 L221 120 L194 101 Z" fill="#273442" stroke="${accent}" stroke-width="2"/>
          <path d="M180 46 C194 59 200 72 201 86 L190 98 L170 98 L159 86 C160 72 166 59 180 46 Z" fill="#07131d" stroke="${accent}" stroke-width="3"/>
          <path d="M160 145 L151 162 L173 151 Z" fill="${accent}" opacity=".9"/>
          <path d="M200 145 L209 162 L187 151 Z" fill="${accent}" opacity=".9"/>
        </svg>
        <div class="ship-state"><span>ENERGIA ${energy}% · ESCUDO ${shield}%</span><strong>OPERACIONAL</strong></div>
      </div>`;
  }

  function openGame(projectId) {
    const id = String(projectId || '').trim();
    if (id) {
      const previous = String(localStorage.getItem(PROJECT_KEY) || '');
      if (previous && previous !== id) localStorage.removeItem(MISSION_KEY);
      localStorage.setItem(PROJECT_KEY, id);
    }
    window.location.assign(GAME_URL);
  }

  function projectsViewActive() {
    return document.getElementById('projects-view')?.classList.contains('active') === true;
  }

  function decorateCards() {
    if (!isMobile() || !projectsViewActive()) return;
    const host = document.getElementById('projects-list');
    if (!host) return;
    const cards = [...host.children].filter(node => node.classList?.contains('project-card'));
    cards.forEach((card, index) => {
      const project = projectForCard(card, index);
      const id = String(project?.id || card.querySelector('[data-project-task]')?.dataset.projectTask || '');

      if (!card.querySelector('.project-game-ship-stable') && !card.querySelector('.project-lite-ship-hangar')) {
        const anchor = card.querySelector('h3 + p') || card.querySelector('h3');
        anchor?.insertAdjacentHTML('afterend', shipMarkup(project, index));
      }

      if (id && !card.querySelector('[data-project-game], [data-project-game-stable]')) {
        const actions = card.querySelector('.list-row > div:last-child') || card.querySelector('.list-row') || card;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'link project-game-action';
        button.dataset.projectGameStable = id;
        button.textContent = '🎮 Jogar';
        actions.appendChild(button);
      }
    });
  }

  function ensureBottomGameButton() {
    if (!isMobile()) return;
    const nav = document.querySelector('.mobile-simple-nav');
    if (!nav || nav.querySelector('[data-simple-game]')) return;
    const menu = nav.querySelector('[data-simple-menu-open]');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'mobile-simple-item';
    button.dataset.simpleGame = '1';
    button.innerHTML = '<span aria-hidden="true">🎮</span><small>Jogo</small>';
    button.addEventListener('click', () => openGame(localStorage.getItem(PROJECT_KEY) || ''));
    nav.insertBefore(button, menu || null);
  }

  function ensureSidebarGameButton() {
    const nav = document.querySelector('.sidebar > nav');
    if (!nav || nav.querySelector('[data-devpilot-game-stable]') || nav.querySelector('[data-devpilot-feature-placeholder="game"]')) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'nav';
    button.dataset.devpilotGameStable = '1';
    button.textContent = '🎮 Modo Jogo';
    button.addEventListener('click', () => openGame(localStorage.getItem(PROJECT_KEY) || ''));
    nav.appendChild(button);
  }

  function observeProjectsOnly() {
    const host = document.getElementById('projects-list');
    if (!host || host === observedProjectsHost) return;
    projectsObserver?.disconnect();
    observedProjectsHost = host;
    projectsObserver = new MutationObserver(() => {
      if (projectsViewActive()) scheduleSync();
    });
    projectsObserver.observe(host, {childList:true, subtree:true});
  }

  function sync() {
    syncFrame = 0;
    installStyle();
    ensureBottomGameButton();
    ensureSidebarGameButton();
    observeProjectsOnly();
    decorateCards();
  }

  function scheduleSync() {
    if (syncFrame) return;
    syncFrame = window.requestAnimationFrame(sync);
  }

  document.addEventListener('click', event => {
    const target = event.target instanceof Element ? event.target : null;
    const button = target?.closest('[data-project-game-stable]');
    if (!button) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    openGame(button.dataset.projectGameStable);
  }, true);

  // Este domínio observa somente a lista de Projetos. Não carrega, observa nem
  // modifica o Project Builder; cadastro e jogo têm ciclos de vida independentes.
  document.addEventListener('devpilot:view-changed', scheduleSync);
  document.addEventListener('devpilot:feature-ready', scheduleSync);
  document.addEventListener('devpilot:page-ready', scheduleSync);
  window.addEventListener('resize', scheduleSync, {passive:true});

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', scheduleSync, {once:true});
  else scheduleSync();
})();
