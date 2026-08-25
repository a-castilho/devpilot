(() => {
  'use strict';

  const loadedFiles = new Set();
  const featureState = new Map();
  const FEATURE_SCRIPT_TIMEOUT_MS = 12000;
  let navigationEpoch = 0;

  const FEATURE_BUNDLES = Object.freeze({
    profile: ['profile.js'],
    users: ['users.js'],
    projectBuilder: [
      'project-provisioning.js',
      'project-builder.js',
      'project-description-profile.js',
      'mobile-project-card-compact.js',
    ],
    reports: ['reports.js'],
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
    ],
    admin: [
      'token-usage.js',
      'token-usage-mobile-fix.js',
      'deploy-admin.js',
      'cloud-admin.js',
      'super-admin-local-test.js',
      'investia-admin.js',
      'investia-homologation.js',
      'linux-terminal.js',
      'linux-beginner-coach.js',
      'career-linkedin.js',
      'mission-control.js',
    ],
    game: [
      'game-workflow-adapter.js',
      'build-game.js',
      'build-game-subphases.js',
      'build-game-new-session.js',
      'build-game-url-bonus.js',
      'build-game-weapons.js',
      'mobile-game-mode.js',
      'game-linux-training.js',
    ],
    audit: ['audit-integrity.js'],
  });

  const scriptName = src => {
    try {
      return new URL(src, location.href).pathname.split('/').pop() || '';
    } catch (_) {
      return '';
    }
  };

  Array.from(document.scripts).forEach(script => {
    const name = scriptName(script.src);
    if (!name) return;
    const dynamic = script.dataset.devpilotFeatureScript === '1';
    const loaded = script.dataset.devpilotFeatureLoadState === 'loaded';
    if (!dynamic || loaded) loadedFiles.add(name);
  });

  const nextPaint = () => new Promise(resolve => {
    window.requestAnimationFrame(() => resolve());
  });

  const shortYield = () => new Promise(resolve => window.setTimeout(resolve, 35));

  function waitForExistingFeatureScript(script, name) {
    const state = script.dataset.devpilotFeatureLoadState;
    if (state === 'loaded') {
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
      const timeoutId = window.setTimeout(() => {
        console.error(`[DevPilot] Timeout ao carregar ${name}`);
        finish(false);
      }, FEATURE_SCRIPT_TIMEOUT_MS);

      script.addEventListener('load', () => finish(true), {once: true});
      script.addEventListener('error', () => finish(false), {once: true});
    });
  }

  function loadScript(name) {
    if (!name || loadedFiles.has(name)) return Promise.resolve(true);

    const existing = Array.from(document.scripts).find(script => scriptName(script.src) === name);
    if (existing) {
      if (existing.dataset.devpilotFeatureScript !== '1') {
        loadedFiles.add(name);
        return Promise.resolve(true);
      }
      if (existing.dataset.devpilotFeatureLoadState === 'failed') existing.remove();
      else return waitForExistingFeatureScript(existing, name);
    }

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

      script.src = `/assets/${encodeURIComponent(name)}?v=ondemand-20260825-8`;
      script.async = false;
      script.dataset.devpilotFeatureScript = '1';
      script.dataset.devpilotFeatureLoadState = 'loading';
      script.onload = () => finish(true);
      script.onerror = () => {
        console.error(`[DevPilot] Falha ao carregar ${name}`);
        finish(false);
      };
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
        await shortYield();
      }
      featureState.set(feature, {
        status: failures.length ? 'partial' : 'loaded',
        failures,
        promise: null,
      });
      document.dispatchEvent(new CustomEvent('devpilot:feature-ready', {
        detail: {feature, failures},
      }));
      return failures.length === 0;
    })();

    featureState.set(feature, {status: 'loading', failures: [], promise});
    return promise;
  }

  window.__devpilotLoadFeature = loadFeature;
  window.__devpilotFeatureState = featureState;

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
    const label = original || button.dataset.devpilotOriginalLabel || button.textContent.replace(/\s*·\s*carregando…?\s*$/u, '');
    button.disabled = false;
    button.textContent = label;
    delete button.dataset.devpilotBusy;
    delete button.dataset.devpilotOriginalLabel;
  }

  function restorePendingPlaceholders() {
    document.querySelectorAll('[data-devpilot-feature-placeholder][data-devpilot-busy="1"]').forEach(button => {
      restorePlaceholder(button, button.dataset.devpilotOriginalLabel || '');
    });
  }

  function findUsersNav() {
    return Array.from(document.querySelectorAll('.sidebar nav .nav'))
      .find(item => item.textContent?.trim() === 'Usuários');
  }

  function featureTarget(feature) {
    if (feature === 'profile') {
      return document.querySelector('.nav[data-profile-view="1"], .nav[data-view="profile"]');
    }
    if (feature === 'users') return findUsersNav();
    if (feature === 'game') {
      return document.querySelector('.nav[data-view="build-game"], .nav[data-view="game"], [data-build-game]');
    }
    return null;
  }

  function finishStalePlaceholderIntent(button, feature, ok, original) {
    if (ok) {
      const target = featureTarget(feature);
      if (target) {
        removePlaceholder(feature);
        return;
      }
      if (feature === 'admin') {
        removePlaceholder(feature);
        return;
      }
    }
    restorePlaceholder(button, original);
  }

  async function openPlaceholder(button, feature) {
    if (!button || button.dataset.devpilotBusy === '1') return;
    const intentEpoch = navigationEpoch;
    const original = button.textContent.replace(/\s*·\s*carregando…?\s*$/u, '');
    button.dataset.devpilotBusy = '1';
    button.dataset.devpilotOriginalLabel = original;
    button.disabled = true;
    button.textContent = `${original} · carregando…`;

    try {
      const ok = await loadFeature(feature);

      if (intentEpoch !== navigationEpoch) {
        finishStalePlaceholderIntent(button, feature, ok, original);
        return;
      }

      if (!ok) {
        const failures = featureState.get(feature)?.failures || [];
        console.error(`[DevPilot] Módulo ${feature} incompleto`, failures);
        window.toast?.(`Não foi possível carregar ${original}. Tente novamente.`);
        restorePlaceholder(button, original);
        return;
      }

      await nextPaint();

      if (intentEpoch !== navigationEpoch) {
        finishStalePlaceholderIntent(button, feature, true, original);
        return;
      }

      if (feature === 'profile' || feature === 'users' || feature === 'game') {
        const target = featureTarget(feature);
        if (!target) {
          const label = feature === 'game' ? 'Modo Jogo' : feature === 'users' ? 'Usuários' : 'Perfil';
          window.toast?.(`${label} foi carregado, mas a navegação não ficou disponível.`);
          restorePlaceholder(button, original);
          return;
        }
        removePlaceholder(feature);
        target.click();
        return;
      }

      if (feature === 'admin') {
        removePlaceholder(feature);
        window.toast?.('Módulos Super Admin carregados.');
        return;
      }

      restorePlaceholder(button, original);
    } catch (error) {
      console.error(`[DevPilot] Falha ao abrir ${feature}`, error);
      window.toast?.(`Falha ao abrir ${original}.`);
      restorePlaceholder(button, original);
    }
  }

  const TRIGGERS = [
    ['[data-project-builder-open]', 'projectBuilder'],
    ['[data-example-project]', 'example'],
    ['.nav[data-view="reports"]', 'reports'],
    ['#voice-hero, #voice-dock', 'voice'],
    ['.nav[data-view="audit"]', 'audit'],
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

    const current = featureState.get(feature);
    if (current?.status === 'loaded') return;

    const intentEpoch = navigationEpoch;
    event.preventDefault();
    event.stopImmediatePropagation();
    trigger.setAttribute('aria-busy', 'true');
    void loadFeature(feature).then(ok => {
      trigger.removeAttribute('aria-busy');
      if (!ok) {
        const failures = featureState.get(feature)?.failures || [];
        console.error(`[DevPilot] Módulo ${feature} incompleto`, failures);
        window.toast?.(`Parte do módulo ${feature} não pôde ser carregada.`);
        return;
      }
      if (intentEpoch !== navigationEpoch || !trigger.isConnected) return;
      trigger.dataset.devpilotFeatureReplay = '1';
      trigger.click();
    }).catch(error => {
      trigger.removeAttribute('aria-busy');
      console.error(`[DevPilot] Falha ao abrir ${feature}`, error);
      window.toast?.(`Falha ao abrir ${feature}.`);
    });
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

  if (document.documentElement.classList.contains('devpilot-auth-pending')) {
    document.addEventListener('devpilot:dashboard-revealed', initializePlaceholders, {once: true});
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializePlaceholders, {once: true});
  } else {
    initializePlaceholders();
  }
})();
