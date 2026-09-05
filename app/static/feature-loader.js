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
  const PROJECTS_LIGHT_FILES = new Set([
    'mobile-project-card-compact.js',
    'project-delete-ui.js',
  ]);
  const FEATURE_SCRIPT_TIMEOUT_MS = 12000;
  let navigationEpoch = 0;

  const FEATURE_BUNDLES = Object.freeze({
    shellCommon: [
      'viewport-adaptive-v15.js',
      'page-navigation-v26.js',
      'dashboard-user-v21.js',
      'executions-v18.js',
      'executions-focus-v19.js',
    ],

    shell: ['simplified-nav.js'],
    mobileShell: ['mobile-accordion-menu.js'],
    profile: ['profile.js'],
    users: ['users.js'],

    providers: [
      'provider-models.js',
      'provider-ollama.js',
    ],

    // O cadastro simples deve ter um único dono de eventos. O runtime legado de
    // provisionamento continua disponível na tela de projetos, mas não entra no
    // clique de Novo projeto e não pode interceptar o submit do builder simples.
    projectBuilder: [
      'project-builder.js',
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

    /*
     * Execuções: tudo que pode alterar cards/ações entra antes da tela ficar
     * interativa. Assim o clique em Detalhes nunca troca o renderer ou o layout.
     */
    tasks: [
      'tasks-operational-ui.js',
      'project-delete-ui.js',
      'task-recovery-flow.js',
      'tasks-recovery-layout-v41.js',
      'task-completion-documentation.js',
    ],

    tasksAnalytics: ['task-analytics.js'],

    /* Detalhes é estritamente local: não pode re-renderizar a lista de execuções. */
    tasksDetails: [
      'execution-results-v28.js',
    ],

    /* Recursos legados/auxiliares permanecem disponíveis fora do clique Detalhes. */
    tasksEnhancements: [
      'task-failures.js',
      'task-image-upload.js',
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

  const assetRevision = name => String(
    window.__devpilotAssetRevisions?.[name] || FEATURE_ASSET_REVISION
  );

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

  const detectedMemory = Number(navigator.deviceMemory || 0);
  const detectedCpu = Number(navigator.hardwareConcurrency || 0);
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches === true;
  const lowPowerDevice =
    reducedMotion ||
    (detectedMemory > 0 && detectedMemory <= 4) ||
    (detectedCpu > 0 && detectedCpu <= 2);

  document.documentElement.classList.toggle('devpilot-low-power', lowPowerDevice);
  window.__devpilotFeaturePerf = window.__devpilotFeaturePerf || [];

  const constrainedProjectsRuntime = () => (
    lowPowerDevice ||
    window.matchMedia?.('(max-width: 900px)')?.matches === true
  );

  function filesForFeature(feature) {
    const files = FEATURE_BUNDLES[feature];
    if (!Array.isArray(files)) return files;
    if (feature === 'projects' && constrainedProjectsRuntime()) {
      return files.filter(name => PROJECTS_LIGHT_FILES.has(name));
    }
    return files;
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
      script.src = `/assets/${encodeURIComponent(name)}?v=${encodeURIComponent(assetRevision(name))}`;
      script.async = false;
      script.dataset.devpilotFeatureScript = '1';
      script.dataset.devpilotFeatureLoadState = 'loading';
      script.onload = () => finish(true);
      script.onerror = () => finish(false);
      document.body.appendChild(script);
    });
  }

  async function loadFeature(feature, options = {}) {
    const files = filesForFeature(feature);
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
          feature, file, durationMs:Math.round(performance.now() - started), ok, at:Date.now(),
        });
        await nextPaint();
        await shortYield();
      }

      const status = cancelled ? 'partial' : failures.length ? 'partial' : 'loaded';
      featureState.set(feature, {status, failures, cancelled, promise:null});
      document.dispatchEvent(new CustomEvent('devpilot:feature-ready', {
        detail:{feature, failures, cancelled, durationMs:Math.round(performance.now() - featureStarted)},
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

  const VIEW_FEATURES = Object.freeze({
    organizations:'organizations',
    projects:'projects',
    tasks:'tasks',
    providers:'providers',
    reports:'reports',
    audit:'audit',
  });

  async function navigateDirect(viewName, source = 'link') {
    if (!viewName) return false;
    navigationEpoch += 1;
    const intentEpoch = navigationEpoch;
    restorePendingPlaceholders();

    // No celular, o roteador opcional pode ainda estar carregando quando o
    // usuário toca em Projetos. Nesse intervalo nunca chamamos showView(), pois
    // o showView nativo dispara loadProjects() com o payload pesado de 50 itens.
    const mobileProjectsFallback = (
      viewName === 'projects' &&
      window.matchMedia?.('(max-width: 900px)')?.matches === true &&
      typeof window.devpilotNavigate !== 'function'
    );

    // A troca de tela pertence ao caminho crítico do clique. Recursos opcionais
    // são hidratados depois e nunca podem bloquear a navegação principal.
    let navigated = false;
    let deferredMobileProjectsLoad = false;
    if (typeof window.devpilotNavigate === 'function') {
      navigated = window.devpilotNavigate(viewName, {source, immediate:true});
    } else if (mobileProjectsFallback) {
      document.querySelectorAll('.view').forEach(view => {
        const active = view.id === 'projects-view';
        view.classList.toggle('active', active);
        view.hidden = !active;
        view.setAttribute('aria-hidden', active ? 'false' : 'true');
      });
      document.querySelectorAll('.sidebar nav .nav[data-view]').forEach(nav => {
        nav.classList.toggle('active', String(nav.dataset.view || '') === 'projects');
      });
      const title = document.querySelector('#page-title');
      if (title) title.textContent = 'Projetos';
      document.documentElement.dataset.devpilotView = 'projects';
      navigated = true;
      deferredMobileProjectsLoad = true;
    } else if (typeof showView === 'function') {
      showView(viewName);
      navigated = true;
    }

    const feature = VIEW_FEATURES[viewName];
    if (feature) {
      void loadFeature(feature, {intentEpoch}).then(ready => {
        if (intentEpoch !== navigationEpoch) return;
        if (!ready) window.toast?.('Tela aberta com alguns recursos opcionais indisponíveis.');
        const guardedMobileProjectsLoad = (
          deferredMobileProjectsLoad &&
          typeof window.loadProjects === 'function' &&
          Boolean(window.loadProjects.__devpilotProjectsOriginal)
        );
        if (guardedMobileProjectsLoad) {
          void Promise.resolve(window.loadProjects()).catch(error => {
            console.error('[DevPilot] Falha ao carregar Projetos em modo leve', error);
            window.toast?.('Não foi possível carregar os projetos.');
          });
        } else if (deferredMobileProjectsLoad) {
          console.error('[DevPilot] Guard mobile de Projetos indisponível; carga pesada bloqueada');
          window.toast?.('Modo leve de Projetos indisponível. Tente novamente.');
        }
      }).catch(error => {
        if (intentEpoch !== navigationEpoch) return;
        console.error(`[DevPilot] Falha ao hidratar ${viewName}`, error);
        window.toast?.('Tela aberta; recursos opcionais serão tentados novamente depois.');
      });
    }

    return navigated;
  }

  function openTaskDirect(trigger) {
    const projectId = String(trigger?.dataset?.projectTask || '');
    const source = projectId ? 'project' : 'dashboard';
    if (typeof window.devpilotOpenTaskModal === 'function') {
      return window.devpilotOpenTaskModal({projectId, source});
    }
    void loadFeature('taskModal').then(() => document.querySelector('#task-modal')?.showModal?.());
    return true;
  }

  function showProjectBuilderImmediately() {
    if (typeof showView === 'function') showView('new-project');
    else {
      document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view.id === 'new-project-view'));
    }
    const title = document.querySelector('#page-title');
    if (title) title.textContent = 'Novo projeto';
    window.scrollTo({top:0, left:0, behavior:'auto'});
  }

  async function openProjectBuilderDirect(trigger) {
    if (!trigger || trigger.dataset.devpilotOpening === '1') return false;
    trigger.dataset.devpilotOpening = '1';
    trigger.setAttribute('aria-busy', 'true');

    // Feedback visual primeiro: rede, organizações e bundles nunca podem segurar
    // a troca para a tela de cadastro.
    showProjectBuilderImmediately();

    try {
      const ready = await loadFeature('projectBuilder');
      const feature = featureState.get('projectBuilder') || {};
      const failures = Array.isArray(feature.failures) ? feature.failures : [];
      const form = document.querySelector('#project-builder-form');
      const builderReady = form?.dataset.simpleBuilderReady === '1';
      if (!builderReady || failures.includes('project-builder.js')) {
        throw new Error('Não foi possível carregar o cadastro de projeto.');
      }
      if (!ready) window.toast?.('Cadastro aberto; algum recurso auxiliar ficou indisponível.');

      return true;
    } catch (error) {
      console.error('[DevPilot] Falha ao abrir Novo projeto', error);
      window.toast?.(error?.message || 'Não foi possível abrir o cadastro de projeto.');
      return false;
    } finally {
      trigger.removeAttribute('aria-busy');
      delete trigger.dataset.devpilotOpening;
    }
  }

  async function analyzeProjectDirect(trigger) {
    const projectId = String(trigger?.dataset?.id || '');
    if (!projectId || typeof api !== 'function') return false;
    if (trigger.dataset.devpilotAnalyzing === '1') return false;
    trigger.dataset.devpilotAnalyzing = '1';
    trigger.disabled = true;
    try {
      await api(`/projects/${encodeURIComponent(projectId)}/analyze`, {method:'POST'});
      window.toast?.('Análise técnica enfileirada');
      if (typeof loadDashboard === 'function') await loadDashboard();
      return true;
    } catch (error) {
      window.toast?.(error?.message || 'Falha ao iniciar análise');
      return false;
    } finally {
      trigger.disabled = false;
      delete trigger.dataset.devpilotAnalyzing;
    }
  }

  const TRIGGERS = [
    ['[data-example-project]', 'example'],
    ['#tasks-v9-indicators', 'tasksAnalytics'],
    ['.tasks-v9-details, .task-instructions-load', 'tasksDetails'],
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
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;

    const placeholder = target.closest('[data-devpilot-feature-placeholder]');
    if (placeholder) {
      event.preventDefault();
      event.stopImmediatePropagation();
      void openPlaceholder(placeholder, placeholder.dataset.devpilotFeaturePlaceholder);
      return;
    }

    const taskTrigger = target.closest('[data-open="task-modal"], [data-project-task]');
    if (taskTrigger) {
      event.preventDefault();
      event.stopImmediatePropagation();
      openTaskDirect(taskTrigger);
      return;
    }

    const projectBuilderTrigger = target.closest('[data-project-builder-open]');
    if (projectBuilderTrigger) {
      event.preventDefault();
      event.stopImmediatePropagation();
      void openProjectBuilderDirect(projectBuilderTrigger);
      return;
    }

    const analyzeTrigger = target.closest('#projects-list .analyze[data-id]');
    if (analyzeTrigger) {
      event.preventDefault();
      event.stopImmediatePropagation();
      void analyzeProjectDirect(analyzeTrigger);
      return;
    }

    const viewTrigger = target.closest('[data-view]');
    if (viewTrigger && !viewTrigger.dataset.devpilotFeaturePlaceholder) {
      const viewName = String(viewTrigger.dataset.view || '');
      if (viewName) {
        event.preventDefault();
        event.stopImmediatePropagation();
        void navigateDirect(viewName, viewTrigger.closest('.sidebar') ? 'menu' : 'link');
        return;
      }
    }

    const match = matchFeatureTrigger(target);
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
    const feature = VIEW_FEATURES[view];
    if (feature) void loadFeature(feature);
  }

  function initializeAuthenticatedUi() {
    initializePlaceholders();
    void loadFeature('shellCommon');
    if (window.matchMedia('(min-width: 901px)').matches) void loadFeature('shell');
    else initializeMobileShell();
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
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initializeIfAuthenticated, {once:true});
    else initializeIfAuthenticated();
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
