(() => {
  'use strict';

  if (window.__devpilotFeatureLoaderReady) return;
  window.__devpilotFeatureLoaderReady = true;

  const FEATURE_SCRIPT_TIMEOUT_MS = 12000;
  const MANIFEST_SRC = '/assets/runtime-manifest.js?v=20260830-unified-1';
  const loadedFiles = new Set();
  const featureState = new Map();
  const backgroundJobs = new Map();
  let navigationEpoch = 0;

  const scriptName = src => {
    try { return new URL(src, location.href).pathname.split('/').pop() || ''; }
    catch (_) { return ''; }
  };

  Array.from(document.scripts).forEach(script => {
    const name = scriptName(script.src);
    if (name && script.dataset.devpilotFeatureLoadState !== 'failed') loadedFiles.add(name);
  });

  const nextPaint = () => new Promise(resolve => window.requestAnimationFrame(resolve));
  const shortYield = () => new Promise(resolve => window.setTimeout(resolve, 24));
  const idleYield = () => new Promise(resolve => {
    if ('requestIdleCallback' in window) {
      window.requestIdleCallback(() => resolve(), {timeout: 220});
    } else {
      window.setTimeout(resolve, 48);
    }
  });

  function installLowPowerHint() {
    const memory = Number(navigator.deviceMemory || 0);
    const cpu = Number(navigator.hardwareConcurrency || 0);
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches === true;
    const lowPower = reducedMotion || (memory > 0 && memory <= 4) || (cpu > 0 && cpu <= 2);
    document.documentElement.classList.toggle('devpilot-low-power', lowPower);
  }

  function loadRawScript(src, dataset = {}) {
    return new Promise(resolve => {
      const absolute = new URL(src, location.href).href;
      const existing = Array.from(document.scripts).find(script => script.src === absolute);
      if (existing) {
        if (existing.dataset.devpilotFeatureLoadState === 'failed') existing.remove();
        else {
          if (existing.dataset.devpilotFeatureLoadState === 'loading') {
            let settled = false;
            const finish = ok => {
              if (settled) return;
              settled = true;
              window.clearTimeout(timeoutId);
              resolve(ok);
            };
            const timeoutId = window.setTimeout(() => finish(false), FEATURE_SCRIPT_TIMEOUT_MS);
            existing.addEventListener('load', () => finish(true), {once: true});
            existing.addEventListener('error', () => finish(false), {once: true});
            return;
          }
          resolve(true);
          return;
        }
      }

      const script = document.createElement('script');
      let settled = false;
      const finish = ok => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timeoutId);
        script.dataset.devpilotFeatureLoadState = ok ? 'loaded' : 'failed';
        if (!ok) script.remove();
        resolve(ok);
      };
      const timeoutId = window.setTimeout(() => finish(false), FEATURE_SCRIPT_TIMEOUT_MS);
      script.src = src;
      script.async = false;
      script.dataset.devpilotFeatureLoadState = 'loading';
      Object.entries(dataset).forEach(([key, value]) => { script.dataset[key] = value; });
      script.onload = () => finish(true);
      script.onerror = () => finish(false);
      document.body.appendChild(script);
    });
  }

  async function ensureManifest() {
    if (window.__devpilotRuntimeManifest) return window.__devpilotRuntimeManifest;
    const ok = await loadRawScript(MANIFEST_SRC, {devpilotRuntimeManifest: '1'});
    if (!ok || !window.__devpilotRuntimeManifest) {
      console.error('[DevPilot] Manifesto de runtime indisponível.');
      return null;
    }
    return window.__devpilotRuntimeManifest;
  }

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
      script.src = `/assets/${encodeURIComponent(name)}?v=runtime-unified-20260830-1`;
      script.async = false;
      script.dataset.devpilotFeatureScript = '1';
      script.dataset.devpilotFeatureLoadState = 'loading';
      script.onload = () => finish(true);
      script.onerror = () => finish(false);
      document.body.appendChild(script);
    });
  }

  function policyFor(manifest, feature) {
    return manifest.policies?.[feature] || manifest.policies?.default || {idleEvery: 3};
  }

  async function loadFiles(manifest, feature, files, {intentEpoch = null, cancellable = true} = {}) {
    const failures = [];
    const policy = policyFor(manifest, feature);
    const idleEvery = Math.max(1, Number(policy.idleEvery || 3));

    for (let index = 0; index < files.length; index += 1) {
      if (cancellable && intentEpoch !== null && intentEpoch !== navigationEpoch) {
        return {failures, cancelled: true};
      }
      const file = files[index];
      const started = performance.now();
      const ok = await loadScript(file);
      window.__devpilotFeaturePerf = window.__devpilotFeaturePerf || [];
      window.__devpilotFeaturePerf.push({feature, file, ok, durationMs: Math.round(performance.now() - started), at: Date.now()});
      if (!ok) failures.push(file);
      await nextPaint();
      await shortYield();
      if (index > 0 && index % idleEvery === 0) await idleYield();
    }
    return {failures, cancelled: false};
  }

  function scheduleBackground(manifest, feature, files) {
    if (!files.length) return Promise.resolve(true);
    if (backgroundJobs.has(feature)) return backgroundJobs.get(feature);

    const job = (async () => {
      await idleYield();
      const result = await loadFiles(manifest, feature, files, {cancellable: false});
      const current = featureState.get(feature) || {};
      const failures = [...new Set([...(current.failures || []), ...result.failures])];
      featureState.set(feature, {status: failures.length ? 'partial' : 'loaded', failures, promise: null});
      document.dispatchEvent(new CustomEvent('devpilot:feature-ready', {detail: {feature, failures, background: true}}));
      return failures.length === 0;
    })().finally(() => backgroundJobs.delete(feature));

    backgroundJobs.set(feature, job);
    return job;
  }

  async function loadFeature(feature, options = {}) {
    const manifest = await ensureManifest();
    if (!manifest) return false;
    const bundle = manifest.bundles?.[feature];
    if (!Array.isArray(bundle)) return false;

    const full = options.full !== false;
    const current = featureState.get(feature);
    if (current?.status === 'loaded') return true;
    if (current?.status === 'warming' && !full) return true;
    if (current?.status === 'warming' && full && backgroundJobs.has(feature)) return backgroundJobs.get(feature);
    if (current?.promise) return current.promise;

    const critical = full ? bundle : (manifest.critical?.[feature] || bundle);
    const criticalSet = new Set(critical);
    const remaining = bundle.filter(file => !criticalSet.has(file));
    const intentEpoch = Number.isInteger(options.intentEpoch) ? options.intentEpoch : null;

    const promise = (async () => {
      const result = await loadFiles(manifest, feature, critical, {intentEpoch, cancellable: intentEpoch !== null});
      if (result.cancelled) {
        featureState.set(feature, {status: 'idle', failures: result.failures, promise: null});
        return false;
      }
      if (full && remaining.length) {
        const tail = await loadFiles(manifest, feature, remaining, {intentEpoch, cancellable: intentEpoch !== null});
        const failures = [...result.failures, ...tail.failures];
        featureState.set(feature, {status: failures.length ? 'partial' : 'loaded', failures, promise: null});
        return !tail.cancelled && failures.length === 0;
      }

      const status = remaining.length ? 'warming' : (result.failures.length ? 'partial' : 'loaded');
      featureState.set(feature, {status, failures: result.failures, promise: null});
      if (remaining.length) void scheduleBackground(manifest, feature, remaining);
      document.dispatchEvent(new CustomEvent('devpilot:feature-critical-ready', {detail: {feature, failures: result.failures}}));
      return result.failures.length === 0;
    })();

    featureState.set(feature, {status: 'loading', failures: [], promise});
    return promise;
  }

  window.__devpilotLoadFeature = loadFeature;
  window.__devpilotFeatureState = featureState;

  function openChat() {
    const modal = document.querySelector('#voice-modal');
    if (modal && !modal.open) modal.showModal?.();
    const intentEpoch = navigationEpoch;
    const featurePromise = loadFeature('voice', {full: false, intentEpoch});
    const projectsPromise = typeof window.loadProjects === 'function'
      ? Promise.resolve(window.loadProjects()).catch(() => [])
      : Promise.resolve([]);
    return Promise.all([featurePromise, projectsPromise]).then(([ready]) => {
      document.dispatchEvent(new CustomEvent('devpilot:chat-opened', {detail: {ready}}));
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
    document.querySelectorAll('[data-devpilot-feature-placeholder][data-devpilot-busy="1"]').forEach(button => restorePlaceholder(button, button.dataset.devpilotOriginalLabel || ''));
  }

  function featureTarget(feature) {
    if (feature === 'profile') return document.querySelector('.nav[data-profile-view="1"], .nav[data-view="profile"]');
    if (feature === 'users') return Array.from(document.querySelectorAll('.sidebar nav .nav')).find(item => item.textContent?.trim() === 'Usuários');
    return null;
  }

  async function openPlaceholder(button, feature) {
    if (!button || button.dataset.devpilotBusy === '1') return;
    const manifest = await ensureManifest();
    if (!manifest) return;
    if (feature === 'game') {
      window.location.assign(manifest.routes?.game || '/game/index.html');
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
      const ok = await loadFeature(feature, {full: false, intentEpoch});
      if (intentEpoch !== navigationEpoch) return restorePlaceholder(button, original);
      if (!ok) {
        window.toast?.(`Não foi possível carregar ${original}. Tente novamente.`);
        return restorePlaceholder(button, original);
      }
      if (feature === 'admin') {
        removePlaceholder(feature);
        return;
      }
      const target = featureTarget(feature);
      if (!target) return restorePlaceholder(button, original);
      removePlaceholder(feature);
      target.click();
    } catch (error) {
      console.error(`[DevPilot] Falha ao abrir ${feature}`, error);
      restorePlaceholder(button, original);
    }
  }

  function matchFeatureTrigger(target, manifest) {
    if (!(target instanceof Element)) return null;
    for (const rule of manifest.triggers || []) {
      const trigger = target.closest(rule.selector);
      if (trigger) return {trigger, feature: rule.feature};
    }
    return null;
  }

  document.addEventListener('click', event => {
    void (async () => {
      const placeholder = event.target.closest?.('[data-devpilot-feature-placeholder]');
      if (placeholder) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await openPlaceholder(placeholder, placeholder.dataset.devpilotFeaturePlaceholder);
        return;
      }

      const navTarget = event.target.closest?.('.sidebar nav .nav');
      if (navTarget) {
        navigationEpoch += 1;
        restorePendingPlaceholders();
      }

      const manifest = await ensureManifest();
      if (!manifest) return;
      const match = matchFeatureTrigger(event.target, manifest);
      if (!match) return;
      const {trigger, feature} = match;

      if (feature === 'voice') {
        event.preventDefault();
        event.stopImmediatePropagation();
        trigger.setAttribute('aria-busy', 'true');
        try {
          const ready = await openChat();
          if (!ready) window.toast?.('O chat abriu, mas alguns recursos não puderam ser carregados.');
        } catch (error) {
          console.error('[DevPilot] Falha ao preparar o chat', error);
          window.toast?.('Não foi possível preparar todos os recursos do chat.');
        } finally {
          trigger.removeAttribute('aria-busy');
        }
        return;
      }

      if (trigger.dataset.devpilotFeatureReplay === '1') {
        delete trigger.dataset.devpilotFeatureReplay;
        return;
      }
      const status = featureState.get(feature)?.status;
      if (status === 'loaded' || status === 'warming') return;

      const intentEpoch = navigationEpoch;
      event.preventDefault();
      event.stopImmediatePropagation();
      trigger.setAttribute('aria-busy', 'true');
      try {
        const ok = await loadFeature(feature, {full: false, intentEpoch});
        trigger.removeAttribute('aria-busy');
        if (!ok || intentEpoch !== navigationEpoch || !trigger.isConnected) return;
        trigger.dataset.devpilotFeatureReplay = '1';
        trigger.click();
      } catch (_) {
        trigger.removeAttribute('aria-busy');
      }
    })();
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
    addPlaceholder('admin', 'Super Admin', {superAdmin: true});
  }

  let mobileShellRequested = false;
  function initializeMobileShell() {
    if (mobileShellRequested || !window.matchMedia('(max-width: 900px)').matches) return;
    mobileShellRequested = true;
    void loadFeature('mobileShell', {full: true}).then(ok => { if (!ok) mobileShellRequested = false; });
  }

  let desktopShellRequested = false;
  function initializeDesktopShell() {
    if (desktopShellRequested || !window.matchMedia('(min-width: 901px)').matches) return;
    desktopShellRequested = true;
    void loadFeature('shell', {full: true}).then(ok => { if (!ok) desktopShellRequested = false; });
  }

  function initializeAuthenticatedUi() {
    installLowPowerHint();
    initializePlaceholders();
    initializeMobileShell();
    initializeDesktopShell();
  }

  const authModal = document.querySelector('#auth-modal');
  const authenticatedUiVisible = () => Boolean(localStorage.getItem('devpilot-token')) && (!authModal || authModal.open === false);
  const initializeIfAuthenticated = () => {
    if (authenticatedUiVisible()) initializeAuthenticatedUi();
  };

  if (document.documentElement.classList.contains('devpilot-auth-pending')) {
    document.addEventListener('devpilot:dashboard-revealed', initializeAuthenticatedUi);
    authModal?.addEventListener('close', initializeIfAuthenticated);
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initializeIfAuthenticated, {once: true});
    else initializeIfAuthenticated();
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAuthenticatedUi, {once: true});
  } else {
    initializeAuthenticatedUi();
  }

  window.matchMedia('(max-width: 900px)').addEventListener?.('change', event => {
    if (event.matches) initializeMobileShell();
    else initializeDesktopShell();
  });
})();
