(() => {
  'use strict';

  if (window.__devpilotStandaloneGameReady) return;
  window.__devpilotStandaloneGameReady = true;

  const CORE_TIMEOUT_MS = 7000;
  const REQUIRED_TIMEOUT_MS = 3500;
  const OPTIONAL_TIMEOUT_MS = 3000;
  const ASSET_REVISION = 'release-1.2.0-game-simple-v56-20260902';
  const REQUIRED_ASSET = 'game/action-runtime.js';
  const OPTIONAL_ASSETS = [
    'game/task-payload-guard.js',
    'game/objective-controls.js',
    'game/start-round-mobile.js',
    'game/delivery-gate.js',
    'build-game-url-bonus.js',
    'game/final-delivery-summary.js',
    'game/pipeline-v2-compat.js',
  ];

  const backToDashboard = () => window.location.assign('/');
  const openDashboardView = view => {
    const allowed = new Set(['overview', 'organizations', 'projects', 'tasks', 'providers', 'reports', 'audit']);
    const target = allowed.has(String(view || '')) ? String(view) : 'overview';
    sessionStorage.setItem('devpilot-dashboard-view', target);
    window.location.assign('/');
  };
  const trace = (stage, detail = {}) => window.__devpilotGameTrace?.(stage, detail);
  const gameTarget = () => document.getElementById('build-game-view');
  const yieldToBrowser = () => new Promise(resolve => window.setTimeout(resolve, 45));
  const hasRenderedShell = target => Boolean(
    target && typeof target.querySelector === 'function' && target.querySelector('.build-game-shell')
  );

  document.getElementById('game-exit')?.addEventListener('click', backToDashboard);
  document.getElementById('game-auth-back')?.addEventListener('click', backToDashboard);

  const menu = document.getElementById('game-menu');
  const menuToggle = document.getElementById('game-menu-toggle');
  const setMenuOpen = open => {
    if (!menu || !menuToggle) return;
    menu.hidden = !open;
    menuToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    menuToggle.setAttribute('aria-label', open ? 'Fechar menu do DevPilot' : 'Abrir menu do DevPilot');
  };
  menuToggle?.addEventListener('click', event => {
    event.stopPropagation();
    setMenuOpen(Boolean(menu?.hidden));
  });
  menu?.addEventListener('click', event => {
    const target = event.target.closest?.('[data-game-dashboard-view]');
    if (!target) return;
    openDashboardView(target.dataset.gameDashboardView);
  });
  document.addEventListener('click', event => {
    if (!menu?.hidden && !menu.contains(event.target) && event.target !== menuToggle) setMenuOpen(false);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !menu?.hidden) {
      setMenuOpen(false);
      menuToggle?.focus();
    }
  });

  function showBooting(message = 'Carregando projeto e histórico leve da missão…') {
    const target = gameTarget();
    if (!target || hasRenderedShell(target)) return;
    target.innerHTML = `
      <div class="empty" data-game-boot-state="loading" role="status">
        <strong>Preparando Modo Jogo…</strong>
        <p>${message}</p>
      </div>
    `;
  }

  function showBootError(error) {
    const message = String(error?.message || 'Falha inesperada');
    const target = gameTarget();
    if (!target) return;

    target.innerHTML = `
      <div class="empty" data-game-boot-state="error" role="alert">
        <strong>Não foi possível iniciar o jogo.</strong>
        <p>${message}</p>
        <div class="hero-actions">
          <button class="primary" id="game-error-retry" type="button">Tentar novamente</button>
          <button class="ghost" id="game-error-back" type="button">Voltar ao painel</button>
        </div>
      </div>
    `;

    document.getElementById('game-error-retry')?.addEventListener('click', () => void boot());
    document.getElementById('game-error-back')?.addEventListener('click', backToDashboard);
  }

  function withTimeout(promise, label, timeoutMs = CORE_TIMEOUT_MS) {
    let timer = 0;
    const timeout = new Promise((_, reject) => {
      timer = window.setTimeout(
        () => reject(new Error(`${label} excedeu ${Math.round(timeoutMs / 1000)}s`)),
        timeoutMs,
      );
    });
    return Promise.race([Promise.resolve(promise), timeout])
      .finally(() => window.clearTimeout(timer));
  }

  function loadAsset(name, timeoutMs = OPTIONAL_TIMEOUT_MS) {
    return new Promise(resolve => {
      const script = document.createElement('script');
      let settled = false;
      const finish = ok => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timer);
        if (!ok) script.remove();
        resolve({name, ok});
      };
      const timer = window.setTimeout(() => finish(false), timeoutMs);
      script.src = `/assets/${name}?v=${encodeURIComponent(ASSET_REVISION)}`;
      script.async = false;
      script.dataset.devpilotGameOptional = '1';
      script.onload = () => finish(true);
      script.onerror = () => finish(false);
      document.body.appendChild(script);
    });
  }

  async function loadEnhancements() {
    trace('enhancements:start');
    const results = [];
    for (const name of OPTIONAL_ASSETS) {
      await yieldToBrowser();
      const result = await loadAsset(name);
      results.push(result);
      if (!result.ok) console.warn(`[DevPilot Game] Recurso opcional indisponível: ${name}`);
    }
    window.__devpilotGameEnhancementResults = results;
    document.dispatchEvent(new CustomEvent('devpilot:game:standalone-ready', {detail:{results}}));
    document.dispatchEvent(new CustomEvent('devpilot:game:enhancements-ready', {detail:{results}}));
    trace('enhancements:end', {failed: results.filter(item => !item.ok).map(item => item.name)});
  }

  async function boot() {
    trace('boot:start');
    showBooting();

    const token = String(localStorage.getItem('devpilot-token') || '').trim();
    if (!token) {
      trace('boot:no-token');
      document.getElementById('auth-modal')?.showModal?.();
      return;
    }

    try {
      if (typeof window.api !== 'function' || !window.__devpilotGameApiReady) {
        throw new Error('Runtime de comunicação do Modo Jogo indisponível');
      }
      if (typeof window.loadBuildGame !== 'function') {
        throw new Error('Motor do Modo Jogo indisponível');
      }

      window.__devpilotGameLoadError = null;

      // The action coordinator is a required part of the standalone lifecycle.
      // Install it before the first render so every render emits the event used by
      // the objective and first-round controls.
      trace('action-runtime:start');
      const coordinator = await loadAsset(REQUIRED_ASSET, REQUIRED_TIMEOUT_MS);
      if (!coordinator.ok || !window.__devpilotGameActionRuntimeReady) {
        throw new Error('Coordenador de ações do Modo Jogo indisponível');
      }
      trace('action-runtime:end');

      trace('game-load:start');
      await withTimeout(window.loadBuildGame(), 'Carregamento principal do Modo Jogo');

      if (window.__devpilotGameLoadError) throw window.__devpilotGameLoadError;

      const target = gameTarget();
      if (!hasRenderedShell(target)) {
        throw new Error('A interface principal do jogo não foi renderizada.');
      }

      trace('game-load:end');
      window.__devpilotGameCoreReady = true;
      document.dispatchEvent(new CustomEvent('devpilot:game:core-ready'));
      trace('boot:ready');

      // Optional enhancements never block the usable game UI. Each module yields
      // to the browser between loads.
      void loadEnhancements();
    } catch (error) {
      window.__devpilotGameLoadError = error;
      trace('boot:error', {message: String(error?.message || error || 'erro')});
      console.error('[DevPilot Game Standalone]', error);
      showBootError(error);
    }
  }

  window.queueMicrotask ? window.queueMicrotask(() => void boot()) : window.setTimeout(() => void boot(), 0);
})();
