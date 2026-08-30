(() => {
  'use strict';

  if (window.__devpilotFeatureLoaderReady) return;
  window.__devpilotFeatureLoaderReady = true;

  const FEATURE_ASSET_REVISION = (() => {
    try {
      const src = document.currentScript?.src || '';
      return new URL(src, location.href).searchParams.get('v') || 'devpilot-runtime';
    } catch (_) {
      return 'devpilot-runtime';
    }
  })();

  const loadedFiles = new Set();
  const featureState = new Map();
  const FEATURE_SCRIPT_TIMEOUT_MS = 12000;
  let navigationEpoch = 0;

  const FEATURE_BUNDLES = Object.freeze({
    /* Shell comum: leve, determinístico e necessário em qualquer viewport. */
    shellCommon: [
      'viewport-adaptive-v15.js',
      'page-navigation-v26.js',
      'dashboard-user-v21.js',
      'executions-v18.js',
      'executions-focus-v19.js',
    ],

    shell: [
      'simplified-nav.js',
    ],

    mobileShell: [
      'mobile-accordion-menu.js',
    ],

    profile: ['profile.js'],
    users: ['users.js'],

    providers: [
      'provider-models.js',
      'provider-ollama.js',
    ],

    projectBuilder: [
      'project-provisioning.js',
      'project-builder.js',
      'project-description-profile.js',
      'mobile-project-card-compact.js',
    ],

    projects: [
      'project-provisioning.js',
      'project-builder.js',
      'project-description-profile.js',
      'mobile-project-card-compact.js',
      'project-delete-ui.js',
      'project-ships.js',
      'product-delivery-ui.js',
    ],

    taskModal: ['task-modal.js'],
    gameWeapons: ['game-weapons.js'],

    /* A tela de Execuções abre imediatamente; só o controle de exclusão é essencial. */
    tasks: [
      'project-delete-ui.js',
    ],

    tasksAnalytics: [
      'task-analytics.js',
    ],

    tasksDetails: [
      'execution-results-v28.js',
      'task-completion-documentation.js',
      'task-failures.js',
      'task-image-upload.js',
    ],

    tasksEnhancements: [
      'consolidated-ui.js',
      'analysis-commercial-proposal.js',
      'analysis-failure-actions.js',
      'analysis-incomplete-commercial.js',
      'approval-slider.js',
      'ui-literal-newline-cleanup.js',
    ],

    reports: [
      'reports.js',
      'repeatai-analysis-scroll.js',
      'repeatai-live-graphs.js',
      'repeatai-dashboard-graphs.js',
      'repeatai-pattern-graphs.js',
    ],

    organizations: ['organization-normalization-ui.js'],

    example: [
      'example-project.js',
      'example-project-mobile-training.js',
      'example-project-graphs-fix.js',
      'tws-example.js',
    ],

    voice: [
      'super-admin-voice.js',
      'voice-project-start.js',
      'voice-local-update.js',
      'voice-microphone-permission.js',
      'voice-playback.js',
      'voice-enhanced-ui.js',
      'voice-chatgpt-layout.js',
      'voice-insecure-lan-guard.js',
      'mobile-voice-capture-final.js',
      'voice-project-autoload.js',
      'mobile-chat-project-picker.js',
      'voice-runtime-stability.js',
      'chat-request-watchdog.js',
    ],

    admin: [
      'super-admin-voice.js',
      'super-admin-task-panel.js',
      'token-usage.js',
      'token-usage-mobile-fix.js',
      'deploy-admin.js',
      'cloud-admin.js',
      'super-admin-local-test.js',
      'investia-admin.js',
      'investia-homologation.js',
      'game-rules-admin.js',
      'linux-terminal.js',
      'linux-beginner-coach.js',
      'career-linkedin.js',
      'mission-control.js',
      'rag-admin-ui.js',
      'rag-jobs-ui.js',
    ],

    audit: [
      'audit-integrity.js',
      'telemetry-capture.js',
      'telemetry-replay-capture.js',
    ],
  });

  const scriptName = src => {
    try { return new URL(src, location.href).pathname.split('/').pop() || ''; }
    catch (_) { return ''; }
  };

  Array.from(document.scripts).forEach(script => {
    const name = scriptName(script.src);
    if (name && script.dataset.devpilotFeatureLoadState !== 'failed') loadedFiles.add(name);
  });

  const nextPaint = () => new Promise(resolve => window.requestAnimationFrame(resolve));

  const shortYield = () => new Promise(resolve => {
    if (typeof window.scheduler?.yield === 'function') {
      Promise.resolve(window.scheduler.yield()).then(resolve).catch(() => window.setTimeout(resolve, 32));
      return;
    }
    window.setTimeout(resolve, 32);
  });

  const idleYield = () => new Promise(resolve => {
    if ('requestIdleCallback' in window) {
      window.requestIdleCallback(() => resolve(), {timeout: 220});
      return;
    }
    window.setTimeout(resolve, 48);
  });

  const detectedMemory = Number(navigator.deviceMemory || 0);
  const detectedCpu = Number(navigator.hardwareConcurrency || 0);
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches === true;
  const lowPowerDevice =
    reducedMotion ||
    (detectedMemory > 0 && detectedMemory <= 4) ||
    (detectedCpu > 0 && detectedCpu <= 2);

  document.documentElement.classList.toggle('devpilot-low-power', lowPowerDevice);
  window.__devpilotFeaturePerf = window.__devpilotFeaturePerf || [];

  function waitForExistingFeatureScript(script, name) {
    const state = script.dataset.devpilotFeatureLoadState;
    if (state === 'loaded' || script.dataset.devpilotFeatureScript !== '1') {
      loadedFiles.add(name);
      return Promise.resolve(true);
    }
    if (state === 'failed') {
      script.remove();
      return Promise.resolve(false);
    }
    return new Promise(resolve => {
      let settled = false;
      const finish = ok => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timeoutId);
        if (ok) {
          script.dataset.devpilotFeatureLoadState = 'loaded';
          loadedFiles.add(name);
        } else {
          script.dataset.devpilotFeatureLoadState = 'failed';
          script.remove();
        }
        resolve(ok);
      };
      const timeoutId = window.setTimeout(() => finish(false), FEATURE_SCRIPT_TIMEOUT_MS);
      script.addEventListener('load', () => finish(true), {once:true});
      script.addEventListener('error', () => finish(false), {once:true});
    });
  }

  function loadScript(name) {
    if (!name || loadedFiles.has(name)) return Promise.resolve(true);
    const existing = Array.from(document.scripts).find(script => scriptName(script.src) === name);
    if (existing) return waitForExistingFeatureScript(existing, name);

    return new Promise(resolve => {
      const script = document.createElement('script');
      let settled = false;
      const finish = ok => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timeoutId);
        if (ok) {
          script.dataset.devpilotFeatureLoadState = 'loaded';
          loadedFiles.add(name);
        } else {
          script.dataset.devpilotFeatureLoadState = 'failed';
          script.remove();
        }
        resolve(ok);
      };
      const timeoutId = window.setTimeout(() => {
        console.error(`[DevPilot] Timeout ao carregar ${name}`);
        finish(false);
      }, FEATURE_SCRIPT_TIMEOUT_MS);
      script.src = `/assets/${encodeURIComponent(name)}?v=${encodeURIComponent(FEATURE_ASSET_REVISION)}`;
      script.async = false;
      script.dataset.devpilotFeatureScript = '1';
      script.dataset.devpilotFeatureLoadState = 'loading';
      script.onload = () => finish(true);
      script.onerror = () => finish(false);
      document.body.appendChild(script);
    });
  }

  async function loadFeature(feature, options = {}) {
    const files = FEATURE_BUNDLES[feature];
    if (!Array.isArray(files)) return false;

    const current = featureState.get(feature);
    if (current?.status === 'loaded') return true;
    if (current?.promise) return current.promise;

    const intentEpoch = Number.isInteger(options.intentEpoch) ? options.intentEpoch : null;
    const promise = (async () => {
      const failures = [];
      let cancelled = false;
      const featureStarted = performance.now();

      for (let index = 0; index < files.length; index += 1) {
        if (intentEpoch !== null && intentEpoch !== navigationEpoch) {
          cancelled = true;
          break;
        }

        const file = files[index];
        const started = performance.now();
        const ok = await loadScript(file);
        if (!ok) failures.push(file);

        window.__devpilotFeaturePerf.push({
          feature, file, durationMs: Math.round(performance.now() - started), ok, at: Date.now(),
        });

        await nextPaint();
        await shortYield();
        if (index > 0 && index % 2 === 0) await idleYield();
      }

      const status = cancelled ? 'partial' : failures.length ? 'partial' : 'loaded';
      featureState.set(feature, {status, failures, cancelled, promise:null});

      document.dispatchEvent(new CustomEvent('devpilot:feature-ready', {
        detail: {feature, failures, cancelled, durationMs:Math.round(performance.now() - featureStarted)},
      }));
      return !cancelled && failures.length === 0;
    })();

    featureState.set(feature, {status:'loading', failures:[], cancelled:false, promise});
    return promise;
  }

  window.__devpilotLoadFeature = loadFeature;
  window.__devpilotFeatureState = featureState;

  function openChat() {
    const modal = document.querySelector('#voice-modal');
    if (modal && !modal.open) modal.showModal?.();
    const featurePromise = loadFeature('voice');
    const projectsPromise = typeof window.loadProjects === 'function'
      ? Promise.resolve(window.loadProjects()).catch(() => [])
      : Promise.resolve([]);

    return Promise.all([featurePromise, projectsPromise]).then(([ready]) => {
      document.dispatchEvent(new CustomEvent('devpilot:chat-opened', {detail:{ready}}));
      window.requestAnimationFrame(() => document.querySelector('#voice-transcript, #voice-chat-input')?.focus?.());
      return ready;
    });
  }

  window.devpilotOpenChat = openChat;
  const navRoot = () => document.querySelector('.sidebar nav');

  function addPlaceholder(feature, label, {superAdmin = false} = {}) {
    const nav = navRoot();
    if (!nav || nav.querySelector(`[data-devpilot-feature-placeholder="${feature}"]`)) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'nav';
    button.dataset.devpilotFeaturePlaceholder = feature;
    if (superAdmin) button.dataset.superAdmin = 'true';
    button.textContent = label;
    nav.appendChild(button);
  }

  function removePlaceholder(feature) {
    document.querySelector(`[data-devpilot-feature-placeholder="${feature}"]`)?.remove();
  }

  function restorePlaceholder(button, original) {
    if (!button?.isConnected) return;
    button.disabled = false;
    button.removeAttribute('aria-busy');
    button.textContent = original || button.dataset.devpilotOriginalLabel || button.textContent.replace(/\s*·\s*carregando…?\s*$/u, '');
    delete button.dataset.devpilotBusy;
    delete button.dataset.devpilotOriginalLabel;
  }

  function restorePendingPlaceholders() {
    document.querySelectorAll('[data-devpilot-feature-placeholder][data-devpilot-busy="1"]')
      .forEach(button => restorePlaceholder(button, button.dataset.devpilotOriginalLabel || ''));
  }

  function featureTarget(feature) {
    if (feature === 'profile') return document.querySelector('.nav[data-profile-view="1"], .nav[data-view="profile"]');
    if (feature === 'users') return Array.from(document.querySelectorAll('.sidebar nav .nav')).find(item => item.textContent?.trim() === 'Usuários');
    return null;
  }

  async function openPlaceholder(button, feature) {
    if (!button || button.dataset.devpilotBusy === '1') return;
    if (feature === 'game') {
      window.location.assign('/game/index.html');
      return;
    }

    const intentEpoch = navigationEpoch;
    const original = button.textContent.replace(/\s*·\s*carregando…?\s*$/u, '');
    button.dataset.devpilotBusy = '1';
    button.dataset.devpilotOriginalLabel = original;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    button.textContent = `${original} · carregando…`;

    try {
      const ok = await loadFeature(feature, {intentEpoch});
      if (intentEpoch !== navigationEpoch) return restorePlaceholder(button, original);
      if (!ok) {
        window.toast?.(`Não foi possível carregar ${original}. Tente novamente.`);
        return restorePlaceholder(button, original);
      }
      const target = featureTarget(feature);
      if (feature === 'admin') {
        removePlaceholder(feature);
        return;
      }
      if (!target) return restorePlaceholder(button, original);
      removePlaceholder(feature);
      target.click();
    } catch (error) {
      console.error(`[DevPilot] Falha ao abrir ${feature}`, error);
      restorePlaceholder(button, original);
    }
  }

  const TRIGGERS = [
    ['[data-project-builder-open]', 'projectBuilder'],
    ['[data-example-project]', 'example'],
    ['[data-open="task-modal"]', 'taskModal'],
    ['#tasks-v9-indicators', 'tasksAnalytics'],
    ['.tasks-v9-details, .task-instructions-load', 'tasksDetails'],

    ['.nav[data-view="organizations"]', 'organizations'],
    ['.nav[data-view="projects"]', 'projects'],
    ['.nav[data-view="tasks"]', 'tasks'],
    ['.nav[data-view="providers"]', 'providers'],
    ['.nav[data-view="reports"]', 'reports'],
    ['.nav[data-view="audit"]', 'audit'],
    ['#voice-hero, #voice-dock, #voice-start, #voice-send', 'voice'],
  ];

  function matchFeatureTrigger(target) {
    if (!(target instanceof Element)) return null;
    for (const [selector, feature] of TRIGGERS) {
      const trigger = target.closest(selector);
      if (trigger) return {trigger, feature};
    }
    return null;
  }

  document.addEventListener('click', event => {
    const placeholder = event.target.closest?.('[data-devpilot-feature-placeholder]');
    if (placeholder) {
      event.preventDefault();
      event.stopImmediatePropagation();
      void openPlaceholder(placeholder, placeholder.dataset.devpilotFeaturePlaceholder);
      return;
    }

    const navTarget = event.target.closest?.('.sidebar nav .nav');
    if (navTarget) {
      navigationEpoch += 1;
      restorePendingPlaceholders();
    }

    const match = matchFeatureTrigger(event.target);
    if (!match) return;
    const {trigger, feature} = match;

    if (feature === 'voice') {
      event.preventDefault();
      event.stopImmediatePropagation();
      trigger.setAttribute('aria-busy', 'true');
      void openChat().then(ready => {
        if (!ready) window.toast?.('O chat abriu, mas alguns recursos não puderam ser carregados.');
      }).catch(error => {
        console.error('[DevPilot] Falha ao preparar o chat', error);
        window.toast?.('Não foi possível preparar todos os recursos do chat.');
      }).finally(() => trigger.removeAttribute('aria-busy'));
      return;
    }

    if (trigger.dataset.devpilotFeatureReplay === '1') {
      delete trigger.dataset.devpilotFeatureReplay;
      return;
    }
    if (featureState.get(feature)?.status === 'loaded') return;

    const intentEpoch = navigationEpoch;
    event.preventDefault();
    event.stopImmediatePropagation();
    trigger.setAttribute('aria-busy', 'true');
    void loadFeature(feature, {intentEpoch}).then(ok => {
      trigger.removeAttribute('aria-busy');
      if (!ok || intentEpoch !== navigationEpoch || !trigger.isConnected) return;
      trigger.dataset.devpilotFeatureReplay = '1';
      trigger.click();
    }).catch(() => trigger.removeAttribute('aria-busy'));
  }, true);

  let placeholdersInitialized = false;
  function initializePlaceholders() {
    if (placeholdersInitialized) return;
    const nav = navRoot();
    if (!nav) return;
    placeholdersInitialized = true;
    addPlaceholder('profile', 'Perfil');
    addPlaceholder('users', 'Usuários');
    addPlaceholder('game', 'Modo Jogo');
    addPlaceholder('admin', 'Super Admin', {superAdmin:true});
  }

  let mobileShellRequested = false;
  function initializeMobileShell() {
    if (mobileShellRequested || !window.matchMedia('(max-width: 900px)').matches) return;
    mobileShellRequested = true;
    void loadFeature('mobileShell').then(ok => { if (!ok) mobileShellRequested = false; });
  }

  function initializeActiveViewFeature() {
    const active = document.querySelector('.sidebar nav .nav.active[data-view]');
    const view = String(active?.dataset?.view || '');
    const featureByView = {
      projects:'projects', tasks:'tasks', providers:'providers', reports:'reports', audit:'audit',
    };
    const feature = featureByView[view];
    if (feature) void loadFeature(feature);
  }

  function initializeAuthenticatedUi() {
    initializePlaceholders();
    void loadFeature('shellCommon');

    if (window.matchMedia('(min-width: 901px)').matches) {
      void loadFeature('shell');
    } else {
      initializeMobileShell();
    }

    initializeActiveViewFeature();
  }

  const authModal = document.querySelector('#auth-modal');
  const authenticatedUiVisible = () => Boolean(localStorage.getItem('devpilot-token')) && (!authModal || authModal.open === false);
  const initializeIfAuthenticated = () => {
    if (authenticatedUiVisible()) initializeAuthenticatedUi();
  };

  if (document.documentElement.classList.contains('devpilot-auth-pending')) {
    document.addEventListener('devpilot:dashboard-revealed', initializeAuthenticatedUi);
    authModal?.addEventListener('close', initializeIfAuthenticated);
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initializeIfAuthenticated, {once:true});
    } else {
      initializeIfAuthenticated();
    }
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAuthenticatedUi, {once:true});
  } else {
    initializeAuthenticatedUi();
  }

  window.matchMedia('(max-width: 900px)').addEventListener?.('change', event => {
    if (event.matches) initializeMobileShell();
    else void loadFeature('shell');
  });
})();
