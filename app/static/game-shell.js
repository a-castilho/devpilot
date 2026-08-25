/* DevPilot Game Shell: isolated, touch-first presentation layer for Build Game. */
(() => {
  'use strict';

  if (window.__devpilotGameShellReady) return;
  window.__devpilotGameShellReady = true;

  const STYLE_ID = 'devpilot-game-shell-style';
  const ROOT_ID = 'devpilot-game-shell';
  const VIEW_ID = 'build-game-view';
  let originalParent = null;
  let originalNextSibling = null;
  let viewObserver = null;

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const link = document.createElement('link');
    link.id = STYLE_ID;
    link.rel = 'stylesheet';
    link.href = '/assets/game-shell.css?v=20260825-1';
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
    const cards = view.querySelectorAll('.build-game-score > div strong');
    const project = cards[2]?.textContent?.trim() || '—';
    const xp = cards[1]?.textContent?.trim() || '0 XP';
    const progress = cards[0]?.textContent?.trim() || '0/6 fases';
    const phase = view.querySelector('.build-game-phase.current .build-game-phase-copy strong')?.textContent?.trim()
      || (view.querySelector('.build-game-victory') ? 'Missão concluída' : 'Aguardando próxima fase');
    return {project, xp, progress, phase};
  }

  function updateHud(view) {
    const root = ensureRoot();
    const state = snapshot(view);
    root.querySelector('[data-game-hud-project]').textContent = state.project;
    root.querySelector('[data-game-hud-xp]').textContent = state.xp;
    root.querySelector('[data-game-hud-progress]').textContent = state.progress.replace(' fases', '');
    root.querySelector('[data-game-hud-phase]').textContent = state.phase;
    events.emit('state', state);
  }

  function enterGame(view = document.getElementById(VIEW_ID)) {
    const root = ensureRoot();
    const slot = root.querySelector('[data-game-slot]');
    if (!slot || !view) return false;

    if (!originalParent) {
      originalParent = view.parentNode;
      originalNextSibling = view.nextSibling;
    }
    if (view.parentNode !== slot) slot.appendChild(view);
    root.hidden = false;
    document.body.classList.add('devpilot-game-mode');
    view.classList.add('devpilot-game-view-mounted');
    updateHud(view);
    events.emit('entered', {mission_id: localStorage.getItem('devpilot-build-game-mission') || null});
    return true;
  }

  function restoreView(view) {
    if (!view || !originalParent || view.parentNode === originalParent) return;
    if (originalNextSibling?.parentNode === originalParent) originalParent.insertBefore(view, originalNextSibling);
    else originalParent.appendChild(view);
  }

  function exitGame() {
    const root = document.getElementById(ROOT_ID);
    const view = document.getElementById(VIEW_ID);
    restoreView(view);
    if (root) root.hidden = true;
    document.body.classList.remove('devpilot-game-mode');
    view?.classList.remove('devpilot-game-view-mounted');
    events.emit('exited');
    return true;
  }

  function sync() {
    const view = document.getElementById(VIEW_ID);
    if (!view) return false;
    if (view.classList.contains('active')) return enterGame(view);
    if (document.body.classList.contains('devpilot-game-mode')) exitGame();
    return true;
  }

  window.DevPilotGameShell = Object.freeze({
    enter: enterGame,
    exit: exitGame,
    sync,
    snapshot: () => {
      const view = document.getElementById(VIEW_ID);
      return view ? snapshot(view) : null;
    },
  });

  function watchView(view) {
    if (!view || viewObserver) return;
    viewObserver = new MutationObserver(() => {
      if (view.classList.contains('active')) {
        enterGame(view);
        updateHud(view);
      } else if (document.body.classList.contains('devpilot-game-mode')) {
        exitGame();
      }
    });
    viewObserver.observe(view, {attributes: true, attributeFilter: ['class'], childList: true, subtree: true});
  }

  function wireGameFeedback() {
    document.addEventListener('click', event => {
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

  function boot() {
    ensureStyle();
    ensureResponseManager();
    ensureRoot();
    wireGameFeedback();
    if (sync()) watchView(document.getElementById(VIEW_ID));
    const observer = new MutationObserver(() => {
      const view = document.getElementById(VIEW_ID);
      if (!view) return;
      watchView(view);
      sync();
      observer.disconnect();
    });
    observer.observe(document.body, {childList: true, subtree: true});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();
