(() => {
  'use strict';

  if (window.__devpilotStandaloneGameReady) return;
  window.__devpilotStandaloneGameReady = true;

  const CORE_TIMEOUT_MS = 7000;
  const OPTIONAL_TIMEOUT_MS = 3000;
  const ASSET_REVISION = 'release-1.2.0-game-actions-v54-20260902';
  const OPTIONAL_ASSETS = [
    'game/action-runtime.js',
    'game/task-payload-guard.js',
    'game/objective-controls.js',
    'game/start-round-mobile.js',
    'game/delivery-gate.js',
    'build-game-url-bonus.js',
    'game/final-delivery-summary.js',
    'game/pipeline-v2-compat.js',
  ];

  const backToDashboard = () => window.location.assign('/');
  const trace = (stage, detail = {}) => window.__devpilotGameTrace?.(stage, detail);
  const gameTarget = () => document.getElementById('build-game-view');
  const yieldToBrowser = () => new Promise(resolve => window.setTimeout(resolve, 45));
  const hasRenderedShell = target => Boolean(
    target && typeof target.querySelector === 'function' && target.querySelector('.build-game-shell')
  );

  document.getElementById('game-exit')?.addEventListener('click', backToDashboard);
  document.getElementById('game-auth-back')?.addEventListener('click', backToDashboard);

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

  function loadOptionalAsset(name) {
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
      const timer = window.setTimeout(() => finish(false), OPTIONAL_TIMEOUT_MS);
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
      const result = await loadOptionalAsset(name);
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

      // Enhancements never block the usable game UI. The action coordinator is
      // loaded first and every later module yields to the browser between loads.
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
