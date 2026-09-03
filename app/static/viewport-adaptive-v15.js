(() => {
  'use strict';

  if (window.__devpilotViewportAdaptiveV15) return;
  window.__devpilotViewportAdaptiveV15 = true;

  const root = document.documentElement;
  let frame = 0;
  let lastSignature = '';
  let lastObservedWidth = 0;

  function metrics() {
    const viewport = window.visualViewport;
    const width = Math.max(1, Number(viewport?.width || window.innerWidth || 1));
    const height = Math.max(1, Number(viewport?.height || window.innerHeight || 1));
    const screenWidth = Math.max(1, Number(window.screen?.availWidth || window.screen?.width || width));
    const screenHeight = Math.max(1, Number(window.screen?.availHeight || window.screen?.height || height));
    const ratio = width / screenWidth;
    const dpr = Number(window.devicePixelRatio || 1);
    const zoomedOut = width > 900 && (ratio >= 1.08 || (dpr < 0.95 && ratio > 1.01));
    const physicalWidth = Math.min(screenWidth, width);
    const physicalHeight = Math.min(screenHeight, height);
    const compact = physicalWidth <= 1280 || height <= 820 || zoomedOut;
    const short = physicalHeight <= 820 || height <= 760;
    const boost = zoomedOut ? Math.min(2.25, Math.max(1.08, ratio)) : 1;
    return {width, height, screenWidth, screenHeight, ratio, dpr, zoomedOut, compact, short, boost};
  }

  function viewportMode(value) {
    if (value.width <= 600) return 'phone';
    if (value.width <= 900) return 'tablet';
    return value.compact ? 'compact' : 'wide';
  }

  function setClass(name, enabled) {
    if (root.classList.contains(name) === enabled) return;
    root.classList.toggle(name, enabled);
  }

  function setStyle(name, value) {
    if (root.style.getPropertyValue(name) === value) return;
    root.style.setProperty(name, value);
  }

  function setData(name, value) {
    if (root.dataset[name] === value) return;
    root.dataset[name] = value;
  }

  function apply() {
    frame = 0;
    const value = metrics();
    const mode = viewportMode(value);
    const width = Math.round(value.width);
    const height = Math.round(value.height);
    const boost3 = value.boost.toFixed(3);
    const boost2 = value.boost.toFixed(2);

    const mobile = width <= 900;
    const signature = mobile
      ? [width, mode, value.zoomedOut, value.compact, boost3].join('|')
      : [width, height, mode, value.zoomedOut, value.compact, value.short, boost3].join('|');

    lastObservedWidth = width;
    if (signature === lastSignature) return;
    lastSignature = signature;

    setClass('dp-zoom-out', value.zoomedOut);
    setClass('dp-space-compact', value.compact);
    setClass('dp-space-short', value.short);
    setClass('dp-vp-phone', value.width <= 600);
    setClass('dp-vp-tablet', value.width > 600 && value.width <= 900);
    setClass('dp-vp-notebook', value.width > 900 && value.compact);
    setClass('dp-vp-wide', value.width > 1280 && !value.compact);
    setStyle('--dp-ui-boost', boost3);
    setStyle('--dp-viewport-width', `${width}px`);
    setStyle('--dp-viewport-height', `${height}px`);
    setData('dpViewport', mode);
    setData('dpZoom', value.zoomedOut ? 'out' : 'normal');
    setData('dpBoost', boost2);
    document.dispatchEvent(new CustomEvent('devpilot:viewport-adapted', {detail:value}));
  }

  function schedule() {
    if (frame) return;
    frame = window.requestAnimationFrame(apply);
  }

  function scheduleViewportResize() {
    const width = Math.round(Number(window.visualViewport?.width || window.innerWidth || 0));
    if (width > 0 && width <= 900 && lastObservedWidth > 0 && Math.abs(width - lastObservedWidth) < 2) return;
    schedule();
  }

  function scheduleOrientationChange() {
    window.setTimeout(schedule, 40);
  }

  function ensureStylesheet(selector, href, datasetKey) {
    if (document.querySelector(selector)) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    link.dataset[datasetKey] = '1';
    document.head.appendChild(link);
  }

  function loadCss() {
    ensureStylesheet('link[data-layout-adaptive-v15]', '/assets/layout-adaptive-v15.css?v=20260830-1', 'layoutAdaptiveV15');
    ensureStylesheet('link[data-sidebar-responsive-v16]', '/assets/sidebar-responsive-v16.css?v=20260830-1', 'sidebarResponsiveV16');
    ensureStylesheet('link[data-sidebar-state-v24]', '/assets/sidebar-state-v24.css?v=20260830-1', 'sidebarStateV24');
    ensureStylesheet('link[data-dashboard-user-v20]', '/assets/dashboard-user-v20.css?v=20260830-1', 'dashboardUserV20');
    ensureStylesheet('link[data-users-layout-v25]', '/assets/users-layout-v25.css?v=20260830-1', 'usersLayoutV25');
    ensureStylesheet('link[data-page-navigation-v26]', '/assets/page-navigation-v26.css?v=20260903-project-v94', 'pageNavigationV26');
    ensureStylesheet('link[data-layout-scale-v36]', '/assets/layout-scale-v36.css?v=20260830-1', 'layoutScaleV36');
    ensureStylesheet('link[data-layout-authority-v37]', '/assets/layout-authority-v37.css?v=20260830-1', 'layoutAuthorityV37');
  }

  function openTaskModalSafe(trigger) {
    const projectId = String(trigger?.dataset?.projectTask || '');
    const source = projectId ? 'project' : 'dashboard';
    const modal = document.querySelector('#task-modal');

    if (modal && !modal.open && typeof modal.showModal === 'function') {
      try { modal.showModal(); } catch (_) {}
    }

    if (typeof window.devpilotOpenTaskModal === 'function') {
      try { window.devpilotOpenTaskModal({projectId, source}); } catch (error) {
        console.warn('[DevPilot] Falha ao inicializar modal já disponível', error);
      }
      return;
    }

    if (typeof window.__devpilotLoadFeature === 'function') {
      void Promise.resolve(window.__devpilotLoadFeature('taskModal')).then(() => {
        if (typeof window.devpilotOpenTaskModal === 'function') {
          return window.devpilotOpenTaskModal({projectId, source});
        }
        const readyModal = document.querySelector('#task-modal');
        if (readyModal && !readyModal.open) readyModal.showModal?.();
        return true;
      }).catch(error => {
        console.error('[DevPilot] Falha ao carregar Nova execução', error);
        window.toast?.('Não foi possível carregar todos os campos da execução.');
      });
    }
  }

  function installTaskActionSafeOpen() {
    if (window.__devpilotTaskActionSafeOpenV41) return;
    window.__devpilotTaskActionSafeOpenV41 = true;

    // Novo projeto pertence exclusivamente ao feature-loader. Este runtime
    // protege apenas Nova execução, evitando concorrência entre owners de CTA.
    window.addEventListener('click', event => {
      const target = event.target instanceof Element ? event.target : null;
      if (!target) return;

      const taskTrigger = target.closest('[data-open="task-modal"], [data-project-task]');
      if (!taskTrigger) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      openTaskModalSafe(taskTrigger);
    }, true);
  }

  loadCss();
  apply();
  installTaskActionSafeOpen();

  window.addEventListener('resize', scheduleViewportResize, {passive:true});
  window.addEventListener('orientationchange', scheduleOrientationChange, {passive:true});
  window.visualViewport?.addEventListener('resize', scheduleViewportResize, {passive:true});
  document.addEventListener('devpilot:view-changed', schedule);
  document.addEventListener('devpilot:dashboard-revealed', schedule);
  document.addEventListener('devpilot:feature-ready', schedule);

  console.info('[DevPilot] Viewport Adaptive V41 · Novo projeto com owner único');
})();
