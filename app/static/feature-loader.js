(() => {
  'use strict';

  const loadedFiles = new Set();
  const featureState = new Map();

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
      'build-game.js',
      'build-game-subphases.js',
      'build-game-new-session.js',
      'build-game-url-bonus.js',
      'build-game-weapons.js',
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
    if (name) loadedFiles.add(name);
  });

  const nextPaint = () => new Promise(resolve => {
    window.requestAnimationFrame(() => resolve());
  });

  const shortYield = () => new Promise(resolve => window.setTimeout(resolve, 35));

  function waitForExistingFeatureScript(script, name) {
    return new Promise(resolve => {
      const settle = ok => {
        if (ok) {
          script.dataset.devpilotFeatureLoadState = 'loaded';
          loadedFiles.add(name);
        } else {
          script.dataset.devpilotFeatureLoadState = 'failed';
          script.remove();
        }
        resolve(ok);
      };

      script.addEventListener('load', () => settle(true), {once: true});
      script.addEventListener('error', () => settle(false), {once: true});
    });
  }

  function loadScript(name) {
    if (!name || loadedFiles.has(name)) return Promise.resolve(true);

    const existing = Array.from(document.scripts).find(script => scriptName(script.src) === name);
    if (existing) {
      if (existing.dataset.devpilotFeatureLoadState === 'failed') {
        existing.remove();
      } else if (existing.dataset.devpilotFeatureScript === '1') {
        return waitForExistingFeatureScript(existing, name);
      } else {
        loadedFiles.add(name);
        return Promise.resolve(true);
      }
    }

    return new Promise(resolve => {
      const script = document.createElement('script');
      script.src = `/assets/${encodeURIComponent(name)}?v=ondemand-20260825-5`;
      script.async = false;
      script.dataset.devpilotFeatureScript = '1';
      script.dataset.devpilotFeatureLoadState = 'loading';
      script.onload = () => {
        script.dataset.devpilotFeatureLoadState = 'loaded';
        loadedFiles.add(name);
        resolve(true);
      };
      script.onerror = () => {
        script.dataset.devpilotFeatureLoadState = 'failed';
        script.remove();
        console.error(`[DevPilot] Falha ao carregar ${name}`);
        resolve(false);
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
    button.disabled = false;
    button.textContent = original;
    delete button.dataset.devpilotBusy;
  }

  function findUsersNav() {
    return Array.from(document.querySelectorAll('.sidebar nav .nav'))
      .find(item => item.textContent?.trim() === 'Usuários');
  }

  async function openPlaceholder(button, feature) {
    if (!button || button.dataset.devpilotBusy === '1') return;
    button.dataset.devpilotBusy = '1';
    button.disabled = true;
    const original = button.textContent;
    button.textContent = `${original} · carregando…`;

    try {
      const ok = await loadFeature(feature);
      if (!ok) {
        const failures = featureState.get(feature)?.failures || [];
        console.error(`[DevPilot] Módulo ${feature} incompleto`, failures);
        window.toast?.(`Não foi possível carregar ${original}. Tente novamente.`);
        restorePlaceholder(button, original);
        return;
      }

      await nextPaint();

      if (feature === 'profile') {
        const target = document.querySelector('.nav[data-profile-view="1"], .nav[data-view="profile"]');
        if (!target) {
          window.toast?.('Perfil foi carregado, mas a navegação não ficou disponível.');
          restorePlaceholder(button, original);
          return;
        }
        removePlaceholder(feature);
        target.click();
        return;
      }

      if (feature === 'users') {
        const target = findUsersNav();
        if (!target) {
          window.toast?.('Usuários foi carregado, mas a navegação não ficou disponível.');
          restorePlaceholder(button, original);
          return;
        }
        removePlaceholder(feature);
        target.click();
        return;
      }

      if (feature === 'game') {
        const target = document.querySelector('.nav[data-view="build-game"], .nav[data-view="game"], [data-build-game]');
        if (!target) {
          window.toast?.('Modo Jogo foi carregado, mas a navegação não ficou disponível.');
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

    const match = matchFeatureTrigger(event.target);
    if (!match) return;
    const {trigger, feature} = match;
    if (trigger.dataset.devpilotFeatureReplay === '1') {
      delete trigger.dataset.devpilotFeatureReplay;
      return;
    }

    const current = featureState.get(feature);
    if (current?.status === 'loaded') return;

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
      if (!trigger.isConnected) return;
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

  // Não altera o menu enquanto o modal de autenticação está ativo. O loader
  // pode ser baixado no core, mas seu primeiro trabalho de DOM só acontece
  // depois que o dashboard foi revelado.
  if (document.documentElement.classList.contains('devpilot-auth-pending')) {
    document.addEventListener('devpilot:dashboard-revealed', initializePlaceholders, {once: true});
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializePlaceholders, {once: true});
  } else {
    initializePlaceholders();
  }
})();
