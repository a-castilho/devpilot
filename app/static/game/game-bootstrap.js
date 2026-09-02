(() => {
  'use strict';

  if (window.__devpilotStandaloneGameReady) return;
  window.__devpilotStandaloneGameReady = true;

  const CORE_TIMEOUT_MS = 7000;
  const OPTIONAL_TIMEOUT_MS = 3000;
  const ASSET_REVISION = 'release-1.2.0-game-entry-minimal-v65-20260902';

  // Entry must stay tiny. These are the only modules allowed to load
  // automatically immediately after the first usable paint.
  const ENTRY_ASSETS = [
    'game/action-runtime.js',
    'game/task-payload-guard.js',
    'game/objective-controls.js',
  ];

  // Verification is important, but it must never compete with initial paint.
  const BACKGROUND_ASSETS = [
    'game/delivery-gate.js',
  ];

  // Delivery/deploy UI is irrelevant until the mission is actually complete.
  const VICTORY_ASSETS = [
    'build-game-url-bonus.js',
    'game/final-delivery-summary.js',
  ];

  const ALLOWED_ASSETS = new Set([
    ...ENTRY_ASSETS,
    ...BACKGROUND_ASSETS,
    ...VICTORY_ASSETS,
  ]);
  const assetLoads = new Map();
  let victoryAssetsStarted = false;
  let backgroundAssetsStarted = false;

  const backToDashboard = () => window.location.assign('/');
  const openDashboardView = view => {
    const allowed = new Set(['overview', 'organizations', 'projects', 'tasks', 'providers', 'reports', 'audit']);
    const target = allowed.has(String(view || '')) ? String(view) : 'overview';
    sessionStorage.setItem('devpilot-dashboard-view', target);
    window.location.assign('/');
  };
  const trace = (stage, detail = {}) => window.__devpilotGameTrace?.(stage, detail);
  const gameTarget = () => document.getElementById('build-game-view');
  const mobileRuntime = window.matchMedia?.('(max-width: 900px)')?.matches === true;
  const yieldToBrowser = () => new Promise(resolve => window.setTimeout(resolve, mobileRuntime ? 90 : 45));
  const hasRenderedShell = target => Boolean(
    target && typeof target.querySelector === 'function' && target.querySelector('.build-game-shell')
  );
  const hasVictory = () => Boolean(document.querySelector('#build-game-view .build-game-victory'));
  const hasMission = () => Boolean(String(localStorage.getItem('devpilot-build-game-mission') || '').trim());

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

  function showBooting(message = 'Carregando somente o núcleo necessário para iniciar…') {
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
    const assetName = String(name || '');
    if (!ALLOWED_ASSETS.has(assetName)) {
      return Promise.resolve({name: assetName, ok: false, blocked: true});
    }
    if (assetLoads.has(assetName)) return assetLoads.get(assetName);

    const promise = new Promise(resolve => {
      const script = document.createElement('script');
      let settled = false;
      const finish = ok => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timer);
        if (!ok) script.remove();
        resolve({name: assetName, ok});
      };
      const timer = window.setTimeout(() => finish(false), timeoutMs);
      script.src = `/assets/${assetName}?v=${encodeURIComponent(ASSET_REVISION)}`;
      script.async = false;
      script.dataset.devpilotGameOptional = '1';
      script.dataset.devpilotGameAsset = assetName;
      script.dataset.devpilotGameRevision = ASSET_REVISION;
      script.onload = () => finish(true);
      script.onerror = () => finish(false);
      document.body.appendChild(script);
    });

    assetLoads.set(assetName, promise);
    return promise;
  }

  async function loadAssetGroup(names, stage) {
    trace(`${stage}:start`);
    const results = [];
    for (const name of names) {
      await yieldToBrowser();
      const result = await loadAsset(name);
      results.push(result);
      if (!result.ok) console.warn(`[DevPilot Game] Recurso opcional indisponível: ${name}`);
    }
    trace(`${stage}:end`, {failed: results.filter(item => !item.ok).map(item => item.name)});
    return results;
  }

  function scheduleIdle(action, delayMs = 1400) {
    window.setTimeout(() => {
      if (typeof window.requestIdleCallback === 'function') {
        window.requestIdleCallback(() => void action(), {timeout: 2200});
        return;
      }
      void action();
    }, delayMs);
  }

  async function loadEntryEnhancements() {
    const results = await loadAssetGroup(ENTRY_ASSETS, 'entry-enhancements');
    window.__devpilotGameEnhancementResults = results;
    window.__devpilotGameEntryAssets = [...ENTRY_ASSETS];
    document.dispatchEvent(new CustomEvent('devpilot:game:standalone-ready', {detail:{results}}));
    document.dispatchEvent(new CustomEvent('devpilot:game:enhancements-ready', {detail:{results}}));
    return results;
  }

  function scheduleBackgroundGate() {
    if (backgroundAssetsStarted || !hasMission()) return;
    backgroundAssetsStarted = true;
    scheduleIdle(async () => {
      const results = await loadAssetGroup(BACKGROUND_ASSETS, 'background-gate');
      window.__devpilotGameBackgroundResults = results;
    }, mobileRuntime ? 2600 : 1600);
  }

  function scheduleVictoryEnhancements() {
    if (victoryAssetsStarted || !hasVictory()) return;
    victoryAssetsStarted = true;
    scheduleIdle(async () => {
      const results = await loadAssetGroup(VICTORY_ASSETS, 'victory-enhancements');
      window.__devpilotGameVictoryResults = results;
    }, mobileRuntime ? 900 : 450);
  }

  function startEnhancementsAfterPaint() {
    const start = () => window.setTimeout(async () => {
      await loadEntryEnhancements();
      scheduleBackgroundGate();
      scheduleVictoryEnhancements();
    }, 0);
    if (typeof window.requestAnimationFrame === 'function') {
      window.requestAnimationFrame(start);
    } else {
      start();
    }
  }

  document.addEventListener('devpilot:game:rendered', () => {
    scheduleBackgroundGate();
    scheduleVictoryEnhancements();
  });

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
      window.__devpilotGameBootProfile = 'minimal-v65';
      document.dispatchEvent(new CustomEvent('devpilot:game:core-ready'));
      trace('boot:ready');

      startEnhancementsAfterPaint();
    } catch (error) {
      window.__devpilotGameLoadError = error;
      trace('boot:error', {message: String(error?.message || error || 'erro')});
      console.error('[DevPilot Game Standalone]', error);
      showBootError(error);
    }
  }

  window.queueMicrotask ? window.queueMicrotask(() => void boot()) : window.setTimeout(() => void boot(), 0);
})();
