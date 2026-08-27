(() => {
  'use strict';

  if (window.__devpilotFeatureLoaderReady) return;
  window.__devpilotFeatureLoaderReady = true;

  const loadedFiles = new Set();
  const featureState = new Map();
  const FEATURE_SCRIPT_TIMEOUT_MS = 12000;
  let navigationEpoch = 0;

  const FEATURE_BUNDLES = Object.freeze({
    mobileShell: ['mobile-accordion-menu.js'],
    profile: ['profile.js'],
    users: ['users.js'],
    providers: ['provider-models.js', 'provider-ollama.js'],
    projectBuilder: ['project-provisioning.js', 'project-builder.js', 'project-description-profile.js', 'mobile-project-card-compact.js'],
    reports: ['reports.js'],
    tasks: ['task-analytics.js', 'system-tests.js'],
    example: ['example-project.js', 'example-project-mobile-training.js', 'example-project-graphs-fix.js', 'tws-example.js'],
    voice: ['super-admin-voice.js', 'voice-project-start.js', 'voice-local-update.js', 'voice-microphone-permission.js', 'voice-playback.js', 'voice-enhanced-ui.js', 'voice-chatgpt-layout.js', 'voice-insecure-lan-guard.js'],
    admin: ['token-usage.js', 'token-usage-mobile-fix.js', 'deploy-admin.js', 'cloud-admin.js', 'super-admin-local-test.js', 'investia-admin.js', 'investia-homologation.js', 'game-rules-admin.js', 'linux-terminal.js', 'linux-beginner-coach.js', 'career-linkedin.js', 'mission-control.js'],
    gameAdvanced: ['build-game-subphases.js', 'build-game-repair-mission.js', 'build-game-new-session.js', 'build-game-url-bonus.js', 'build-game-weapons.js'],
    audit: ['audit-integrity.js', 'telemetry-capture.js', 'telemetry-replay-capture.js'],
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
      script.addEventListener('load', () => finish(true), {once: true});
      script.addEventListener('error', () => finish(false), {once: true});
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
      script.src = `/assets/${encodeURIComponent(name)}?v=ondemand-20260826-3`;
      script.async = false;
      script.dataset.devpilotFeatureScript = '1';
      script.dataset.devpilotFeatureLoadState = 'loading';
      script.onload = () => finish(true);
      script.onerror = () => finish(false);
      document.body.appendChild(script);
    });
  }

  async function loadFeature(feature) {
    const files = FEATURE_BUNDLES[feature];
    if (!Array.isArray(files)) return false;
    const current = featureState.get(feature);
    if (current?.status === 'loaded') return true;
    if (current?.promise) return current.promise;

    const promise = (async () => {
      const failures = [];
      for (const file of files) {
        const ok = await loadScript(file);
        if (!ok) failures.push(file);
        await nextPaint();
      }
      featureState.set(feature, {status: failures.length ? 'partial' : 'loaded', failures, promise: null});
      document.dispatchEvent(new CustomEvent('devpilot:feature-ready', {detail: {feature, failures}}));
      return failures.length === 0;
    })();
    featureState.set(feature, {status: 'loading', failures: [], promise});
    return promise;
  }

  window.__devpilotLoadFeature = loadFeature;
  window.__devpilotFeatureState = featureState;
  window.__devpilotLoadGameAdvanced = () => loadFeature('gameAdvanced');

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
    document.querySelectorAll('[data-devpilot-feature-placeholder][data-devpilot-busy="1"]').forEach(button => restorePlaceholder(button, button.dataset.devpilotOriginalLabel || ''));
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
      const ok = await loadFeature(feature);
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
    ['[data-project-builder-open]', 'projectBuilder'], ['[data-example-project]', 'example'],
    ['.nav[data-view="providers"]', 'providers'], ['.nav[data-view="reports"]', 'reports'],
    ['.nav[data-view="tasks"]', 'tasks'], ['#voice-hero, #voice-dock', 'voice'], ['.nav[data-view="audit"]', 'audit'],
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
    if (trigger.dataset.devpilotFeatureReplay === '1') {
      delete trigger.dataset.devpilotFeatureReplay;
      return;
    }
    if (featureState.get(feature)?.status === 'loaded') return;
    const intentEpoch = navigationEpoch;
    event.preventDefault();
    event.stopImmediatePropagation();
    trigger.setAttribute('aria-busy', 'true');
    void loadFeature(feature).then(ok => {
      trigger.removeAttribute('aria-busy');
      if (!ok || intentEpoch !== navigationEpoch || !trigger.isConnected) return;
      trigger.dataset.devpilotFeatureReplay = '1';
      trigger.click();
    }).catch(() => trigger.removeAttribute('aria-busy'));
  }, true);

  let placeholdersInitialized = false;
  function initializePlaceholders() {
    if (placeholdersInitialized) return;
    placeholdersInitialized = true;
    addPlaceholder('profile', 'Perfil');
    addPlaceholder('users', 'Usuários');
    addPlaceholder('game', 'Modo Jogo');
    addPlaceholder('admin', 'Super Admin', {superAdmin: true});
  }

  let mobileShellRequested = false;
  function initializeMobileShell() {
    if (mobileShellRequested || !window.matchMedia('(max-width: 900px)').matches) return;
    mobileShellRequested = true;
    void loadFeature('mobileShell').then(ok => { if (!ok) mobileShellRequested = false; });
  }

  function initializeAuthenticatedUi() {
    initializePlaceholders();
    initializeMobileShell();
  }

  if (document.documentElement.classList.contains('devpilot-auth-pending')) document.addEventListener('devpilot:dashboard-revealed', initializeAuthenticatedUi, {once: true});
  else if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initializeAuthenticatedUi, {once: true});
  else initializeAuthenticatedUi();

  window.matchMedia('(max-width: 900px)').addEventListener?.('change', event => { if (event.matches) initializeMobileShell(); });
})();
