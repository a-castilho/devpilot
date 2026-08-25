(() => {
  'use strict';

  const STORAGE_KEY = 'devpilot-workspace-skin';
  const CSS_ID = 'devpilot-workspace-skins-css';
  const PICKER_ID = 'devpilot-workspace-skin-picker';
  const SKINS = [
    {id: 'black', label: 'Preto', color: '#000000', themeColor: '#000000'},
    {id: 'yellow', label: 'Amarelo', color: '#ffd84d', themeColor: '#151000'},
    {id: 'red', label: 'Vermelho', color: '#ff526b', themeColor: '#150407'},
    {id: 'blue', label: 'Azul', color: '#4d94ff', themeColor: '#030b18'},
    {id: 'green', label: 'Verde', color: '#42d99c', themeColor: '#03110c'},
    {id: 'white', label: 'Branco', color: '#ffffff', themeColor: '#f5f7fa'},
  ];

  const FEATURE_BUNDLES = Object.freeze({
    projects: [
      'project-provisioning.js',
      'project-builder.js',
      'project-description-profile.js',
      'mobile-project-card-compact.js',
      'project-ships.js',
      'build-game-cockpit.js',
      'product-delivery-ui.js',
    ],
    tasks: [
      'consolidated-ui.js',
      'task-modal.js',
      'task-analytics.js',
      'task-failures.js',
      'task-image-upload.js',
      'analysis-commercial-proposal.js',
      'analysis-failure-actions.js',
      'analysis-incomplete-commercial.js',
      'approval-slider.js',
    ],
    providers: [
      'provider-models.js',
      'provider-ollama.js',
    ],
    reports: [
      'reports.js',
      'repeatai-analysis-scroll.js',
      'repeatai-live-graphs.js',
      'repeatai-dashboard-graphs.js',
      'repeatai-pattern-graphs.js',
    ],
    organizations: [
      'organization-normalization-ui.js',
    ],
    audit: [
      'audit-integrity.js',
    ],
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
      'cloud-admin.js',
      'deploy-admin.js',
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
      'mobile-game-mode.js',
      'game-linux-training.js',
    ],
    telemetry: [
      'telemetry-capture.js',
      'telemetry-replay-capture.js',
    ],
  });

  const featureState = new Map();
  const loadedFiles = new Set();
  const sleep = ms => new Promise(resolve => window.setTimeout(resolve, ms));
  const nextPaint = () => new Promise(resolve => window.requestAnimationFrame(() => resolve()));

  function scriptName(src) {
    try {
      return new URL(src, location.href).pathname.split('/').pop() || '';
    } catch (_) {
      return '';
    }
  }

  function indexExistingScripts() {
    document.scripts.forEach(script => {
      const name = scriptName(script.src);
      if (name) loadedFiles.add(name);
    });
  }

  function ensureStylesheet() {
    if (document.getElementById(CSS_ID)) return;
    const link = document.createElement('link');
    link.id = CSS_ID;
    link.rel = 'stylesheet';
    link.href = '/assets/workspace-skins.css?v=20260825-stable2';
    document.head.appendChild(link);
  }

  function validSkin(id) {
    return SKINS.some(skin => skin.id === id);
  }

  function updateThemeColor(skin) {
    let meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) {
      meta = document.createElement('meta');
      meta.name = 'theme-color';
      document.head.appendChild(meta);
    }
    meta.content = skin.themeColor;
  }

  function syncPicker(skin) {
    const picker = document.getElementById(PICKER_ID);
    if (!picker) return;
    picker.querySelectorAll('.workspace-skin-swatch').forEach(button => {
      const selected = button.dataset.skin === skin.id;
      button.setAttribute('aria-pressed', String(selected));
      button.title = selected ? `${skin.label} selecionado` : `Usar skin ${button.dataset.label}`;
    });
  }

  function applySkin(id, announce = false) {
    const skin = SKINS.find(item => item.id === id) || SKINS[0];
    const root = document.documentElement;
    root.removeAttribute('data-workspace-tone');
    root.dataset.workspaceSkin = skin.id;
    localStorage.setItem(STORAGE_KEY, skin.id);
    updateThemeColor(skin);
    syncPicker(skin);
    if (announce && typeof toast === 'function') toast(`Skin alterada para ${skin.label}.`);
    document.dispatchEvent(new CustomEvent('devpilot:workspace-skin', {detail: {skin: skin.id}}));
  }

  function removeLegacyArtifactsOnce() {
    document.querySelectorAll('.workspace-tone-picker').forEach(element => element.remove());
    document.documentElement.removeAttribute('data-workspace-tone');
    [document.body, document.documentElement].forEach(parent => {
      if (!parent) return;
      [...parent.childNodes].forEach(node => {
        if (node.nodeType !== Node.TEXT_NODE) return;
        const value = String(node.nodeValue || '').trim();
        if (value === '\\n' || value === '\\r\\n') node.remove();
      });
    });
  }

  function buildPicker() {
    if (document.getElementById(PICKER_ID)) return;

    const picker = document.createElement('div');
    picker.id = PICKER_ID;
    picker.className = 'workspace-skin-picker is-collapsed';
    picker.dataset.collapsed = 'true';
    picker.setAttribute('aria-label', 'Skins do DevPilot');

    const swatches = document.createElement('div');
    swatches.id = `${PICKER_ID}-swatches`;
    swatches.className = 'workspace-skin-swatches';
    swatches.setAttribute('role', 'group');
    swatches.setAttribute('aria-label', 'Escolha uma cor');
    swatches.setAttribute('aria-hidden', 'true');

    SKINS.forEach(skin => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'workspace-skin-swatch';
      button.dataset.skin = skin.id;
      button.dataset.label = skin.label;
      button.style.setProperty('--swatch', skin.color);
      button.setAttribute('aria-label', `Skin ${skin.label}`);
      button.setAttribute('aria-pressed', 'false');
      button.tabIndex = -1;
      button.addEventListener('click', () => applySkin(skin.id, true));
      swatches.appendChild(button);
    });

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'workspace-skin-toggle';
    toggle.textContent = '‹';
    toggle.setAttribute('aria-controls', swatches.id);
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'Mostrar seletor de cores');
    toggle.title = 'Mostrar cores';
    toggle.addEventListener('click', () => {
      const collapsed = !picker.classList.contains('is-collapsed');
      picker.classList.toggle('is-collapsed', collapsed);
      picker.dataset.collapsed = String(collapsed);
      swatches.setAttribute('aria-hidden', String(collapsed));
      swatches.querySelectorAll('.workspace-skin-swatch').forEach(button => {
        button.tabIndex = collapsed ? -1 : 0;
      });
      toggle.textContent = collapsed ? '‹' : '›';
      toggle.setAttribute('aria-expanded', String(!collapsed));
      toggle.setAttribute('aria-label', collapsed ? 'Mostrar seletor de cores' : 'Esconder seletor de cores');
      toggle.title = collapsed ? 'Mostrar cores' : 'Esconder cores';
    });

    picker.append(swatches, toggle);
    document.body.appendChild(picker);
  }

  /*
   * O servidor legado ainda tenta iniciar uma segunda onda de dezenas de scripts
   * depois do núcleo. Em máquinas com pouca memória isso reproduz o congelamento
   * mesmo quando o boot inicial é progressivo. Interceptamos APENAS os scripts
   * marcados pelo scheduler automático e simulamos sua conclusão sem baixá-los.
   * Cargas explícitas de feature usam outro marcador e passam normalmente.
   */
  function installDeferredCircuitBreaker() {
    const body = document.body;
    if (!body || body.dataset.devpilotDeferredCircuitBreaker === '1') return;
    body.dataset.devpilotDeferredCircuitBreaker = '1';

    const nativeAppendChild = body.appendChild;
    const appendNormally = node => nativeAppendChild.call(body, node);
    window.__devpilotNativeBodyAppend = appendNormally;

    body.appendChild = function appendChildWithCircuitBreaker(node) {
      const boot = window.__devpilotBoot;
      const isAutomaticDeferred = node instanceof HTMLScriptElement
        && node.dataset.devpilotProgressive === '1'
        && boot?.phase === 'deferred';

      if (!isAutomaticDeferred) return nativeAppendChild.call(this, node);

      const name = scriptName(node.src);
      boot.suppressed = Array.isArray(boot.suppressed) ? boot.suppressed : [];
      if (name && !boot.suppressed.includes(name)) boot.suppressed.push(name);
      node.dataset.devpilotSuppressed = '1';

      queueMicrotask(() => {
        try {
          if (typeof node.onload === 'function') node.onload(new Event('load'));
        } catch (error) {
          console.error('[DevPilot] Falha ao suprimir módulo automático', name, error);
        }
      });
      return node;
    };

    document.addEventListener('devpilot:authenticated-ui-ready', () => {
      try { delete body.appendChild; } catch (_) { body.appendChild = nativeAppendChild; }
    }, {once: true});
  }

  function loadFeatureScript(name) {
    if (!name || loadedFiles.has(name)) return Promise.resolve(true);

    const existing = [...document.scripts].find(script => scriptName(script.src) === name && script.isConnected);
    if (existing) {
      loadedFiles.add(name);
      return Promise.resolve(true);
    }

    return new Promise(resolve => {
      const script = document.createElement('script');
      script.src = `/assets/${encodeURIComponent(name)}?v=ondemand-20260825-1`;
      script.async = false;
      script.dataset.devpilotFeature = '1';
      script.onload = () => {
        loadedFiles.add(name);
        resolve(true);
      };
      script.onerror = () => {
        console.error(`[DevPilot] Falha ao carregar feature: ${name}`);
        resolve(false);
      };

      const append = window.__devpilotNativeBodyAppend;
      if (typeof append === 'function') append(script);
      else document.body.appendChild(script);
    });
  }

  async function loadFeature(feature) {
    const files = FEATURE_BUNDLES[feature];
    if (!Array.isArray(files)) return false;

    const existing = featureState.get(feature);
    if (existing?.status === 'loaded') return true;
    if (existing?.promise) return existing.promise;

    const promise = (async () => {
      const boot = window.__devpilotBoot = window.__devpilotBoot || {};
      boot.feature = feature;
      boot.featureLoading = true;
      const failures = [];

      for (const file of files) {
        const ok = await loadFeatureScript(file);
        if (!ok) failures.push(file);
        await nextPaint();
        await sleep(45);
      }

      boot.featureLoading = false;
      boot.feature = null;
      boot.featureFailures = failures;
      featureState.set(feature, {status: failures.length ? 'partial' : 'loaded', promise: null});
      document.dispatchEvent(new CustomEvent('devpilot:feature-ready', {
        detail: {feature, failures},
      }));
      return failures.length === 0;
    })();

    featureState.set(feature, {status: 'loading', promise});
    return promise;
  }

  window.__devpilotLoadFeature = loadFeature;
  window.__devpilotFeatureState = featureState;

  function featureTrigger(target) {
    if (!(target instanceof Element)) return null;
    const rules = [
      ['.nav[data-view="projects"], [data-project-builder-open]', 'projects'],
      ['.nav[data-view="tasks"], [data-open="task-modal"], [data-project-task]', 'tasks'],
      ['.nav[data-view="providers"]', 'providers'],
      ['.nav[data-view="reports"]', 'reports'],
      ['.nav[data-view="audit"]', 'audit'],
      ['.nav[data-view="organizations"]', 'organizations'],
      ['[data-example-project]', 'example'],
      ['#voice-hero, #voice-dock, #voice-start, #voice-send', 'voice'],
      ['.nav-group-toggle[data-nav-group-toggle="super-admin"]', 'admin'],
      ['[data-build-game], [data-game-mode], [data-game-open]', 'game'],
    ];

    for (const [selector, feature] of rules) {
      const trigger = target.closest(selector);
      if (trigger) return {trigger, feature};
    }
    return null;
  }

  function installFeatureGate() {
    if (document.documentElement.dataset.devpilotFeatureGate === '1') return;
    document.documentElement.dataset.devpilotFeatureGate = '1';

    document.addEventListener('click', event => {
      const match = featureTrigger(event.target);
      if (!match) return;
      const {trigger, feature} = match;
      if (trigger.dataset.devpilotFeatureReplay === '1') {
        delete trigger.dataset.devpilotFeatureReplay;
        return;
      }

      const stateItem = featureState.get(feature);
      if (stateItem?.status === 'loaded') return;

      event.preventDefault();
      event.stopImmediatePropagation();

      trigger.setAttribute('aria-busy', 'true');
      void loadFeature(feature).then(ok => {
        trigger.removeAttribute('aria-busy');
        if (!ok && typeof toast === 'function') {
          toast(`Parte do módulo ${feature} não pôde ser carregada.`);
        }
        if (!trigger.isConnected) return;
        trigger.dataset.devpilotFeatureReplay = '1';
        trigger.click();
      }).catch(error => {
        trigger.removeAttribute('aria-busy');
        console.error(`[DevPilot] Falha ao abrir ${feature}`, error);
        if (typeof toast === 'function') toast(`Falha ao abrir ${feature}.`);
      });
    }, true);
  }

  function initialize() {
    indexExistingScripts();
    installDeferredCircuitBreaker();
    installFeatureGate();
    ensureStylesheet();
    removeLegacyArtifactsOnce();
    buildPicker();
    const saved = localStorage.getItem(STORAGE_KEY);
    applySkin(validSkin(saved) ? saved : 'black', false);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once: true});
  } else {
    initialize();
  }
})();
