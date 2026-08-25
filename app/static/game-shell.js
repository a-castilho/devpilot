/* DevPilot Game Shell: isolated, touch-first presentation layer for Build Game. */
(() => {
  'use strict';

  if (window.__devpilotGameShellReady) return;
  window.__devpilotGameShellReady = true;

  const STYLE_ID = 'devpilot-game-shell-style';
  const ROOT_ID = 'devpilot-game-shell';
  const VIEW_ID = 'build-game-view';
  const METRICS = window.__devpilotGameRuntime = window.__devpilotGameRuntime || {
    enters: 0,
    exits: 0,
    refreshes: 0,
    classTransitions: 0,
    baseLoads: 0,
    dedupedLoads: 0,
  };

  let originalParent = null;
  let originalNextSibling = null;
  let viewObserver = null;
  let activeView = null;
  let loadBuildGameWrapped = false;
  let feedbackWired = false;
  let baseLoadBuildGame = null;
  let loadInFlight = null;
  let loaderGuardTimer = null;

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const link = document.createElement('link');
    link.id = STYLE_ID;
    link.rel = 'stylesheet';
    link.href = '/assets/game-shell.css?v=20260825-3';
    document.head.appendChild(link);
  }

  function ensureResponseManager() {
    if (window.DevPilotResponses || document.querySelector('script[data-game-response-manager="1"]')) return;
    const script = document.createElement('script');
    script.src = '/assets/response-manager.js?v=20260825-2';
    script.async = false;
    script.dataset.gameResponseManager = '1';
    document.head.appendChild(script);
  }

  const listeners = new Map();
  const events = window.DevPilotGameEvents = window.DevPilotGameEvents || {
    emit(type, detail = {}) {
      document.dispatchEvent(new CustomEvent(`devpilot:game:${type}`, {detail}));
      const callbacks = listeners.get(type) || [];
      callbacks.forEach(callback => {
        try { callback(detail); } catch (error) { console.error('[DevPilotGameEvents]', error); }
      });
    },
    on(type, callback) {
      const callbacks = listeners.get(type) || [];
      callbacks.push(callback);
      listeners.set(type, callbacks);
      return () => listeners.set(type, callbacks.filter(item => item !== callback));
    },
  };

  function ensureRoot() {
    let root = document.getElementById(ROOT_ID);
    if (root) return root;
    root = document.createElement('section');
    root.id = ROOT_ID;
    root.className = 'devpilot-game-shell';
    root.hidden = true;
    root.setAttribute('aria-label', 'Modo Jogo do DevPilot');
    root.innerHTML = `
      <header class="devpilot-game-hud">
        <button class="devpilot-game-exit" type="button" aria-label="Sair do modo jogo">‹</button>
        <div class="devpilot-game-hud-copy">
          <span>MISSÃO ATIVA</span>
          <strong data-game-hud-phase>Preparando partida</strong>
        </div>
        <div class="devpilot-game-hud-stats" aria-label="Estado da partida">
          <span><small>Projeto</small><b data-game-hud-project>—</b></span>
          <span><small>XP</small><b data-game-hud-xp>0 XP</b></span>
          <span><small>Progresso</small><b data-game-hud-progress>0/6</b></span>
        </div>
      </header>
      <main class="devpilot-game-stage" data-game-slot></main>
    `;
    root.querySelector('.devpilot-game-exit')?.addEventListener('click', () => {
      const overview = document.querySelector('.sidebar .nav[data-view="overview"]');
      if (overview) overview.click();
      else exitGame();
    });
    document.body.appendChild(root);
    return root;
  }

  function snapshot(view) {
    const cards = view?.querySelectorAll?.('.build-game-score > div strong') || [];
    const project = cards[2]?.textContent?.trim() || '—';
    const xp = cards[1]?.textContent?.trim() || '0 XP';
    const progress = cards[0]?.textContent?.trim() || '0/6 fases';
    const phase = view?.querySelector?.('.build-game-phase.current .build-game-phase-copy strong')?.textContent?.trim()
      || (view?.querySelector?.('.build-game-victory') ? 'Missão concluída' : 'Aguardando próxima fase');
    return {project, xp, progress, phase};
  }

  function refresh(view = activeView || document.getElementById(VIEW_ID)) {
    if (!view || !document.body.classList.contains('devpilot-game-mode')) return false;
    const root = ensureRoot();
    const state = snapshot(view);
    root.querySelector('[data-game-hud-project]').textContent = state.project;
    root.querySelector('[data-game-hud-xp]').textContent = state.xp;
    root.querySelector('[data-game-hud-progress]').textContent = state.progress.replace(' fases', '');
    root.querySelector('[data-game-hud-phase]').textContent = state.phase;
    METRICS.refreshes += 1;
    events.emit('state', state);
    return true;
  }

  function enterGame(view = document.getElementById(VIEW_ID)) {
    if (!view) return false;
    const root = ensureRoot();
    const slot = root.querySelector('[data-game-slot]');
    if (!slot) return false;

    const alreadyActive = activeView === view
      && document.body.classList.contains('devpilot-game-mode')
      && root.hidden === false
      && view.parentNode === slot;

    if (!originalParent) {
      originalParent = view.parentNode;
      originalNextSibling = view.nextSibling;
    }
    if (view.parentNode !== slot) slot.appendChild(view);
    root.hidden = false;
    document.body.classList.add('devpilot-game-mode');
    view.classList.add('devpilot-game-view-mounted');
    activeView = view;
    refresh(view);

    if (!alreadyActive) {
      METRICS.enters += 1;
      events.emit('entered', {mission_id: localStorage.getItem('devpilot-build-game-mission') || null});
    }
    return true;
  }

  function restoreView(view) {
    if (!view || !originalParent || view.parentNode === originalParent) return;
    if (originalNextSibling?.parentNode === originalParent) originalParent.insertBefore(view, originalNextSibling);
    else originalParent.appendChild(view);
  }

  function exitGame() {
    const root = document.getElementById(ROOT_ID);
    const view = activeView || document.getElementById(VIEW_ID);
    const wasActive = document.body.classList.contains('devpilot-game-mode');
    restoreView(view);
    if (root) root.hidden = true;
    document.body.classList.remove('devpilot-game-mode');
    view?.classList.remove('devpilot-game-view-mounted');
    activeView = null;
    if (wasActive) {
      METRICS.exits += 1;
      events.emit('exited');
    }
    return true;
  }

  function sync() {
    const view = document.getElementById(VIEW_ID);
    if (!view) return false;
    if (view.classList.contains('active')) return enterGame(view);
    if (document.body.classList.contains('devpilot-game-mode')) return exitGame();
    return true;
  }

  function watchView(view) {
    if (!view || viewObserver) return;
    viewObserver = new MutationObserver(records => {
      if (!records.some(record => record.type === 'attributes' && record.attributeName === 'class')) return;
      METRICS.classTransitions += 1;
      if (view.classList.contains('active')) enterGame(view);
      else if (document.body.classList.contains('devpilot-game-mode')) exitGame();
    });
    // Renderizações internas do jogo não podem reentrar no shell.
    viewObserver.observe(view, {attributes: true, attributeFilter: ['class']});
  }

  function captureBaseLoader() {
    if (baseLoadBuildGame || typeof window.loadBuildGame !== 'function') return false;
    baseLoadBuildGame = window.loadBuildGame;
    window.__devpilotBaseLoadBuildGame = baseLoadBuildGame;
    return true;
  }

  async function runBaseLoad(...args) {
    captureBaseLoader();
    const loader = baseLoadBuildGame || window.loadBuildGame;
    if (typeof loader !== 'function') throw new Error('Motor base do jogo não ficou disponível.');
    if (loadInFlight) {
      METRICS.dedupedLoads += 1;
      return loadInFlight;
    }
    METRICS.baseLoads += 1;
    loadInFlight = Promise.resolve().then(() => loader(...args)).finally(() => {
      loadInFlight = null;
    });
    return loadInFlight;
  }

  function wrapGameLoader() {
    if (loadBuildGameWrapped || typeof window.loadBuildGame !== 'function') return false;
    captureBaseLoader();
    const original = window.loadBuildGame;
    if (original.__devpilotGameStableWrapper) {
      loadBuildGameWrapped = true;
      return true;
    }
    const wrapped = async (...args) => {
      if (loadInFlight) {
        METRICS.dedupedLoads += 1;
        return loadInFlight;
      }
      loadInFlight = Promise.resolve().then(() => original(...args)).then(result => {
        refresh();
        return result;
      }).finally(() => {
        loadInFlight = null;
      });
      return loadInFlight;
    };
    wrapped.__devpilotGameStableWrapper = true;
    wrapped.__devpilotBaseLoader = baseLoadBuildGame;
    window.loadBuildGame = wrapped;
    loadBuildGameWrapped = true;
    return true;
  }

  function guardLoaderDuringBundleBoot() {
    if (captureBaseLoader()) wrapGameLoader();
    if (loadBuildGameWrapped && loaderGuardTimer) {
      window.clearInterval(loaderGuardTimer);
      loaderGuardTimer = null;
    }
  }

  function startLoaderGuard() {
    if (loaderGuardTimer || loadBuildGameWrapped) return;
    let attempts = 0;
    loaderGuardTimer = window.setInterval(() => {
      attempts += 1;
      guardLoaderDuringBundleBoot();
      if (attempts >= 250 && loaderGuardTimer) {
        window.clearInterval(loaderGuardTimer);
        loaderGuardTimer = null;
      }
    }, 8);
  }

  async function openBaseGameFromNavigation(button) {
    if (!button || button.dataset.devpilotBaseOpening === '1') return;
    button.dataset.devpilotBaseOpening = '1';
    button.setAttribute('aria-busy', 'true');
    try {
      if (typeof showView !== 'function') throw new Error('Navegação principal indisponível.');
      showView('build-game');
      const title = document.querySelector('#page-title');
      if (title) title.textContent = 'Jogo de construção';
      const view = document.getElementById(VIEW_ID);
      if (view) enterGame(view);
      await runBaseLoad();
      refresh(view);
      document.dispatchEvent(new CustomEvent('devpilot:game:base-ready'));
    } catch (error) {
      console.error('[DevPilot Game] Falha ao abrir runtime base:', error);
      window.DevPilotResponses?.error?.(error?.message || 'Falha ao abrir o Modo Jogo.');
    } finally {
      button.removeAttribute('aria-busy');
      delete button.dataset.devpilotBaseOpening;
    }
  }

  function wireGameFeedback() {
    if (feedbackWired) return;
    feedbackWired = true;

    // O primeiro acesso pelo menu usa somente o motor base. Os módulos avançados
    // continuam carregados, mas não entram na cadeia de fetch/render inicial.
    document.addEventListener('click', event => {
      const nav = event.target.closest?.('.sidebar nav .nav[data-view="build-game"], .sidebar nav .nav[data-view="game"]');
      if (nav && typeof window.__devpilotBaseLoadBuildGame === 'function') {
        event.preventDefault();
        event.stopImmediatePropagation();
        void openBaseGameFromNavigation(nav);
        return;
      }

      const phase = event.target.closest?.('#build-game-view [data-play-phase]');
      if (phase) {
        const label = phase.dataset.playPhase || '';
        window.DevPilotResponses?.loading?.(`Iniciando fase ${label} da partida…`, {timeout: 10000});
        events.emit('phase-start-requested', {phase: Number(label) || null});
        return;
      }
      if (event.target.closest?.('#build-game-new')) {
        window.DevPilotResponses?.info?.('Preparando uma nova partida…', {duration: 1800});
        events.emit('new-session-requested');
      }
    }, true);
  }

  window.DevPilotGameShell = Object.freeze({
    enter: enterGame,
    exit: exitGame,
    sync,
    refresh,
    loadBase: runBaseLoad,
    snapshot: () => {
      const view = activeView || document.getElementById(VIEW_ID);
      return view ? snapshot(view) : null;
    },
    metrics: () => ({...METRICS}),
  });

  document.addEventListener('devpilot:feature-ready', event => {
    if (event.detail?.feature !== 'game') return;
    guardLoaderDuringBundleBoot();
    sync();
  });

  document.addEventListener('devpilot:game:rendered', () => refresh());

  function boot() {
    ensureStyle();
    ensureResponseManager();
    ensureRoot();
    wireGameFeedback();
    startLoaderGuard();
    guardLoaderDuringBundleBoot();

    const view = document.getElementById(VIEW_ID);
    if (view) {
      watchView(view);
      sync();
      return;
    }

    const observer = new MutationObserver(() => {
      const current = document.getElementById(VIEW_ID);
      if (!current) return;
      watchView(current);
      sync();
      observer.disconnect();
    });
    observer.observe(document.body, {childList: true});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();
